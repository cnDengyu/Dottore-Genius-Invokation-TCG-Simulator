from typing import List
from random import random

from dgisim.src.player_agent import PlayerAgent
from dgisim.src.state.game_state import GameState
from dgisim.src.action import *
from dgisim.src.phase.card_select_phase import CardSelectPhase
from dgisim.src.phase.starting_hand_select_phase import StartingHandSelectPhase
from dgisim.src.phase.roll_phase import RollPhase
from dgisim.src.phase.action_phase import ActionPhase
from dgisim.src.card.cards import Cards
from dgisim.src.character.character import CharacterSkill
from dgisim.src.dices import AbstractDices, ActualDices
from dgisim.src.element.element import Element


class NoneAgent(PlayerAgent):
    pass


class LazyAgent(PlayerAgent):
    _NUM_PICKED_CARDS = 3

    def choose_action(self, history: List[GameState], pid: GameState.Pid) -> PlayerAction:
        game_state = history[-1]
        curr_phase = game_state.get_phase()
        if isinstance(curr_phase, CardSelectPhase):
            _, selected_cards = game_state.get_player(
                pid).get_hand_cards().pick_random_cards(self._NUM_PICKED_CARDS)
            return CardSelectAction(selected_cards)
        elif isinstance(curr_phase, StartingHandSelectPhase):
            return CharacterSelectAction(1)
        elif isinstance(curr_phase, RollPhase):
            raise Exception("No Action Defined")
        elif isinstance(curr_phase, ActionPhase):
            selection = random()
            me = game_state.get_player(pid)
            available_dices = me.get_dices()
            if available_dices.num_dices() > 0 and selection < 0.5:
                dices = available_dices.basically_satisfy(AbstractDices({
                    Element.ANY: 2,
                }))
                if dices is not None:
                    print("TTK")
                    return SkillAction(
                        CharacterSkill.NORMAL_ATTACK,
                        DiceOnlyInstruction(dices),
                    )
            return EndRoundAction()
        else:
            raise Exception("No Action Defined")
