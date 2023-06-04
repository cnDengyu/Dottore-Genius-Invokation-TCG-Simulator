from __future__ import annotations
from typing import FrozenSet, Optional, cast, Union, ClassVar, Iterable, Callable
from enum import Enum
from dataclasses import InitVar, dataclass, asdict, replace
from itertools import chain

import dgisim.src.status.status as stt
from dgisim.src.element.element import Element, Reaction, ReactionDetail
import dgisim.src.character.character as char
import dgisim.src.state.game_state as gs
import dgisim.src.state.player_state as ps
import dgisim.src.card.card as cd
import dgisim.src.dices as ds
from dgisim.src.helper.quality_of_life import just


class Zone(Enum):
    CHARACTER = 0
    SUMMONS = 1
    SUPPORT = 2
    # HAND = 3
    # EFFECT = 4


class TriggeringSignal(Enum):
    FAST_ACTION = 0
    COMBAT_ACTION = 1
    DEATH_EVENT = 2
    SWAP_EVENT = 3
    ROUND_START = 4
    END_ROUND_CHECK_OUT = 5
    ROUND_END = 6


class DynamicCharacterTarget(Enum):
    SELF_SELF = 0
    SELF_ACTIVE = 1
    SELF_OFF_FIELD = 2
    SELF_ALL = 3
    SELF_ABS = 4
    OPPO_ACTIVE = 5
    OPPO_OFF_FIELD = 6


@dataclass(frozen=True)
class StaticTarget:
    pid: gs.GameState.Pid
    zone: Zone
    id: int


@dataclass(frozen=True)
class Effect:
    def execute(self, game_state: gs.GameState) -> gs.GameState:
        raise Exception("Not Overriden or Implemented")

    def name(self) -> str:
        return self.__class__.__name__

    def dict_str(self) -> Union[dict, str]:
        return asdict(self)

    def __str__(self) -> str:
        return self.__class__.__name__


@dataclass(frozen=True)
class TriggerrbleEffect(Effect):
    pass


@dataclass(frozen=True)
class DirectEffect(Effect):
    pass


@dataclass(frozen=True)
class CheckerEffect(Effect):
    pass


@dataclass(frozen=True)
class PhaseEffect(Effect):
    pass


@dataclass(frozen=True)
class TriggerStatusEffect(Effect):
    target: StaticTarget
    status: type[stt.Status]
    signal: TriggeringSignal

    def execute(self, game_state: gs.GameState) -> gs.GameState:
        character = game_state.get_target(self.target)
        if not isinstance(character, char.Character):
            return game_state
        character = cast(char.Character, character)
        effects: Iterable[Effect] = []

        if issubclass(self.status, stt.CharacterTalentStatus):
            # TODO
            pass
        elif issubclass(self.status, stt.EquipmentStatus):
            # TODO
            pass
        elif issubclass(self.status, stt.CharacterStatus):
            statuses = character.get_character_statuses()
            status = statuses.find(self.status)
            if status is None:
                return game_state
            effects = status.react_to_signal(self.target, self.signal)
        else:
            raise Exception("Unexpected Status Type to Trigger", self.status)
        return game_state.factory().f_effect_stack(
            lambda es: es.push_many_fl(effects)
        ).build()


def _loopAllStatuses(
        game_state: gs.GameState,
        pid: gs.GameState.Pid,
        f: Callable[[gs.GameState, stt.Status, StaticTarget], gs.GameState]
) -> gs.GameState:
    """
    Perform f on all statuses of player pid in order
    """
    player = game_state.get_player(pid)

    # characters first
    characters = player.get_characters()
    ordered_characters = characters.get_character_in_activity_order()
    for character in ordered_characters:
        # get character's private statuses and add triggerStatusEffect to global effect_stack
        statuses = character.get_all_statuses_ordered_flattened()
        character_id = character.get_id()
        target = StaticTarget(
            pid,
            Zone.CHARACTER,
            character_id
        )
        for status in statuses:
            game_state = f(game_state, status, target)

    # combat status TODO
    # summons TODO
    # supports TODO

    return game_state


def _triggerAllStatusesEffects(
        game_state: gs.GameState, pid: gs.GameState.Pid, signal: TriggeringSignal
) -> list[Effect]:
    """
    Takes the current game_state, trigger all statuses in order of player pid
    Returns the triggering effects in order (first to last)
    """
    effects: list[Effect] = []

    def f(game_state: gs.GameState, status: stt.Status, target: StaticTarget) -> gs.GameState:
        nonlocal effects
        effects.append(TriggerStatusEffect(target, type(status), signal))
        return game_state

    _loopAllStatuses(game_state, pid, f)
    return effects


def _preprocessByAllStatuses(
        game_state: gs.GameState,
        pid: gs.GameState.Pid,
        item: Preprocessable,
        pp_type: stt.Status.PPType,
) -> tuple[gs.GameState, Preprocessable]:
    def f(game_state: gs.GameState, status: stt.Status, target: StaticTarget) -> gs.GameState:
        nonlocal item
        item, new_status = status.preprocess(item, pp_type)
        if new_status == status:
            game_state = UpdateStatusEffect(target, new_status).execute(game_state)
        return game_state

    game_state = _loopAllStatuses(game_state, pid, f)
    return game_state, item


@dataclass(frozen=True)
class AllStatusTriggererEffect(TriggerrbleEffect):
    """
    This effect triggers the characters' statuses with the provided signal in order.
    """
    pid: gs.GameState.Pid
    signal: TriggeringSignal

    def execute(self, game_state: gs.GameState) -> gs.GameState:
        effects = _triggerAllStatusesEffects(game_state, self.pid, self.signal)
        return game_state.factory().f_effect_stack(
            lambda es: es.push_many_fl(effects)
        ).build()


@dataclass(frozen=True)
class SwapCharacterCheckerEffect(CheckerEffect):
    pass


@dataclass(frozen=True)
class DeathCheckCheckerEffect(CheckerEffect):
    def execute(self, game_state: gs.GameState) -> gs.GameState:
        # return game_state
        p1_character = game_state.get_player1().get_characters().get_active_character()
        p2_character = game_state.get_player2().get_characters().get_active_character()
        assert p1_character is not None and p2_character is not None
        pid: gs.GameState.Pid
        if p1_character.defeated():
            pid = gs.GameState.Pid.P1
        elif p2_character.defeated():
            pid = gs.GameState.Pid.P2
        else:  # if no one defeated, continue
            return game_state
        death_swap_player = game_state.get_player(pid)
        waiting_player = game_state.get_other_player(pid)
        # TODO: check if game ends
        if death_swap_player.defeated():
            return game_state.factory().phase(game_state.get_mode().game_end_phase()).build()
        effects: list[Effect] = []
        # TODO: trigger other death based effects
        effects.append(DeathSwapPhaseStartEffect())
        effects.append(DeathSwapPhaseEndEffect(
            pid,
            death_swap_player.get_phase(),
            waiting_player.get_phase(),
        ))
        return game_state.factory().effect_stack(
            game_state.get_effect_stack().push_many_fl(tuple(effects))
        ).player(
            pid,
            game_state.get_player(pid).factory().phase(
                ps.PlayerState.Act.ACTION_PHASE
            ).build()
        ).other_player(
            pid,
            game_state.get_other_player(pid).factory().phase(
                ps.PlayerState.Act.PASSIVE_WAIT_PHASE
            ).build()
        ).build()
    pass


@dataclass(frozen=True)
class DeathSwapPhaseStartEffect(PhaseEffect):
    pass


@dataclass(frozen=True)
class DeathSwapPhaseEndEffect(PhaseEffect):
    my_pid: gs.GameState.Pid
    my_last_phase: ps.PlayerState.Act
    other_last_phase: ps.PlayerState.Act

    def execute(self, game_state: gs.GameState) -> gs.GameState:
        player = game_state.get_player(self.my_pid)
        other_player = game_state.get_other_player(self.my_pid)
        player = player.factory().phase(self.my_last_phase).build()
        other_player = other_player.factory().phase(self.other_last_phase).build()
        return game_state.factory().player(
            self.my_pid,
            player
        ).other_player(
            self.my_pid,
            other_player
        ).build()


@dataclass(frozen=True)
class EndPhaseCheckoutEffect(PhaseEffect):
    """
    This is responsible for triggering character statuses/summons/supports by the
    end of the round.
    """

    def execute(self, game_state: gs.GameState) -> gs.GameState:
        active_id = game_state.get_active_player_id()
        # active_player = game_state.get_player(active_id)
        effects = [
            AllStatusTriggererEffect(
                active_id,
                TriggeringSignal.END_ROUND_CHECK_OUT
            ),
            # TODO: add active_player's team status, summons status... here
            AllStatusTriggererEffect(
                active_id.other(),
                TriggeringSignal.END_ROUND_CHECK_OUT
            ),
            # TODO: add active_player's team status, summons status... here
        ]
        return game_state.factory().f_effect_stack(
            lambda es: es.push_many_fl(effects)
        ).build()


@dataclass(frozen=True)
class EndRoundEffect(PhaseEffect):
    """
    This is responsible for triggering other clean ups (e.g. remove satiated)
    """

    def execute(self, game_state: gs.GameState) -> gs.GameState:
        active_id = game_state.get_active_player_id()
        active_player = game_state.get_player(active_id)
        effects = [
            AllStatusTriggererEffect(
                active_id,
                TriggeringSignal.ROUND_END
            ),
            # TODO: add active_player's team status, summons status... here
            AllStatusTriggererEffect(
                active_id.other(),
                TriggeringSignal.ROUND_END
            ),
            # TODO: add active_player's team status, summons status... here
        ]
        return game_state.factory().f_effect_stack(
            lambda es: es.push_many_fl(effects)
        ).build()


@dataclass(frozen=True)
class TurnEndEffect(PhaseEffect):
    def execute(self, game_state: gs.GameState) -> gs.GameState:
        active_player_id = game_state.get_active_player_id()
        player = game_state.get_player(active_player_id)
        other_player = game_state.get_other_player(active_player_id)
        assert player.get_phase() is ps.PlayerState.Act.ACTION_PHASE
        # TODO: other tidy up
        if other_player.get_phase() is ps.PlayerState.Act.END_PHASE:
            return game_state
        return game_state.factory().active_player(
            active_player_id.other()
        ).player(
            active_player_id,
            player.factory().phase(ps.PlayerState.Act.PASSIVE_WAIT_PHASE).build()
        ).other_player(
            active_player_id,
            other_player.factory().phase(ps.PlayerState.Act.ACTION_PHASE).build()
        ).build()


@dataclass(frozen=True)
class EndPhaseTurnEndEffect(PhaseEffect):
    def execute(self, game_state: gs.GameState) -> gs.GameState:
        active_player_id = game_state.get_active_player_id()
        player = game_state.get_player(active_player_id)
        other_player = game_state.get_other_player(active_player_id)
        assert player.get_phase() is ps.PlayerState.Act.ACTIVE_WAIT_PHASE
        return game_state.factory().active_player(
            active_player_id.other()
        ).player(
            active_player_id,
            player.factory().phase(ps.PlayerState.Act.PASSIVE_WAIT_PHASE).build()
        ).other_player(
            active_player_id,
            other_player.factory().phase(ps.PlayerState.Act.ACTIVE_WAIT_PHASE).build()
        ).build()


@dataclass(frozen=True)
class SetBothPlayerPhaseEffect(PhaseEffect):
    phase: ps.PlayerState.Act

    def execute(self, game_state: gs.GameState) -> gs.GameState:
        return game_state.factory().f_player1(
            lambda p: p.factory().phase(self.phase).build()
        ).f_player2(
            lambda p: p.factory().phase(self.phase).build()
        ).build()


@dataclass(frozen=True)
class RemoveCharacterStatusEffect(DirectEffect):
    target: StaticTarget
    status: type[stt.Status]

    def execute(self, game_state: gs.GameState) -> gs.GameState:
        character = game_state.get_character_target(self.target)
        if character is None:
            return game_state
        new_character = character
        if issubclass(self.status, stt.CharacterTalentStatus):
            pass
        elif issubclass(self.status, stt.EquipmentStatus):
            pass
        elif issubclass(self.status, stt.CharacterStatus):
            statuses = character.get_character_statuses()
            new_statuses = statuses.remove(self.status)
            new_character = new_character.factory().character_statuses(new_statuses).build()
        return game_state.factory().f_player(
            self.target.pid,
            lambda p: p.factory().f_characters(
                lambda cs: cs.factory().character(new_character).build()
            ).build()
        ).build()


@dataclass(frozen=True)
class SwapCharacterEffect(DirectEffect):
    source: StaticTarget
    target: StaticTarget

    def execute(self, game_state: gs.GameState) -> gs.GameState:
        assert self.source.pid == self.target.pid \
            and self.source.zone == Zone.CHARACTER \
            and self.target.zone == Zone.CHARACTER \
            and self.source.id != self.target.id
        pid = self.source.pid
        player = game_state.get_player(pid)
        characters = player.get_characters()
        characters = characters.factory().active_character_id(self.target.id).build()
        player = player.factory().characters(characters).build()
        # TODO: Trigger swap event
        return game_state.factory().player(pid, player).build()


@dataclass(frozen=True)
class DamageEffect(Effect):
    source: StaticTarget
    target: DynamicCharacterTarget
    element: Element
    damage: int
    reaction: Optional[ReactionDetail] = None

    _DAMAGE_ELEMENTS: ClassVar[FrozenSet[Element]] = frozenset({
        Element.PYRO,
        Element.HYDRO,
        Element.ANEMO,
        Element.ELECTRO,
        Element.DENDRO,
        Element.CRYO,
        Element.GEO,
        Element.PHYSICAL,
        Element.PIERCING,
    })

    def legal(self) -> bool:
        return self.element in self._DAMAGE_ELEMENTS

    @staticmethod
    def _get_opponent(game_state: gs.GameState, damage: DamageEffect) -> Optional[char.Character]:
        if damage.target is DynamicCharacterTarget.OPPO_ACTIVE:
            return game_state.get_other_player(
                damage.source.pid
            ).get_characters().get_active_character()
        else:
            raise Exception("Not implemented yet")

    @staticmethod
    def _damage_preprocess(
            game_state: gs.GameState, damage: DamageEffect, pp_type: stt.Status.PPType
    ) -> tuple[gs.GameState, DamageEffect]:
        source_id = damage.source.pid
        game_state, item = _preprocessByAllStatuses(game_state, source_id, damage, pp_type)
        game_state, item = _preprocessByAllStatuses(game_state, source_id.other(), damage, pp_type)
        assert type(item) == DamageEffect
        damage = item
        return game_state, damage

    @classmethod
    def _element_confirmation(
            cls, game_state: gs.GameState, damage: DamageEffect
    ) -> tuple[gs.GameState, DamageEffect]:
        return cls._damage_preprocess(game_state, damage, stt.Status.PPType.DmgElement)

    @classmethod
    def _reaction_confirmation(
            cls, game_state: gs.GameState, damage: DamageEffect
    ) -> tuple[gs.GameState, DamageEffect, Optional[ReactionDetail]]:
        target_char = cls._get_opponent(game_state, damage)
        assert target_char is not None

        # try to identify the reaction
        second_elem = damage.element
        all_aura = target_char.get_elemental_aura()
        reaction: Optional[Reaction] = None
        reactionDetail: Optional[ReactionDetail] = None
        first_elem: Optional[Element] = None
        for first_elem in all_aura:
            reaction = Reaction.consult_reaction(first_elem, second_elem)
            if reaction is not None:
                break

        # generate & update new aura
        new_aura = all_aura
        if reaction is not None:
            assert first_elem is not None
            new_aura.remove(first_elem)
            reactionDetail = ReactionDetail(reaction, first_elem, second_elem)
            damage = replace(damage, reaction=reactionDetail)
        elif new_aura.aurable(second_elem):
            new_aura.add(second_elem)

        if new_aura != all_aura:
            game_state = game_state.factory().f_player(
                just(game_state.belongs_to(target_char)),
                lambda p: p.factory().f_characters(
                    lambda cs: cs.factory().character(
                        target_char.factory().elemental_aura(new_aura).build()
                    ).build()
                ).build()
            ).build()

        game_state, damage = cls._damage_preprocess(
            game_state, damage, stt.Status.PPType.DmgReaction
        )
        return game_state, damage, reactionDetail

    @classmethod
    def _damage_confirmation(
            cls, game_state: gs.GameState, damage: DamageEffect
    ) -> tuple[gs.GameState, DamageEffect]:
        return cls._damage_preprocess(game_state, damage, stt.Status.PPType.DmgAmount)

    def execute(self, game_state: gs.GameState) -> gs.GameState:
        pid = self.source.pid
        from dgisim.src.character.character import Character
        # Get damage target
        opponent = self._get_opponent(game_state, self)
        if opponent is None:
            return game_state
        game_state, elemented_damage = self._element_confirmation(game_state, self)
        game_state, reactioned_damage, reaction = self._reaction_confirmation(
            game_state, elemented_damage)
        game_state, actual_damage = self._damage_confirmation(game_state, reactioned_damage)
        # Damage Calculation
        hp = opponent.get_hp()
        hp = max(0, hp - actual_damage.damage)

        # LATESET_TODO: use the reaction information to generate further effects

        opponent = opponent.factory().hp(hp).build()
        other_player = game_state.get_other_player(pid)
        other_characters = other_player.get_characters().factory().character(opponent).build()
        other_player = other_player.factory().characters(other_characters).build()
        return game_state.factory().other_player(pid, other_player).build()


@dataclass(frozen=True)
class EnergyRechargeEffect(Effect):
    target: StaticTarget
    recharge: int

    def execute(self, game_state: gs.GameState) -> gs.GameState:
        character = game_state.get_target(self.target)
        if not isinstance(character, char.Character):
            return game_state
        character = cast(char.Character, character)
        energy = min(character.get_energy() + self.recharge, character.get_max_energy())
        if energy == character.get_energy():
            return game_state
        character = character.factory().energy(energy).build()
        player = game_state.get_player(self.target.pid)
        characters = player.get_characters().factory().character(character).build()
        player = player.factory().characters(characters).build()
        return game_state.factory().player(
            self.target.pid,
            player
        ).build()
    
@dataclass(frozen=True)
class EnergyDrainEffect(Effect):
    target: StaticTarget
    drain: int
    
    def execute(self, game_state: gs.GameState) -> gs.GameState:
        character = game_state.get_target(self.target)
        if not isinstance(character, char.Character):
            return game_state
        character = cast(char.Character, character)
        energy = max(character.get_energy() - self.drain, 0)
        if energy == character.get_energy():
            return game_state
        character = character.factory().energy(energy).build()
        player = game_state.get_player(self.target.pid)
        characters = player.get_characters().factory().character(character).build()
        player = player.factory().characters(characters).build()
        return game_state.factory().player(
            self.target.pid,
            player
        ).build()


@dataclass(frozen=True)
class RecoverHPEffect(Effect):
    target: StaticTarget
    recovery: int

    def execute(self, game_state: gs.GameState) -> gs.GameState:
        character = game_state.get_target(self.target)
        if not isinstance(character, char.Character):
            return game_state
        character = cast(char.Character, character)
        hp = min(character.get_hp() + self.recovery, character.get_max_hp())
        if hp == character.get_hp():
            return game_state
        return game_state.factory().f_player(
            self.target.pid,
            lambda p: p.factory().f_characters(
                lambda cs: cs.factory().f_character(
                    character.get_id(),
                    lambda c: c.factory().hp(hp).build()
                ).build()
            ).build()
        ).build()


@dataclass(frozen=True)
class RemoveCardEffect(Effect):
    pid: gs.GameState.Pid
    card: type[cd.Card]

    def execute(self, game_state: gs.GameState) -> gs.GameState:
        pid = self.pid
        card = self.card
        hand_cards = game_state.get_player(pid).get_hand_cards()
        if not hand_cards.contains(card) or hand_cards[card] <= 0:
            return game_state
        return game_state.factory().f_player(
            pid,
            lambda p: p.factory().f_hand_cards(
                lambda cs: cs.remove(card)
            ).build()
        ).build()


@dataclass(frozen=True)
class RemoveDiceEffect(Effect):
    pid: gs.GameState.Pid
    dices: ds.ActualDices

    def execute(self, game_state: gs.GameState) -> gs.GameState:
        pid = self.pid
        dices = self.dices
        new_dices = game_state.get_player(pid).get_dices() - dices
        if not new_dices.is_legal():
            raise Exception("Not enough dices for this effect")
        return game_state.factory().f_player(
            pid,
            lambda p: p.factory().dices(new_dices).build()
        ).build()


@dataclass(frozen=True)
class AddStatusEffect(Effect):
    target: StaticTarget
    status: type[stt.Status]

    def execute(self, game_state: gs.GameState) -> gs.GameState:
        character = game_state.get_target(self.target)
        assert isinstance(character, char.Character)
        if issubclass(self.status, stt.CharacterTalentStatus):
            pass
        elif issubclass(self.status, stt.EquipmentStatus):
            pass
        elif issubclass(self.status, stt.CharacterStatus):
            character = character.factory().f_character_statuses(
                lambda bs: bs.update_statuses(self.status())
            ).build()
        return game_state.factory().f_player(
            self.target.pid,
            lambda p: p.factory().f_characters(
                lambda cs: cs.factory().character(character).build()
            ).build()
        ).build()


@dataclass(frozen=True)
class UpdateStatusEffect(Effect):
    target: StaticTarget
    status: stt.Status

    def execute(self, game_state: gs.GameState) -> gs.GameState:
        character = game_state.get_target(self.target)
        assert isinstance(character, char.Character)
        if isinstance(self.status, stt.CharacterTalentStatus):
            pass
        elif isinstance(self.status, stt.EquipmentStatus):
            pass
        elif isinstance(self.status, stt.CharacterStatus):
            character = character.factory().f_character_statuses(
                lambda bs: bs.update_statuses(self.status)
            ).build()
        return game_state.factory().f_player(
            self.target.pid,
            lambda p: p.factory().f_characters(
                lambda cs: cs.factory().character(character).build()
            ).build()
        ).build()


@dataclass(frozen=True)
class AddCardEffect(Effect):
    target: StaticTarget
    card: type[cd.Card]

    def execute(self, game_state: gs.GameState) -> gs.GameState:
        # TODO: add card
        return super().execute(game_state)


# This has to be by the end of the file or there's cyclic import error
Preprocessable = Union[DamageEffect, int]