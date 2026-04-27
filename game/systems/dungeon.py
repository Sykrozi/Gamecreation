"""
Dungeon runner — generates a sequence of rooms per run and drives the flow.

Room sequence per run:
  [Combat, Combat, ..., Skill (mandatory), ..., Event (rare), ..., Boss (final)]

The number of combat rooms varies (4–8), one skill room is always present,
events are rare, and the boss is always last.

Zone entry is gated by:
  1. The previous zone's boss must have been recorded as defeated.
  2. The player must meet the minimum combat level for the zone.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

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
    SKILL  = "skill"
    LOOT   = "loot"
    EVENT  = "event"
    BOSS   = "boss"


class EventType(Enum):
    MERCHANT      = "merchant"
    RARE_MONSTER  = "rare_monster"
    TRAP          = "trap"
    TREASURE      = "treasure"
    ELITE         = "elite"


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


# ─── Zone unlock gating ───────────────────────────────────────────────────────

def can_enter_zone(
    zone_id: str,
    player: Player,
    defeated_boss_ids: set[str],
) -> tuple[bool, str]:
    """
    Returns (can_enter, reason_if_not).

    `defeated_boss_ids` is a persistent set on the player's save of all boss IDs
    they have killed across previous runs.
    """
    from data.zones import ZONES
    zone = ZONES.get(zone_id)
    if not zone:
        return False, f"Unknown zone '{zone_id}'."

    unlock = zone.unlock
    if unlock.previous_boss_id is not None:
        if unlock.previous_boss_id not in defeated_boss_ids:
            boss_def = BOSSES.get(unlock.previous_boss_id)
            boss_name = boss_def.name if boss_def else unlock.previous_boss_id
            return False, f"Must defeat {boss_name} first."

    cb = player.skills.combat_level
    if cb < unlock.min_combat_level:
        return False, (
            f"Need Combat Level {unlock.min_combat_level} "
            f"(you have {cb}). {unlock.description}"
        )

    return True, ""


# ─── Generator ────────────────────────────────────────────────────────────────

class DungeonGenerator:
    """Builds a randomised room sequence for a zone."""

    def generate(self, zone: str) -> DungeonRun:
        from data.zones import ZONES
        zone_def = ZONES.get(zone)

        zone_monsters = get_monsters_by_zone(zone)
        normal_monsters = [m for m in zone_monsters
                           if not m.is_boss and not m.is_elite and not m.is_rare]
        elite_monsters  = [m for m in zone_monsters if m.is_elite]
        rare_monsters   = [m for m in zone_monsters if m.is_rare]
        boss            = get_boss_for_zone(zone)

        rooms: list[Room] = []
        num_combat    = random.randint(4, 8)
        skill_room_pos = random.randint(1, num_combat - 1)
        event_room_pos = random.randint(1, num_combat - 1) if random.random() < 0.35 else -1
        loot_room_pos  = random.randint(1, num_combat - 1) if random.random() < 0.25 else -1

        for i in range(num_combat):
            if i == skill_room_pos:
                rooms.append(Room(room_type=RoomType.SKILL, index=len(rooms)))
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


# ─── Runner ───────────────────────────────────────────────────────────────────

class DungeonRunner:
    """
    Drives a dungeon run — connects rooms to combat engine, loot, and events.

    Parameters
    ----------
    player          : Player instance (modified in-place)
    zone            : Zone ID string
    luck            : Float [0.0, 1.0] — luck modifier for LootResolver
    bestiary        : Optional Bestiary — if provided, kills are recorded
    defeated_bosses : Set of boss IDs already killed (used for unlock check at
                      construction time; caller can pre-validate with
                      can_enter_zone() to show a cleaner error)
    """

    def __init__(
        self,
        player: Player,
        zone: str,
        luck: float = 0.0,
        bestiary=None,
        defeated_bosses: set[str] | None = None,
    ) -> None:
        self.player  = player
        self.zone    = zone
        self.luck    = luck
        self.bestiary = bestiary
        self.defeated_bosses: set[str] = defeated_bosses or set()

        generator = DungeonGenerator()
        self.run = generator.generate(zone)
        # _loot is initialised lazily via the property (so __new__ callers work too)

    @property
    def current_room(self) -> Room | None:
        return self.run.current_room

    @property
    def _loot(self):
        if not hasattr(self, "_loot_resolver"):
            from systems.loot import LootResolver
            self._loot_resolver = LootResolver(
                zone_id=getattr(self, "zone", "forest"),
                luck=getattr(self, "luck", 0.0),
                depth=0,
            )
        return self._loot_resolver

    # ─── Room info ────────────────────────────────────────────────────────

    def enter_current_room(self) -> dict:
        """Return info about the current room for the UI layer to display."""
        room = self.current_room
        if not room:
            return {"type": "complete", "message": "Dungeon complete!"}

        if room.room_type == RoomType.COMBAT:
            return {
                "type": "combat",
                "monster": room.monster.name if room.monster else "Unknown enemy",
                "weaknesses": self._weakness_dict(room.monster),
            }
        elif room.room_type == RoomType.BOSS:
            return {
                "type": "boss",
                "boss": room.monster.name if room.monster else "Unknown boss",
                "phases": len(room.monster.phases) if hasattr(room.monster, "phases") else 1,
            }
        elif room.room_type == RoomType.SKILL:
            from data.zones import ZONES
            zone_def = ZONES.get(self.zone)
            skill_name = (
                zone_def.skill_challenge.value if zone_def else "mining"
            )
            return {"type": "skill", "skill": skill_name}
        elif room.room_type == RoomType.LOOT:
            return {"type": "loot", "drops": [d.item_id for d in room.loot]}
        elif room.room_type == RoomType.EVENT:
            return {
                "type": "event",
                "event": room.event_type.value if room.event_type else "unknown",
                "monster": room.monster.name if room.monster else None,
            }
        return {"type": "unknown"}

    # ─── Combat ───────────────────────────────────────────────────────────

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
        """Call after combat finishes. Handles drops, XP, advance, and bestiary."""
        result = engine.result
        room   = self.current_room

        if result == CombatResult.PLAYER_WIN:
            monster_def = engine.enemy.definition
            is_boss     = isinstance(monster_def, BossDefinition) or monster_def.is_boss
            is_special  = getattr(monster_def, "is_elite", False) or getattr(monster_def, "is_rare", False)

            # --- XP ---
            xp_gain = engine.enemy.xp_reward
            from core.constants import SkillType
            self.player.skills.add_xp(SkillType.ATTACK,   xp_gain // 2)
            self.player.skills.add_xp(SkillType.DEFENSE,  xp_gain // 4)
            self.player.skills.add_xp(SkillType.STRENGTH, xp_gain // 4)

            # --- Loot (using LootResolver) ---
            self._loot.depth = self.run.current_room_index
            if is_special:
                loot_result = self._loot.resolve_special_monster(monster_def)
            else:
                loot_result = self._loot.resolve_kill(monster_def)

            overflow = self._apply_loot(loot_result)

            # Track boss kill for zone unlock
            if is_boss:
                self.defeated_bosses.add(monster_def.id)

            # Record in bestiary
            if self.bestiary is not None:
                self.bestiary.record_kill(monster_def.id, self.zone)

            # Build drop summary for callers
            drops = [
                {"item_id": d.item_id, "quantity": d.quantity, "rarity": d.rarity.value}
                for d in loot_result.dropped_items
            ]
            for d in drops:
                self.run.drops_this_run.append(d)

            bus.emit(GameEvent(EVT_DROP_RECEIVED, {
                "drops": drops,
                "zone_currency": loot_result.zone_currency,
                "gold": loot_result.gold,
            }))

            room.completed = True
            self.run.advance()
            self._check_dungeon_complete()

            return {
                "result": "win",
                "xp": xp_gain,
                "drops": drops,
                "zone_currency": loot_result.zone_currency,
                "gold": loot_result.gold,
                "overflow": overflow,
                "is_boss": is_boss,
            }

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

    # ─── Room interactions ────────────────────────────────────────────────

    def collect_loot_room(self) -> dict:
        room = self.current_room
        if not room or room.room_type != RoomType.LOOT:
            return {"error": "Not a loot room"}
        loot_result = self._loot.resolve_loot_room(room.loot)
        self._apply_loot(loot_result)
        drops = [
            {"item_id": d.item_id, "quantity": d.quantity, "rarity": d.rarity.value}
            for d in loot_result.dropped_items
        ]
        room.completed = True
        self.run.advance()
        return {"drops": drops, "zone_currency": loot_result.zone_currency}

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
        damage, loot_result = self._loot.resolve_trap(self.player.hp)
        self.player._hp = max(1, self.player.hp - damage)
        self._apply_loot(loot_result)
        drops = [
            {"item_id": d.item_id, "quantity": d.quantity, "rarity": d.rarity.value}
            for d in loot_result.dropped_items
        ]
        room = self.current_room
        if room:
            room.completed = True
            self.run.advance()
        return {"trap_damage": damage, "drops": drops}

    def handle_treasure_event(self) -> dict:
        loot_result = self._loot.resolve_treasure()
        self._apply_loot(loot_result)
        drops = [
            {"item_id": d.item_id, "quantity": d.quantity, "rarity": d.rarity.value}
            for d in loot_result.dropped_items
        ]
        room = self.current_room
        if room:
            room.completed = True
            self.run.advance()
        return {
            "drops": drops,
            "zone_currency": loot_result.zone_currency,
        }

    # ─── Internal helpers ─────────────────────────────────────────────────

    def _apply_loot(self, loot_result) -> list[str]:
        """Apply a LootResult to the player. Returns list of overflow item IDs."""
        from systems.loot import LootResolver
        overflow = LootResolver.apply_to_player(loot_result, self.player)
        return overflow

    def _check_dungeon_complete(self) -> None:
        if self.current_room is None:
            self.run.is_complete = True
            bus.emit(GameEvent(EVT_DUNGEON_COMPLETE, {
                "zone": self.zone,
                "drops": self.run.drops_this_run,
            }))

    def _weakness_dict(self, monster) -> dict:
        if monster is None:
            return {}
        from core.constants import CombatStyle
        result = {}
        for style in CombatStyle:
            default = "neutral"
            for w in monster.weaknesses:
                if hasattr(w, "style") and w.style == style:
                    default = w.weakness.value if hasattr(w.weakness, "value") else str(w.weakness)
            result[style.value] = default
        return result

    def status(self) -> str:
        r = self.run
        return (
            f"[{self.zone.upper()}] Room {r.current_room_index + 1}/{r.total_rooms} | "
            f"Player HP: {self.player.hp}/{self.player.max_hp}"
        )
