from __future__ import annotations
import random
from collections import Counter
from functools import lru_cache
from typing import Any, Optional, Iterator, Iterable

from typing_extensions import Self, override, TYPE_CHECKING

from .helper.hashable_dict import HashableDict
from .helper.quality_of_life import BIG_INT, case_val
from .element import Element

if TYPE_CHECKING:
    from .state.game_state import GameState
    from .state.player_state import PlayerState

__all__ = [
    "AbstractDice",
    "ActualDice",
    "Dice",
]


class Dice:
    """
    Base class for dice
    """
    _LEGAL_ELEMS = frozenset(elem for elem in Element)

    def __init__(self, dice: dict[Element, int]) -> None:
        self._dice = HashableDict.from_dict(dice)

    def __add__(self, other: Dice | dict[Element, int]) -> Self:
        dice: dict[Element, int]
        if isinstance(other, Dice):
            dice = other._dice
        else:
            dice = other
        return type(self)(self._dice + dice)

    def __sub__(self, other: Dice | dict[Element, int]) -> Self:
        dice: dict[Element, int]
        if isinstance(other, Dice):
            dice = other._dice
        else:
            dice = other
        return type(self)(self._dice - dice)

    def num_dice(self) -> int:
        return sum(self._dice.values())

    def is_even(self) -> bool:
        return self.num_dice() % 2 == 0

    def is_empty(self) -> bool:
        return not any(val > 0 for val in self._dice.values())

    def is_legal(self) -> bool:
        return all(map(lambda x: x >= 0, self._dice.values())) \
            and all(elem in self._LEGAL_ELEMS for elem in self._dice)

    def validify(self) -> Self:
        if self.is_legal():
            return self
        return type(self)(dict(
            (elem, n)
            for elem, n in self._dice.items()
            if elem in self._LEGAL_ELEMS and n > 0
        ))

    def elems(self) -> Iterable[Element]:
        return self._dice.keys()

    def pick_random_dice(self, num: int) -> tuple[Self, Self]:
        """
        Returns the left dice and selected dice
        """
        num = min(self.num_dice(), num)
        if num == 0:
            return (self, type(self).from_empty())
        picked_dice: dict[Element, int] = HashableDict(Counter(
            random.sample(list(self._dice.keys()), counts=self._dice.values(), k=num)
        ))
        return type(self)(self._dice - picked_dice), type(self)(picked_dice)

    def __contains__(self, elem: Element) -> bool:
        return (
            elem in self._LEGAL_ELEMS
            and self[elem] > 0
        )

    def __iter__(self) -> Iterator[Element]:
        return (
            elem
            for elem in self._dice
            if self[elem] > 0
        )

    def __getitem__(self, index: Element) -> int:
        return self._dice.get(index, 0)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Dice):
            return False
        return self is other or self._dice == other._dice

    def __hash__(self) -> int:
        return hash(self._dice)

    def __repr__(self) -> str:
        existing_dice = dict([
            (dice.name, str(num))
            for dice, num in self._dice.items()
            if num != 0
        ])
        return (
            '{'
            + ", ".join(
                f"{key}: {val}"
                for key, val in existing_dice.items()
            )
            + '}'
        )

    def to_dict(self) -> dict[Element, int]:
        return self._dice.to_dict()

    def dict_str(self) -> dict[str, Any]:
        existing_dice = dict([
            (dice.name, str(num))
            for dice, num in self._dice.items()
            if num != 0
        ])
        return existing_dice

    def __copy__(self) -> Self:  # pragma: no cover
        return self

    def __deepcopy__(self, _) -> Self:  # pragma: no cover
        return self

    @classmethod
    def from_empty(cls) -> Self:
        return cls(HashableDict((
            (elem, 0)
            for elem in cls._LEGAL_ELEMS
        )))


_PURE_ELEMS = frozenset({
    Element.PYRO,
    Element.HYDRO,
    Element.ANEMO,
    Element.ELECTRO,
    Element.DENDRO,
    Element.CRYO,
    Element.GEO,
})


class ActualDice(Dice):
    """
    Used for the actual dice a player can have.
    """
    _LEGAL_ELEMS = frozenset({
        Element.OMNI,
        Element.PYRO,
        Element.HYDRO,
        Element.ANEMO,
        Element.ELECTRO,
        Element.DENDRO,
        Element.CRYO,
        Element.GEO,
    })

    # tested against the actual game in Genshin
    _LEGAL_ELEMS_ORDERED: tuple[Element, ...] = (
        Element.OMNI,
        Element.CRYO,
        Element.HYDRO,
        Element.PYRO,
        Element.ELECTRO,
        Element.GEO,
        Element.DENDRO,
        Element.ANEMO,
    )
    # the bigger the i, the higher the priority
    _LEGAL_ELEMS_ORDERED_DICT: dict[Element, int] = {
        elem: i
        for i, elem in enumerate(reversed(_LEGAL_ELEMS_ORDERED))
    }
    _LEGAL_ELEMS_ORDERED_DICT_REV: dict[int, Element] = {
        i: elem
        for elem, i in _LEGAL_ELEMS_ORDERED_DICT.items()
    }

    def _satisfy(self, requirement: AbstractDice) -> bool:
        assert self.is_legal() and requirement.is_legal()

        # satisfy all pure elements first
        pure_deducted: HashableDict[Element, int] = HashableDict((
            (elem, self[elem] - requirement[elem])
            for elem in _PURE_ELEMS
        ), frozen=False)
        omni_needed = sum(
            -num
            for num in pure_deducted.values()
            if num < 0
        )

        # if OMNI given cannot cover pure misses, fail
        if self[Element.OMNI] < omni_needed:
            return False

        # test OMNI requirement
        omni_remained = self[Element.OMNI] - omni_needed
        most_pure: int = max(pure_deducted.values())
        if omni_remained + most_pure < requirement[Element.OMNI]:
            return False

        # We have enough dice to satisfy Element.ANY, so success
        return True

    def loosely_satisfy(self, requirement: AbstractDice) -> bool:
        """
        Asserts self and requirement are legal, and then check if self can match
        requirement.
        """
        if self.num_dice() < requirement.num_dice():
            return False
        return self._satisfy(requirement)

    def just_satisfy(self, requirement: AbstractDice) -> bool:
        """
        Asserts self and requirement are legal, and then check if self can match
        requirement.

        self must have the same number of dice as requirement asked for.
        """
        if self.num_dice() != requirement.num_dice():
            return False
        return self._satisfy(requirement)

    def basically_satisfy(
            self,
            requirement: AbstractDice,
            game_state: Optional[GameState] = None,
    ) -> Optional[ActualDice]:
        if requirement.num_dice() > self.num_dice():
            return None
        # TODO: optimize for having game_state
        from collections import defaultdict
        remaining: dict[Element, int] = self._dice.copy()
        answer: dict[Element, int] = defaultdict(int)
        pures: dict[Element, int] = HashableDict(frozen=False)
        omni = 0
        any = 0
        omni_required = 0
        for elem in requirement:
            if elem in _PURE_ELEMS:
                pures[elem] = requirement[elem]
            elif elem is Element.OMNI:
                omni = requirement[elem]
            elif elem is Element.ANY:
                any = requirement[elem]
            else:  # pragma: no cover
                raise Exception("Unknown element")
        if len(pures) > 0:
            for elem in pures:
                if remaining.get(elem, 0) < pures[elem]:
                    answer[elem] += remaining.get(elem, 0)
                    omni_required += pures[elem] - remaining.get(elem, 0)
                    remaining[elem] = 0
                else:
                    answer[elem] += pures[elem]
                    remaining[elem] -= pures[elem]
        if omni > 0:
            best_elem: Optional[Element] = None
            best_count = 0
            for elem in list(_PURE_ELEMS):
                this_count = remaining.get(elem, 0)
                if best_count > omni and this_count >= omni and this_count < best_count:
                    best_elem = elem
                    best_count = this_count
                elif best_count < omni and this_count > best_count:
                    best_elem = elem
                    best_count = this_count
                elif best_count == omni:
                    break
            if best_elem is not None:
                best_count = min(best_count, omni)
                answer[best_elem] += best_count
                remaining[best_elem] -= best_count
                omni_required += omni - best_count
            else:
                omni_required += omni
        if any > 0:
            from operator import itemgetter
            sorted_elems = sorted(remaining.items(), key=itemgetter(1))
            for elem, num in sorted_elems:
                if elem in _PURE_ELEMS:
                    num = min(num, any)
                    answer[elem] += num
                    remaining[elem] -= num
                    any -= num
                    if any == 0:
                        break
            if any > 0:
                answer[Element.OMNI] += any
                remaining[Element.OMNI] -= any
        if omni_required > 0:
            if remaining.get(Element.OMNI, 0) < omni_required:
                return None
            answer[Element.OMNI] += omni_required
        return ActualDice(answer)

    def _init_ordered_dice(
            self,
            priority_elems: None | frozenset[Element]
    ) -> HashableDict[Element, int]:
        character_elems: frozenset[Element]
        if priority_elems is None:
            character_elems = frozenset()
        else:
            character_elems = priority_elems

        dice: dict[Element, int] = {}
        if self[Element.OMNI] > 0:
            dice[Element.OMNI] = self[Element.OMNI]
        # list[tuple[alive chars have elem, num of elem, priority of elem]]
        sorted_categories: list[tuple[int, int, int]] = sorted(
            (
                (
                    case_val(elem in character_elems, 1, 0),
                    self[elem],
                    self._LEGAL_ELEMS_ORDERED_DICT[elem],
                )
                for elem in self.elems()
                if elem is not Element.OMNI and self[elem] > 0
            ),
            reverse=True
        )
        for _, _, priority in sorted_categories:
            elem = self._LEGAL_ELEMS_ORDERED_DICT_REV[priority]
            dice[elem] = self[elem]
        return HashableDict.from_dict(dice)

    def dice_ordered(self, player_state: None | PlayerState) -> dict[Element, int]:
        return self.readonly_dice_ordered(player_state).to_dict()

    def readonly_dice_ordered(self, player_state: None | PlayerState) -> HashableDict[Element, int]:
        return self._init_ordered_dice(
            None
            if player_state is None
            else frozenset(
                char.ELEMENT()
                for char in player_state.get_characters().get_alive_characters()
            )
        )

    @classmethod
    def from_random(cls, size: int, excepted_elems: set[Element] = set()) -> ActualDice:
        dice = ActualDice.from_empty()
        dice._dice._unfreeze()
        for i in range(size):
            elem = random.choice(tuple(ActualDice._LEGAL_ELEMS - excepted_elems))
            dice._dice[elem] += 1
        dice._dice.freeze()
        return dice

    @classmethod
    def from_all(cls, size: int, elem: Element) -> ActualDice:
        dice = ActualDice.from_empty()
        dice._dice._unfreeze()
        dice._dice[Element.OMNI] = size
        dice._dice.freeze()
        return dice

    @classmethod
    def from_dice(cls, dice: Dice) -> Optional[ActualDice]:
        new_dice = ActualDice(dice._dice)
        if not new_dice.is_legal():
            return None
        else:
            return new_dice


class AbstractDice(Dice):
    """
    Used for the dice cost of cards and other actions
    """
    _LEGAL_ELEMS = frozenset({
        Element.OMNI,  # represents the request for dice of the same type
        Element.PYRO,
        Element.HYDRO,
        Element.ANEMO,
        Element.ELECTRO,
        Element.DENDRO,
        Element.CRYO,
        Element.GEO,
        Element.ANY,
    })

    def can_cost_less_any(self) -> bool:
        return self[Element.ANY] > 0

    def cost_less_any(self, num: int) -> Self:
        return (self - {Element.ANY: 1}).validify()

    def can_cost_less_elem(self, elem: None | Element = None) -> bool:
        if elem is not None:
            return self[elem] > 0 or self[Element.ANY] > 0
        else:
            return any(
                self[elem] > 0
                for elem in _PURE_ELEMS
            ) or self[Element.ANY] > 0

    def cost_less_elem(self, num: int, elem: None | Element = None) -> Self:
        if elem is None:
            elem = next((
                elem
                for elem in ActualDice._LEGAL_ELEMS_ORDERED
                if self[elem] > 0
            ), None)
            if elem is None:
                return self
        elem_less_amount = min(self[elem], num)
        any_less_amount = max(0, num - elem_less_amount)
        ret_val = (self - {elem: elem_less_amount, Element.ANY: any_less_amount}).validify()
        assert ret_val.is_legal(), f"{self} - {num}{elem} -> {ret_val}"
        return ret_val

    @classmethod
    def from_dice(cls, dice: Dice) -> Optional[AbstractDice]:
        new_dice = AbstractDice(dice._dice)
        if not new_dice.is_legal():
            return None
        else:
            return new_dice