"""
Dungeon runner — generates a sequence of rooms per run and drives the flow.

Room sequence per run:
  [Combat, Combat, ..., Skill (mandatory), ..., Event (rare), ..., Boss (final)]

The number of combat rooms varies (4–8), one skill room is always present,
events are rare, and the boss is always last.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto

from core.events import bus, GameEvent, EVT_DUNGEON_COMPLETE, EVT_DROP_RECEIVED
from data.monsters import (
    MonsterDefinition, BossDefinition,
    get_monsters_by_zone, get_boss_for_zone,
    BOSSES, Drop,
)
from entities.monster import MonsterInstance, BossInstance
from entities.player import Player
from systems.combat import CombatEngine, CombatResult


class RoomType(Enum):
    COMBAT = "combat"
    SKILL = "skill"
    LOOT = "loot"
    EVENT = "event"
    BOSS = "boss"


class EventType(Enum):
    MERCHANT = "merchant"
    RARE_MONSTER = "rare_monster"
    TRAP = "trap"
    TREASURE = "treasure"
    ELITE = "elite"


@dataclass
class Room:
    room_type: RoomType
    index: int
    monster: MonsterDefinition | BossDefinition | None = None
    event_type: EventType | None = None
    loot: list[Drop] = field(default_factory=list)
    completed: bool = False


@dataclass
class DungeonRun:
    zone: str
    rooms: list[Room] = field(default_factory=list)
    current_room_index: int = 0
    drops_this_run: list[dict] = field(default_factory=list)
    is_complete: bool = False
    player_died: bool = False

    @property
    def current_room(self) -> Room | None:
        if self.current_room_index < len(self.rooms):
            return self.rooms[self.current_room_index]
        return None

    def advance(self) -> Room | None:
        self.rooms[self.current_room_index].completed = True
        self.current_room_index += 1
        return self.current_room

    @property
    def total_rooms(self) -> int:
        return len(self.rooms)

    @property
    def progress_pct(self) -> float:
        return self.current_room_index / max(1, self.total_rooms)


class DungeonGenerator:
    """Builds a randomised room sequence for a zone."""

    _SKILL_ROOMS_BY_ZONE: dict[str, str] = {
        "forest": "woodcutting",
        "dungeon_1": "mining",
        "swamp": "herblore",
        "desert": "fishing",
        "mountain": "smithing",
        "raid": "runecraft",
    }

    def generate(self, zone: str) -> DungeonRun:
        zone_monsters = get_monsters_by_zone(zone)
        normal_monsters = [m for m in zone_monsters if not m.is_boss
                           and not m.is_elite and not m.is_rare]
        elite_monsters = [m for m in zone_monsters if m.is_elite]
        rare_monsters = [m for m in zone_monsters if m.is_rare]
        boss = get_boss_for_zone(zone)

        rooms: list[Room] = []
        num_combat = random.randint(4, 8)
        skill_room_pos = random.randint(1, num_combat - 1)  # not first, not last
        event_room_pos = random.randint(1, num_combat - 1) if random.random() < 0.35 else -1
        loot_room_pos = random.randint(1, num_combat - 1) if random.random() < 0.25 else -1

        for i in range(num_combat):
            if i == skill_room_pos:
                skill_name = self._SKILL_ROOMS_BY_ZONE.get(zone, "mining")
                rooms.append(Room(
                    room_type=RoomType.SKILL,
                    index=len(rooms),
                ))
            elif i == event_room_pos:
                event_type = self._pick_event(elite_monsters, rare_monsters)
                event_monster: MonsterDefinition | None = None
                if event_type == EventType.ELITE and elite_monsters:
                    event_monster = random.choice(elite_monsters)
                elif event_type == EventType.RARE_MONSTER and rare_monsters:
                    event_monster = random.choice(rare_monsters)
                rooms.append(Room(
                    room_type=RoomType.EVENT,
                    index=len(rooms),
                    event_type=event_type,
                    monster=event_monster,
                ))
            elif i == loot_room_pos:
                rooms.append(Room(
                    room_type=RoomType.LOOT,
                    index=len(rooms),
                    loot=self._generate_loot_room_drops(zone),
                ))
            else:
                monster = random.choice(normal_monsters) if normal_monsters else None
                rooms.append(Room(
                    room_type=RoomType.COMBAT,
                    index=len(rooms),
                    monster=monster,
                ))

        # Boss always last
        if boss:
            rooms.append(Room(room_type=RoomType.BOSS, index=len(rooms), monster=boss))

        return DungeonRun(zone=zone, rooms=rooms)

    def _pick_event(self, elites, rares) -> EventType:
        options = [EventType.MERCHANT, EventType.TRAP, EventType.TREASURE]
        if elites:
            options.append(EventType.ELITE)
        if rares:
            options.append(EventType.RARE_MONSTER)
        return random.choice(options)

    def _generate_loot_room_drops(self, zone: str) -> list[Drop]:
        from data.items import CONSUMABLES
        loot = []
        consumable_ids = list(CONSUMABLES.keys())
        for _ in range(random.randint(1, 3)):
            loot.append(Drop(
                item_id=random.choice(consumable_ids),
                chance=1.0,
                quantity_min=1,
                quantity_max=3,
            ))
        return loot


class DungeonRunner:
    """Drives a dungeon run — connects rooms to combat engine and event logic."""

    def __init__(self, player: Player, zone: str):
        self.player = player
        self.zone = zone
        generator = DungeonGenerator()
        self.run = generator.generate(zone)

    @property
    def current_room(self) -> Room | None:
        return self.run.current_room

    def enter_current_room(self) -> dict:
        """Return info about the current room for the UI layer to display."""
        room = self.current_room
        if not room:
            return {"type": "complete", "message": "Dungeon complete!"}

        if room.room_type == RoomType.COMBAT:
            return {
                "type": "combat",
                "monster": room.monster.name if room.monster else "Unknown enemy",
                "weaknesses": {
                    s.value: self._get_monster_weakness(room.monster, s)
                    for s in __import__("core.constants", fromlist=["CombatStyle"]).CombatStyle
                } if room.monster else {},
            }
        elif room.room_type == RoomType.BOSS:
            return {
                "type": "boss",
                "boss": room.monster.name if room.monster else "Unknown boss",
                "phases": len(room.monster.phases) if hasattr(room.monster, "phases") else 1,
            }
        elif room.room_type == RoomType.SKILL:
            return {"type": "skill", "skill": "Interact with the skill challenge to proceed."}
        elif room.room_type == RoomType.LOOT:
            return {"type": "loot", "drops": [d.item_id for d in room.loot]}
        elif room.room_type == RoomType.EVENT:
            return {
                "type": "event",
                "event": room.event_type.value if room.event_type else "unknown",
                "monster": room.monster.name if room.monster else None,
            }
        return {"type": "unknown"}

    def start_combat(self) -> CombatEngine | None:
        room = self.current_room
        if not room or room.room_type not in (RoomType.COMBAT, RoomType.BOSS, RoomType.EVENT):
            return None
        if not room.monster:
            return None

        if room.room_type == RoomType.BOSS or isinstance(room.monster, BossDefinition):
            enemy = BossInstance(definition=room.monster)
        else:
            enemy = MonsterInstance(definition=room.monster)

        engine = CombatEngine(player=self.player, enemy=enemy)
        engine.start()
        return engine

    def resolve_combat(self, engine: CombatEngine) -> dict:
        """Call after combat finishes. Handles drops, XP, and room advance."""
        result = engine.result
        room = self.current_room

        if result == CombatResult.PLAYER_WIN:
            xp_gain = engine.enemy.xp_reward
            from core.constants import SkillType
            self.player.skills.add_xp(SkillType.ATTACK, xp_gain // 2)
            self.player.skills.add_xp(SkillType.DEFENSE, xp_gain // 4)
            self.player.skills.add_xp(SkillType.STRENGTH, xp_gain // 4)

            drops = self._resolve_drops(engine.enemy.definition.drops)
            for drop in drops:
                self.run.drops_this_run.append(drop)
            bus.emit(GameEvent(EVT_DROP_RECEIVED, {"drops": drops}))

            room.completed = True
            self.run.advance()
            self._check_dungeon_complete()

            return {"result": "win", "xp": xp_gain, "drops": drops}

        elif result == CombatResult.PLAYER_FLED:
            room.completed = True
            self.run.advance()
            return {"result": "fled"}

        elif result == CombatResult.PLAYER_DEAD:
            self.run.player_died = True
            self.run.is_complete = True
            self.player.die()
            return {"result": "dead", "message": "You died. All run drops lost."}

        return {"result": "unknown"}

    def collect_loot_room(self) -> dict:
        room = self.current_room
        if not room or room.room_type != RoomType.LOOT:
            return {"error": "Not a loot room"}
        drops = self._resolve_drops(room.loot)
        room.completed = True
        self.run.advance()
        return {"drops": drops}

    def complete_skill_room(self, success: bool) -> dict:
        room = self.current_room
        if not room or room.room_type != RoomType.SKILL:
            return {"error": "Not a skill room"}
        if not success:
            return {"blocked": True, "message": "Complete the skill challenge to proceed."}
        room.completed = True
        self.run.advance()
        return {"success": True}

    def handle_trap_event(self) -> dict:
        """Trap deals damage and gives some loot."""
        from data.items import CONSUMABLES
        trap_dmg = random.randint(15, 40)
        self.player._hp = max(1, self.player.hp - trap_dmg)
        loot_drop = [Drop(
            item_id=random.choice(list(CONSUMABLES.keys())),
            chance=1.0, quantity_min=1, quantity_max=2,
        )]
        drops = self._resolve_drops(loot_drop)
        room = self.current_room
        if room:
            room.completed = True
            self.run.advance()
        return {"trap_damage": trap_dmg, "drops": drops}

    def handle_treasure_event(self) -> dict:
        from data.items import CONSUMABLES, WEAPONS, ARMORS
        all_items = list(CONSUMABLES.keys()) + list(WEAPONS.keys()) + list(ARMORS.keys())
        drops = self._resolve_drops([
            Drop(item_id=random.choice(all_items), chance=1.0, quantity_min=1, quantity_max=1)
            for _ in range(random.randint(2, 4))
        ])
        room = self.current_room
        if room:
            room.completed = True
            self.run.advance()
        return {"drops": drops}

    def _resolve_drops(self, drop_table: list[Drop]) -> list[dict]:
        results = []
        for drop in drop_table:
            if random.random() <= drop.chance:
                qty = random.randint(drop.quantity_min, drop.quantity_max)
                results.append({"item_id": drop.item_id, "quantity": qty})
        return results

    def _check_dungeon_complete(self) -> None:
        if self.current_room is None:
            self.run.is_complete = True
            bus.emit(GameEvent(EVT_DUNGEON_COMPLETE, {
                "zone": self.zone,
                "drops": self.run.drops_this_run,
            }))

    def _get_monster_weakness(self, monster, style) -> str:
        if monster is None:
            return "neutral"
        for w in monster.weaknesses:
            if w.style == style:
                return w.weakness.value
        return "neutral"

    def status(self) -> str:
        r = self.run
        return (
            f"[{self.zone.upper()}] Room {r.current_room_index + 1}/{r.total_rooms} | "
            f"Player HP: {self.player.hp}/{self.player.max_hp}"
        )
