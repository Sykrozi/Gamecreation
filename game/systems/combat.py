import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List


class CombatState(Enum):
    PLAYER_TURN = auto()
    VICTORY     = auto()
    DEFEAT      = auto()
    FLED        = auto()


class Action(Enum):
    ATTACK = auto()
    DEFEND = auto()
    FLEE   = auto()


@dataclass
class TurnResult:
    logs:          List[str]    = field(default_factory=list)
    player_damage: int          = 0
    enemy_damage:  int          = 0
    state:         CombatState  = CombatState.PLAYER_TURN
    shake_player:  bool         = False
    shake_enemy:   bool         = False


class CombatSystem:
    def __init__(self, player, enemy):
        self.player = player
        self.enemy  = enemy
        self.state  = CombatState.PLAYER_TURN
        self.turn   = 0

    # ------------------------------------------------------------------
    def execute(self, action: Action) -> TurnResult:
        result = TurnResult()
        self.turn += 1

        if action == Action.ATTACK:
            self._player_strikes(result)
            if result.state is CombatState.PLAYER_TURN:
                self._enemy_turn(result)

        elif action == Action.DEFEND:
            self.player.start_defend()
            result.logs.append("You brace for impact!")
            self._enemy_turn(result)
            self.player.end_turn()

        elif action == Action.FLEE:
            if self._attempt_flee():
                result.logs.append("You escaped from battle!")
                result.state = CombatState.FLED
                self.state   = CombatState.FLED
                return result
            result.logs.append("No escape! The enemy blocks your path.")
            self._enemy_turn(result)

        if result.state is CombatState.PLAYER_TURN and not self.player.alive:
            result.logs.append(f"You have been defeated by {self.enemy.name}...")
            result.state = CombatState.DEFEAT
            self.state   = CombatState.DEFEAT

        return result

    # ------------------------------------------------------------------
    def _player_strikes(self, result: TurnResult):
        raw = self.player.roll_damage()
        dmg = self.enemy.receive_hit(raw)
        result.enemy_damage = dmg
        result.shake_enemy  = True
        result.logs.append(f"You hit {self.enemy.name} for {dmg} damage!")

        if not self.enemy.alive:
            result.logs.append(f"{self.enemy.name} has been defeated!")
            result.state = CombatState.VICTORY
            self.state   = CombatState.VICTORY

    def _enemy_turn(self, result: TurnResult):
        choice = self._ai_choose()
        if choice == "attack":
            raw = self.enemy.roll_damage()
            dmg = self.player.receive_hit(raw)
            result.player_damage = dmg
            result.shake_player  = True
            result.logs.append(
                f"{self.enemy.name} strikes you for {dmg} damage!"
            )
        else:
            self.enemy.start_defend()
            result.logs.append(f"{self.enemy.name} takes a defensive stance!")

    def _ai_choose(self) -> str:
        hp_ratio = self.enemy.hp_ratio
        defend_bias = 0.10 if hp_ratio > 0.5 else 0.25
        if self.enemy.name == "Dark Lord":
            defend_bias += 0.10
        return "defend" if random.random() < defend_bias else "attack"

    def _attempt_flee(self) -> bool:
        speed_edge = self.player.speed - self.enemy.speed
        chance = 0.45 + speed_edge * 0.03
        return random.random() < max(0.15, min(0.80, chance))
