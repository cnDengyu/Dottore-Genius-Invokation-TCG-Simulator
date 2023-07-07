from __future__ import annotations

from ..card import card as cd
from ..card.cards import Cards
from ..character.character_skill_enum import CharacterSkill
from ..dices import ActualDices, AbstractDices
from ..effect.structs import StaticTarget
from ..element.element import Element

from .enums import ActionType

_SingleChoiceType = (
    StaticTarget
    | int
    | ActualDices
    | CharacterSkill
    | type["cd.Card"]
    | Element
    | ActionType
)

GivenChoiceType = tuple[_SingleChoiceType, ...] | ActualDices | AbstractDices | Cards

DecidedChoiceType = _SingleChoiceType | ActualDices | Cards