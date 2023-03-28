from dgisim.src.card.card import *

DEFAULT_CARDS: frozenset[type[Card]] = frozenset({
    Starsigns,
    # Food
    JueyunGuoba,
    LotusFlowerCrisp,
    NorthernSmokedChicken,
    SweetMadame,
    MondstadtHashBrown,
    MushroomPizza,
    MintyMeatRolls,
})

_DEFAULT_CARDS: list[type[Card]] = [
    Starsigns,
    # Food
    JueyunGuoba,
    LotusFlowerCrisp,
    NorthernSmokedChicken,
    SweetMadame,
    MondstadtHashBrown,
    MushroomPizza,
    MintyMeatRolls,
]

_DEFAULT_CARDS_FSET = None


def default_cards() -> frozenset[type[Card]]:
    global _DEFAULT_CARDS_FSET
    if _DEFAULT_CARDS_FSET is None:
        _DEFAULT_CARDS_FSET = frozenset(_DEFAULT_CARDS)
    return _DEFAULT_CARDS_FSET
