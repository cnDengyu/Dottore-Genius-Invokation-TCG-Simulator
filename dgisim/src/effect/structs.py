from dataclasses import dataclass, fields
from typing import TYPE_CHECKING

from ..helper.quality_of_life import dataclass_repr
from ..state.enums import PID
from .enums import ZONE


@dataclass(frozen=True, repr=False)
class StaticTarget:
    pid: PID
    zone: ZONE
    id: int

    def __repr__(self) -> str:
        return dataclass_repr(self)

# TODO: postpone this until further tests are done
#       needs to investigate how Klee's burst and Mona's or Sucrose's Talent co-work
@dataclass(frozen=True, kw_only=True, repr=False)
class DamageType:
    normal_attack: bool = False
    charged_attack: bool = False
    plunge_attack: bool = False
    elemental_skill: bool = False
    elemental_burst: bool = False
    status: bool = False  # any talent, equipmenet, character status, combat status.
    summon: bool = False
    no_boost: bool = False  # reaction secondary damage, Klee's burst status...

    def __repr__(self) -> str:
        cls_fields = fields(self)
        enabled_fields = [
            field.name
            for field in cls_fields
            if self.__getattribute__(field.name)
        ]
        return f'{self.__class__.__name__}({", ".join(enabled_fields)})'