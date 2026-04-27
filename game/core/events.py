from dataclasses import dataclass, field
from typing import Any


@dataclass
class GameEvent:
    name: str
    data: dict[str, Any] = field(default_factory=dict)


class EventBus:
    def __init__(self):
        self._listeners: dict[str, list] = {}

    def subscribe(self, event_name: str, callback) -> None:
        self._listeners.setdefault(event_name, []).append(callback)

    def unsubscribe(self, event_name: str, callback) -> None:
        if event_name in self._listeners:
            self._listeners[event_name].remove(callback)

    def emit(self, event: GameEvent) -> None:
        for cb in self._listeners.get(event.name, []):
            cb(event)


# Singleton bus for the game session
bus = EventBus()

# Event name constants
EVT_COMBAT_START = "combat_start"
EVT_COMBAT_END = "combat_end"
EVT_TURN_START = "turn_start"
EVT_TURN_END = "turn_end"
EVT_ACTION_TAKEN = "action_taken"
EVT_DAMAGE_DEALT = "damage_dealt"
EVT_ENTITY_DIED = "entity_died"
EVT_STATUS_APPLIED = "status_applied"
EVT_STATUS_EXPIRED = "status_expired"
EVT_BOSS_PHASE_CHANGE = "boss_phase_change"
EVT_PLAYER_FLED = "player_fled"
EVT_LEVEL_UP = "level_up"
EVT_ITEM_USED = "item_used"
EVT_DROP_RECEIVED = "drop_received"
EVT_DUNGEON_COMPLETE = "dungeon_complete"
EVT_PLAYER_DIED = "player_died"
