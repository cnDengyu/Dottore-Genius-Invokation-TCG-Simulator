from __future__ import annotations
from dataclasses import dataclass, replace
from typing import ClassVar, cast

from typing_extensions import Self

from src.dgisim.action.action import *
from src.dgisim.agents import *
from src.dgisim.card.card import Card
from src.dgisim.card.cards import Cards
from src.dgisim.character.character import Character
from src.dgisim.character.enums import CharacterSkill
from src.dgisim.dice import ActualDice
from src.dgisim.effect.effect import *
from src.dgisim.effect.enums import DynamicCharacterTarget, TriggeringSignal, Zone
from src.dgisim.effect.structs import DamageType, StaticTarget
from src.dgisim.element import *
from src.dgisim.event import *
from src.dgisim.game_state_machine import GameStateMachine
from src.dgisim.helper.level_print import GamePrinter
from src.dgisim.helper.quality_of_life import *
from src.dgisim.phase import Phase
from src.dgisim.state.enums import Pid
from src.dgisim.state.game_state import GameState
from src.dgisim.state.player_state import PlayerState
from src.dgisim.status.enums import *
from src.dgisim.status.status import *


@dataclass(frozen=True, kw_only=True)
class _TempTestDmgListenerStatus(PlayerHiddenStatus):
    dmgs: tuple[SpecificDamageEffect, ...] = ()

    def _inform(
            self,
            game_state: GameState,
            status_source: StaticTarget,
            info_type: Informables,
            information: InformableEvent,
    ) -> Self:
        if info_type is Informables.DMG_DELT:
            assert isinstance(information, DmgIEvent)
            if information.dmg.source.pid is status_source.pid:
                return replace(self, dmgs=self.dmgs + (information.dmg,))
        return self


@dataclass(frozen=True, kw_only=True)
class _TempTestInfiniteRevivalStatus(HiddenStatus, RevivalStatus):
    REACTABLE_SIGNALS = frozenset({
        TriggeringSignal.TRIGGER_REVIVAL,
    })

    def revivable(self, game_state: GameState, char: StaticTarget) -> bool:
        return True

    def _post_update_react_to_signal(
            self,
            game_state: GameState,
            effects: list[Effect],
            source: StaticTarget,
            signal: TriggeringSignal,
    ) -> list[Effect]:
        if signal is TriggeringSignal.TRIGGER_REVIVAL:
            effects.append(
                ReviveRecoverHPEffect(
                    target=source,
                    recovery=BIG_INT,
                )
            )
        return effects


@dataclass(frozen=True, kw_only=True)
class _TempTestStatus(CharacterStatus):
    dmg: int
    elem: Element
    target: StaticTarget
    REACTABLE_SIGNALS: ClassVar[frozenset[TriggeringSignal]] = frozenset((
        TriggeringSignal.GAME_START,
    ))

    def _react_to_signal(
            self, game_state: GameState, source: StaticTarget, signal: TriggeringSignal
    ) -> tuple[list[Effect], None | Self]:
        if signal is TriggeringSignal.GAME_START:
            return [
                SpecificDamageEffect(
                    source=source,
                    target=source,
                    element=self.elem,
                    damage=self.dmg,
                    damage_type=DamageType(status=True, no_boost=True),
                )
            ], None
        return [], self


@dataclass(frozen=True, kw_only=True)
class _TempTestThickShieldStatus(CharacterStatus, StackedShieldStatus):
    """
    can take BIG_INT to BIG_INT^2 non-PIERCING damage
    """
    usages: int = BIG_INT
    MAX_USAGES: ClassVar[int] = BIG_INT
    SHIELD_AMOUNT: ClassVar[int] = BIG_INT


def add_damage_effect(
        game_state: GameState,
        damage: int,
        elem: Element,
        pid: Pid = Pid.P2,
        char_id: None | int = None,
        damage_type: None | DamageType = None,
) -> GameState:
    """
    Adds ReferredDamageEffect to Player2's active character with `damage` and `elem` from Player1's
    active character (id=1)
    """
    return game_state.factory().f_effect_stack(
        lambda es: es.push_many_fl((
            ReferredDamageEffect(
                source=StaticTarget(
                    pid.other(),
                    Zone.CHARACTERS,
                    case_val(char_id is None, 1, char_id),  # type: ignore
                ),
                target=DynamicCharacterTarget.OPPO_ACTIVE,
                element=elem,
                damage=damage,
                damage_type=case_val(damage_type is None, DamageType(),
                                     damage_type),  # type: ignore
            ),
            AliveMarkCheckerEffect(),
            DefeatedMarkCheckerEffect(),
            DeathCheckCheckerEffect(),
        ))
    ).build()


def add_dmg_listener(game_state: GameState, pid: Pid) -> GameState:
    return AddHiddenStatusEffect(
        pid,
        status=_TempTestDmgListenerStatus,
    ).execute(game_state)


def apply_elemental_aura(
        game_state: GameState,
        element: Element,
        pid: Pid,
        char_id: None | int = None,
) -> GameState:
    """
    Apply elemental aura to the target character.
    If char_id is None (by default), then active character of pid is targeted.
    """
    if char_id is None:
        target = StaticTarget.from_player_active(game_state, pid)
    else:
        target = StaticTarget.from_char_id(pid, char_id)
    return auto_step(
        ApplyElementalAuraEffect(
            source=target,
            target=target,
            element=element,
            source_type=DamageType(status=True),
        ).execute(game_state)
    )


def auto_step(game_state: GameState, observe: bool = False) -> GameState:
    """ Step the game state until a player action is required. """
    gsm = GameStateMachine(game_state, PuppetAgent(), PuppetAgent())
    if not observe:
        gsm.auto_step()
    else:  # pragma: no cover
        while gsm.get_game_state().waiting_for() is None:
            gsm.one_step()
            print(GamePrinter.dict_game_printer(gsm.get_game_state().dict_str()))
            input(":> ")
    return gsm.get_game_state()


def fill_energy_for_all(game_state: GameState) -> GameState:
    return game_state.factory().f_player1(
        lambda p1: p1.factory().f_characters(
            lambda cs: cs.factory().f_characters(
                lambda chars: tuple(
                    char.factory().energy(char.get_max_energy()).build()
                    for char in chars
                )
            ).build()
        ).build()
    ).f_player2(
        lambda p2: p2.factory().f_characters(
            lambda cs: cs.factory().f_characters(
                lambda chars: tuple(
                    char.factory().energy(char.get_max_energy()).build()
                    for char in chars
                )
            ).build()
        ).build()
    ).build()


def fill_dice_with_omni(game_state: GameState) -> GameState:
    dice = {
        Element.OMNI: BIG_INT,
        Element.PYRO: BIG_INT,
        Element.HYDRO: BIG_INT,
        Element.ANEMO: BIG_INT,
        Element.ELECTRO: BIG_INT,
        Element.DENDRO: BIG_INT,
        Element.CRYO: BIG_INT,
        Element.GEO: BIG_INT,
    }
    return game_state.factory().f_player1(
        lambda p: p.factory().dice(ActualDice(dice)).build()
    ).f_player2(
        lambda p: p.factory().dice(ActualDice(dice)).build()
    ).build()


def full_action_step(game_state: GameState, observe: bool = False) -> GameState:
    gsm = GameStateMachine(game_state, PuppetAgent(), PuppetAgent())
    gsm.player_step(observe=observe)
    gsm.auto_step(observe=observe)
    return gsm.get_game_state()


def get_dmg_listener_data(game_state: GameState, pid: Pid) -> tuple[SpecificDamageEffect, ...]:
    hidden_statuses = game_state.get_player(pid).get_hidden_statuses()
    assert _TempTestDmgListenerStatus in hidden_statuses
    listener = hidden_statuses.just_find(_TempTestDmgListenerStatus)
    return listener.dmgs


def grant_all_infinite_revival(game_state: GameState) -> GameState:
    """
    Gives all alive characters a hidden character revival status,
    that can revive the attached character infinite times.
    """
    for pid in (Pid.P1, Pid.P2):
        alive_chars = game_state.get_player(pid).get_characters().get_alive_characters()
        for char in alive_chars:
            game_state = AddCharacterStatusEffect(
                target=StaticTarget.from_char_id(pid, char.get_id()),
                status=_TempTestInfiniteRevivalStatus,
            ).execute(game_state)
    return game_state


def grant_all_thick_shield(game_state: GameState) -> GameState:
    """
    Gives all alive characters a character status of StackedShield,
    that can be assumed to abosrb all reasonable damages in the entire game.
    (except PIERCING damage of course)
    """
    for pid in (Pid.P1, Pid.P2):
        alive_chars = game_state.get_player(pid).get_characters().get_alive_characters()
        for char in alive_chars:
            game_state = AddCharacterStatusEffect(
                target=StaticTarget.from_char_id(pid, char.get_id()),
                status=_TempTestThickShieldStatus,
            ).execute(game_state)
    return game_state


def heal_for_all(game_state: GameState) -> GameState:
    """ only heals the alive characters """
    def heal_player(player: PlayerState) -> PlayerState:
        return player.factory().f_characters(
            lambda cs: cs.factory().f_characters(
                lambda chars: tuple(
                    char.factory().hp(char.get_max_hp() if char.alive() else 0).build()
                    for char in chars
                )
            ).build()
        ).build()

    return game_state.factory().f_player1(heal_player).f_player2(heal_player).build()


def kill_character(
        game_state: GameState,
        character_id: int,
        pid: Pid = Pid.P2,
        hp: int = 0,
) -> GameState:
    """
    Sets Player2's active character's hp to `hp` (default=0)
    """
    return game_state.factory().f_player(
        pid,
        lambda p: p.factory().f_characters(
            lambda cs: cs.factory().f_character(
                character_id,
                lambda c: c.factory().hp(hp).alive(hp > 0).build()
            ).build()
        ).build()
    ).build()


def next_round(game_state: GameState, observe: bool = False) -> GameState:
    gsm = GameStateMachine(game_state, LazyAgent(), LazyAgent())
    gsm.step_until_phase(game_state.get_mode().end_phase, observe=observe)
    gsm.step_until_phase(game_state.get_mode().action_phase, observe=observe)
    gsm.auto_step(observe=observe)
    return gsm.get_game_state()


def next_round_with_great_omni(game_state: GameState, observe: bool = False) -> GameState:
    """ skips to next round and fill players with even number of dice """
    game_state = next_round(game_state, observe)
    return fill_dice_with_omni(game_state)


def oppo_aura_elem(game_state: GameState, elem: Element, char_id: None | int = None) -> GameState:
    """
    DEPRECATED, don't use for further tests.

    Gives Player2's active character `elem` aura
    """
    if char_id is None:
        return game_state.factory().f_player2(
            lambda p: p.factory().f_characters(
                lambda cs: cs.factory().f_active_character(
                    lambda ac: ac.factory().elemental_aura(
                        ElementalAura.from_default().add(elem)
                    ).build()
                ).build()
            ).build()
        ).build()
    else:
        return game_state.factory().f_player2(
            lambda p: p.factory().f_characters(
                lambda cs: cs.factory().f_character(
                    char_id,  # type: ignore
                    lambda ac: ac.factory().elemental_aura(
                        ElementalAura.from_default().add(elem)
                    ).build()
                ).build()
            ).build()
        ).build()


def remove_all_infinite_revival(game_state: GameState) -> GameState:
    """
    Removes the infinite revival statuses granted.
    """
    for pid in (Pid.P1, Pid.P2):
        alive_chars = game_state.get_player(pid).get_characters().get_alive_characters()
        for char in alive_chars:
            game_state = RemoveCharacterStatusEffect(
                target=StaticTarget.from_char_id(pid, char.get_id()),
                status=_TempTestInfiniteRevivalStatus,
            ).execute(game_state)
    return game_state


def remove_all_thick_shield(game_state: GameState) -> GameState:
    """
    Removes the thick shields generated by grant_all_thick_shield()
    """
    for pid in (Pid.P1, Pid.P2):
        alive_chars = game_state.get_player(pid).get_characters().get_alive_characters()
        for char in alive_chars:
            game_state = RemoveCharacterStatusEffect(
                target=StaticTarget.from_char_id(pid, char.get_id()),
                status=_TempTestThickShieldStatus,
            ).execute(game_state)
    return game_state


def remove_aura(game_state: GameState, pid: Pid = Pid.P2, char_id: None | int = None) -> GameState:
    return game_state.factory().f_player(
        pid,
        lambda p: p.factory().f_characters(
            lambda cs: cs.factory().f_character(
                case_val(char_id is None, cs.just_get_active_character_id(), char_id),  # type: ignore
                lambda c: c.factory().elemental_aura(ElementalAura.from_default()).build()
            ).build()
        ).build()
    ).build()


def remove_dmg_listener(game_state: GameState, pid: Pid) -> GameState:
    return RemoveHiddenStatusEffect(
        pid,
        status=_TempTestDmgListenerStatus,
    ).execute(game_state)


def replace_hand_cards(game_state: GameState, pid: Pid, cards: Cards) -> GameState:
    return game_state.factory().f_player(
        pid,
        lambda p: p.factory().hand_cards(cards).build()
    ).build()


def replace_character(
        game_state: GameState,
        pid: Pid,
        char: type[Character],
        char_id: int,
) -> GameState:
    character_instance = char.from_default(char_id).factory().hp(0).alive(False).build()
    game_state = game_state.factory().f_player(
        pid,
        lambda p: p.factory().f_characters(
            lambda cs: cs.factory().character(
                character_instance
            ).build()
        ).build()
    ).build()
    game_state = ReviveRecoverHPEffect(
        target=StaticTarget.from_char_id(pid, char_id),
        recovery=character_instance.get_max_hp(),
    ).execute(game_state)
    return auto_step(game_state)


def replace_character_make_active_add_card(
        game_state: GameState,
        pid: Pid,
        char: type[Character],
        char_id: int,
        card: type[Card],
) -> GameState:
    return replace_character(game_state, pid, char, char_id).factory().f_player(
        pid,
        lambda p: p.factory().f_characters(
            lambda cs: cs.factory().active_character_id(
                char_id
            ).build()
        ).f_hand_cards(
            lambda hcs: hcs.add(card).add(card)
        ).build()
    ).build()


def replace_dice(game_state: GameState, pid: Pid, dice: ActualDice) -> GameState:
    return game_state.factory().f_player(
        pid,
        lambda p: p.factory().dice(dice).build()
    ).build()


def set_active_player_id(game_state: GameState, pid: Pid, character_id: int) -> GameState:
    return game_state.factory().f_player(
        pid,
        lambda p: p.factory().f_characters(
            lambda cs: cs.factory().active_character_id(character_id).build()
        ).build()
    ).build()


def silent_fast_swap(game_state: GameState, pid: Pid, char_id: int) -> GameState:
    return game_state.factory().f_player(
        pid,
        lambda p: p.factory().f_characters(
            lambda cs: cs.factory().active_character_id(char_id).build()
        ).build()
    ).build()


def simulate_status_dmg(
        game_state: GameState,
        dmg_amount: int,
        element: Element = Element.PIERCING,
        pid: Pid = Pid.P2,
        char_id: None | int = None,
        observe: bool = False,
) -> GameState:
    """
    Simulate a damage from a test-only, one-time status that is on the target character.
    The damage is of type "no_boost".
    """
    target = (
        StaticTarget.from_player_active(game_state, pid)
        if char_id is None
        else StaticTarget.from_char_id(pid, char_id)
    )
    game_state = UpdateCharacterStatusEffect(
        target=target,
        status=_TempTestStatus(
            dmg=dmg_amount,
            elem=element,
            target=target,
        ),
    ).execute(game_state)
    game_state = game_state.factory().f_effect_stack(
        lambda es: es.push_one(TriggerStatusEffect(
            target=target,
            status=_TempTestStatus,
            signal=TriggeringSignal.GAME_START,
        ))
    ).build()
    return auto_step(game_state, observe=observe)


def skip_action_round(game_state: GameState, pid: Pid) -> GameState:
    """ pid is the player that is skipped """
    assert pid is game_state.waiting_for()
    return auto_step(TurnEndEffect().execute(game_state))


def skip_action_round_until(game_state: GameState, pid: Pid) -> GameState:
    """ pid is the player that is skipped """
    while pid is not game_state.waiting_for():
        game_state = skip_action_round(game_state, just(game_state.waiting_for()))
    return game_state


def step_action(
        game_state: GameState,
        pid: Pid,
        player_action: PlayerAction,
        observe: bool = False
) -> GameState:
    game_state = just(game_state.action_step(pid, player_action))
    return auto_step(game_state, observe=observe)


def step_skill(
        game_state: GameState,
        pid: Pid,
        skill: CharacterSkill,
        dice: None | ActualDice = None,
        observe: bool = False,
) -> GameState:
    active_character = game_state.get_player(pid).just_get_active_character()
    if dice is None:
        dice_used = ActualDice({Element.OMNI: active_character.skill_cost(skill).num_dice()})
    else:
        dice_used = dice
    player_action = SkillAction(
        skill=skill,
        instruction=DiceOnlyInstruction(dice=dice_used)
    )
    return step_action(game_state, pid, player_action, observe=observe)


def step_swap(
        game_state: GameState,
        pid: Pid,
        char_id: int,
        cost: int = 1,
        observe: bool = False,
) -> GameState:
    player_action = SwapAction(
        char_id=char_id,
        instruction=DiceOnlyInstruction(
            dice=ActualDice({Element.OMNI: cost})
        )
    )
    return step_action(game_state, pid, player_action, observe=observe)


def step_until_phase(game_state: GameState, phase: type[Phase], observe: bool = False) -> GameState:
    """ If game state is already in the `phase` then skip until the next one. """
    gsm = GameStateMachine(game_state, LazyAgent(), LazyAgent())
    gsm.step_until_phase(phase, observe=observe)
    return gsm.get_game_state()


def step_until_signal(game_state: GameState, signal: TriggeringSignal, observe: bool = False) -> GameState:
    """ Step until the next effect is trigger all statuses with `signal` """
    gsm = GameStateMachine(game_state, LazyAgent(), LazyAgent())
    gsm.step_until_holds(lambda gs: (
        gs.get_effect_stack().is_not_empty()
        and (
            gs.get_effect_stack().peek() == AllStatusTriggererEffect(Pid.P1, signal)
            or gs.get_effect_stack().peek() == AllStatusTriggererEffect(Pid.P2, signal)
        )
    ), observe=observe)
    return gsm.get_game_state()


def use_elemental_aura(
        game_state: GameState,
        element: None | Element,
        pid: Pid,
        char_id: None | int = None,
) -> GameState:
    """ Replace elemental aura of the target character """
    if char_id is None:
        target = StaticTarget.from_player_active(game_state, pid)
    else:
        target = StaticTarget.from_char_id(pid, char_id)
    aura = ElementalAura.from_default()
    if element is not None:
        aura = aura.add(element)
    return game_state.factory().f_player(
        target.pid,
        lambda p: p.factory().f_characters(
            lambda cs: cs.factory().f_character(
                cast(int, target.id),
                lambda c: c.factory().elemental_aura(aura).build()
            ).build()
        ).build()
    ).build()
