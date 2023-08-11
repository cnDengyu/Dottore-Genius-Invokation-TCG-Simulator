import unittest

from dgisim.tests.test_characters.common_imports import *


class TestYaeMiko(unittest.TestCase):
    BASE_GAME = ACTION_TEMPLATE.factory().f_player1(
        lambda p: p.factory().f_characters(
            lambda cs: cs.factory().active_character_id(
                2
            ).character(
                YaeMiko.from_default(2)
            ).build()
            # ).f_hand_cards(
            #     lambda hcs: hcs.add(TheScentRemained)
        ).build()
    ).build()
    assert type(BASE_GAME.get_player1().just_get_active_character()) is YaeMiko

    def test_normal_attack(self):
        a1, a2 = PuppetAgent(), PuppetAgent()
        gsm = GameStateMachine(self.BASE_GAME, a1, a2)
        a1.inject_action(SkillAction(
            skill=CharacterSkill.NORMAL_ATTACK,
            instruction=DiceOnlyInstruction(dices=ActualDices({Element.OMNI: 3})),
        ))
        p2ac = gsm.get_game_state().get_player2().just_get_active_character()
        self.assertEqual(p2ac.get_hp(), 10)

        gsm.player_step()
        gsm.auto_step()
        p2ac = gsm.get_game_state().get_player2().just_get_active_character()
        self.assertEqual(p2ac.get_hp(), 9)
        self.assertIn(Element.ELECTRO, p2ac.get_elemental_aura())

    def test_elemental_skill1(self):
        a1, a2 = PuppetAgent(), LazyAgent()
        base_game = self.BASE_GAME.factory().f_player2(
            lambda p2: p2.factory().phase(Act.END_PHASE).build()
        ).build()
        gsm = GameStateMachine(base_game, a1, a2)
        a1.inject_actions([
            SkillAction(
                skill=CharacterSkill.ELEMENTAL_SKILL1,
                instruction=DiceOnlyInstruction(dices=ActualDices({Element.OMNI: 3})),
            ),
            SkillAction(
                skill=CharacterSkill.ELEMENTAL_SKILL1,
                instruction=DiceOnlyInstruction(dices=ActualDices({Element.OMNI: 3})),
            ),
            SkillAction(
                skill=CharacterSkill.ELEMENTAL_SKILL1,
                instruction=DiceOnlyInstruction(dices=ActualDices({Element.OMNI: 3})),
            ),
        ])
        p2ac = gsm.get_game_state().get_player2().just_get_active_character()
        self.assertEqual(p2ac.get_hp(), 10)

        # first skill
        gsm.player_step()
        gsm.auto_step()  # p1 skill
        p1 = gsm.get_game_state().get_player1()
        p2ac = gsm.get_game_state().get_player2().just_get_active_character()
        self.assertEqual(p2ac.get_hp(), 10)
        self.assertFalse(p2ac.get_elemental_aura().has_aura())
        self.assertIn(SesshouSakura, p1.get_summons())
        self.assertEqual(p1.get_summons().just_find(SesshouSakura).usages, 3)

        # second skill increases usage to 6
        gsm.player_step()
        gsm.auto_step()  # p1 skill
        p1 = gsm.get_game_state().get_player1()
        self.assertIn(SesshouSakura, p1.get_summons())
        self.assertEqual(p1.get_summons().just_find(SesshouSakura).usages, 6)

        # summon usages cap at 6
        gsm.player_step()
        gsm.auto_step()  # p1 skill
        p1 = gsm.get_game_state().get_player1()
        self.assertIn(SesshouSakura, p1.get_summons())
        self.assertEqual(p1.get_summons().just_find(SesshouSakura).usages, 6)

    def test_elemental_burst(self):
        a1, a2 = PuppetAgent(), PuppetAgent()
        base_game_state = fill_energy_for_all(self.BASE_GAME)

        # burst with no Sesshou Sakura
        gsm = GameStateMachine(base_game_state, a1, a2)
        a1.inject_action(
            SkillAction(
                skill=CharacterSkill.ELEMENTAL_BURST,
                instruction=DiceOnlyInstruction(dices=ActualDices({Element.OMNI: 3})),
            )
        )
        gsm.player_step()
        gsm.auto_step()
        p1 = gsm.get_game_state().get_player1()
        p2ac = gsm.get_game_state().get_player2().just_get_active_character()
        self.assertEqual(p2ac.get_hp(), 6)
        self.assertIn(Element.ELECTRO, p2ac.get_elemental_aura())
        self.assertNotIn(TenkoThunderboltsStatus, p1.get_combat_statuses())
        self.assertEqual(p1.just_get_active_character().get_energy(), 0)

        # burst with Sesshou Sakura
        game_state = AddSummonEffect(
            target_pid=Pid.P1, summon=SesshouSakura
        ).execute(base_game_state)
        game_state = step_skill(game_state, Pid.P1, CharacterSkill.ELEMENTAL_BURST)
        p1 = game_state.get_player1()
        self.assertIn(TenkoThunderboltsStatus, p1.get_combat_statuses())
        self.assertNotIn(SesshouSakura, p1.get_summons())
        post_burst_state = game_state

        with self.subTest(condition="oppo end round"):
            game_state = step_action(post_burst_state, Pid.P2, EndRoundAction())
            p2ac = game_state.get_player2().just_get_active_character()
            self.assertEqual(p2ac.get_hp(), 3)
            self.assertIn(Element.ELECTRO, p2ac.get_elemental_aura())
            p1 = game_state.get_player1()
            self.assertNotIn(TenkoThunderboltsStatus, p1.get_combat_statuses())
            self.assertNotIn(SesshouSakura, p1.get_summons())

        with self.subTest(condition="oppo take action"):
            game_state = step_skill(post_burst_state, Pid.P2, CharacterSkill.NORMAL_ATTACK)
            p2ac = game_state.get_player2().just_get_active_character()
            self.assertEqual(p2ac.get_hp(), 3)
            self.assertIn(Element.ELECTRO, p2ac.get_elemental_aura())
            p1 = game_state.get_player1()
            self.assertNotIn(TenkoThunderboltsStatus, p1.get_combat_statuses())
            self.assertNotIn(SesshouSakura, p1.get_summons())

    def test_sesshou_sakura_summon(self):
        # p1 has the summon with usages <= 3 and ends the round
        base_game = OverrideSummonEffect(Pid.P1, SesshouSakura(usages=3)).execute(self.BASE_GAME)
        game_state = step_action(base_game, Pid.P1, EndRoundAction())
        p1 = game_state.get_player1()
        p2ac = game_state.get_player2().just_get_active_character()
        self.assertEqual(p2ac.get_hp(), 10)
        self.assertNotIn(Element.ELECTRO, p2ac.get_elemental_aura())
        self.assertIn(SesshouSakura, p1.get_summons())
        self.assertEqual(p1.get_summons().just_find(SesshouSakura).usages, 3)

        # p1 has the summon with usages >= 4 and ends the round
        base_game = OverrideSummonEffect(Pid.P1, SesshouSakura(usages=4)).execute(self.BASE_GAME)
        game_state = step_action(base_game, Pid.P1, EndRoundAction())
        p1 = game_state.get_player1()
        p2ac = game_state.get_player2().just_get_active_character()
        self.assertEqual(p2ac.get_hp(), 9)
        self.assertIn(Element.ELECTRO, p2ac.get_elemental_aura())
        self.assertIn(SesshouSakura, p1.get_summons())
        self.assertEqual(p1.get_summons().just_find(SesshouSakura).usages, 3)

        # test that normal end round attack is working
        base_game = OverrideSummonEffect(Pid.P1, SesshouSakura(usages=3)).execute(self.BASE_GAME)
        game_state = step_action(base_game, Pid.P1, EndRoundAction())
        game_state = step_action(game_state, Pid.P2, EndRoundAction())
        p1 = game_state.get_player1()
        p2ac = game_state.get_player2().just_get_active_character()
        self.assertEqual(p2ac.get_hp(), 9)
        self.assertIn(Element.ELECTRO, p2ac.get_elemental_aura())
        self.assertIn(SesshouSakura, p1.get_summons())
        self.assertEqual(p1.get_summons().just_find(SesshouSakura).usages, 2)

        # test summon disappears on last attack
        base_game = OverrideSummonEffect(Pid.P1, SesshouSakura(usages=1)).execute(self.BASE_GAME)
        game_state = step_action(base_game, Pid.P1, EndRoundAction())
        game_state = step_action(game_state, Pid.P2, EndRoundAction())
        p1 = game_state.get_player1()
        p2ac = game_state.get_player2().just_get_active_character()
        self.assertEqual(p2ac.get_hp(), 9)
        self.assertIn(Element.ELECTRO, p2ac.get_elemental_aura())
        self.assertNotIn(SesshouSakura, p1.get_summons())
