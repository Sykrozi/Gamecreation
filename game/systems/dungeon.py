"""
Dungeon runner — generates a sequence of rooms per run and drives the flow.

Room sequence per run:
  [Combat, Combat, ..., Skill (mandatory), ..., Event (rare), ..., Boss (final)]

The number of combat rooms varies (4–8), one skill room is always present,
events are rare, and the boss is always last.

Zone entry is gated by:
  1. The previous zone's boss must have been recorded as defeated.
  2. The player must meet the minimum combat level for the zone.

Integrated systems:
  - LootResolver   — resolves all item/currency drops
  - SkillChallenge — drives skill-room mini-game resolution
  - MerchantShop   — generates a shop for merchant event rooms
  - ProgressionManager (optional) — records kills, boss kills, run outcomes
  - Bestiary (optional)           — records monster encounters
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from core.events import bus, GameEvent, EVT_DUNGEON_COMPLETE, EVT_DROP_RECEIVED
from data.monsters import (
    MonsterDefinition, BossDefinition,
    get_monsters_by_zone, get_boss_for_zone,
    BOSSES, Drop,
)
from entities.monster import MonsterInstance, BossInstance
from entities.player import Player
from systems.combat import CombatEngine, CombatResult

if TYPE_CHECKING:
    from systems.progression import ProgressionManager
    from systems.bestiary import Bestiary
    from systems.merchant import MerchantShop


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

    `defeated_boss_ids` is the persistent set of boss IDs killed across runs
    (typically stored in ProgressionManager.defeated_bosses).
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
        zone_monsters = get_monsters_by_zone(zone)
        normal_monsters = [m for m in zone_monsters
                           if not m.is_boss and not m.is_elite and not m.is_rare]
        elite_monsters  = [m for m in zone_monsters if m.is_elite]
        rare_monsters   = [m for m in zone_monsters if m.is_rare]
        boss            = get_boss_for_zone(zone)

        rooms: list[Room] = []
        num_combat     = random.randint(4, 8)
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
    Drives a dungeon run — connects rooms to combat, loot, skill, and events.

    Parameters
    ----------
    player      : Player instance (modified in-place)
    zone        : Zone ID string
    luck        : Float [0.0, 1.0] — luck modifier for LootResolver
    bestiary    : Optional Bestiary — records monster encounters
    progression : Optional ProgressionManager — records kills, boss kills,
                  run start (called automatically in __init__)
    defeated_bosses : Set of boss IDs already killed (used for unlock gating)
    """

    def __init__(
        self,
        player: Player,
        zone: str,
        luck: float = 0.0,
        bestiary: "Bestiary | None" = None,
        progression: "ProgressionManager | None" = None,
        defeated_bosses: set[str] | None = None,
    ) -> None:
        self.player      = player
        self.zone        = zone
        self.luck        = luck
        self.bestiary    = bestiary
        self.progression = progression
        self.defeated_bosses: set[str] = (
            defeated_bosses
            if defeated_bosses is not None
            else (progression.defeated_bosses if progression else set())
        )

        generator = DungeonGenerator()
        self.run = generator.generate(zone)
        # _loot, _merchant lazily initialised via properties below

        if self.progression:
            self.progression.record_run_start(zone)

    @property
    def current_room(self) -> Room | None:
        return self.run.current_room

    # ─── Lazy helpers ─────────────────────────────────────────────────────

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
        if room.room_type == RoomType.BOSS:
            return {
                "type": "boss",
                "boss": room.monster.name if room.monster else "Unknown boss",
                "phases": len(room.monster.phases) if hasattr(room.monster, "phases") else 1,
            }
        if room.room_type == RoomType.SKILL:
            from data.zones import ZONES
            zone_def = ZONES.get(self.zone)
            skill = zone_def.skill_challenge if zone_def else None
            return {
                "type": "skill",
                "skill": skill.value if skill else "unknown",
                "description": f"A {skill.value.capitalize()} challenge blocks your path." if skill else "",
            }
        if room.room_type == RoomType.LOOT:
            return {"type": "loot", "drops": [d.item_id for d in room.loot]}
        if room.room_type == RoomType.EVENT:
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
        """Call after combat finishes. Updates drops, XP, bestiary, progression."""
        result = engine.result
        room   = self.current_room

        if result == CombatResult.PLAYER_WIN:
            monster_def = engine.enemy.definition
            is_boss    = isinstance(monster_def, BossDefinition) or monster_def.is_boss
            is_special = (getattr(monster_def, "is_elite", False)
                          or getattr(monster_def, "is_rare", False))

            # --- XP ---
            xp_gain = engine.enemy.xp_reward
            from core.constants import SkillType
            self.player.skills.add_xp(SkillType.ATTACK,   xp_gain // 2)
            self.player.skills.add_xp(SkillType.DEFENSE,  xp_gain // 4)
            self.player.skills.add_xp(SkillType.STRENGTH, xp_gain // 4)

            # --- Loot ---
            self._loot.depth = self.run.current_room_index
            loot_result = (
                self._loot.resolve_special_monster(monster_def) if is_special
                else self._loot.resolve_kill(monster_def)
            )
            overflow = self._apply_loot(loot_result)

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

            # --- Progression / bestiary ---
            if self.progression:
                self.progression.record_kill(self.zone)
                if is_boss:
                    self.progression.record_boss_kill(monster_def.id, self.zone)

            if self.bestiary is not None:
                self.bestiary.record_kill(monster_def.id, self.zone)

            if is_boss:
                self.defeated_bosses.add(monster_def.id)

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
                "boss_id": monster_def.id if is_boss else None,
            }

        if result == CombatResult.PLAYER_FLED:
            room.completed = True
            self.run.advance()
            return {"result": "fled"}

        if result == CombatResult.PLAYER_DEAD:
            self.run.player_died = True
            self.run.is_complete = True
            self.player.die()
            if self.progression:
                self.progression.record_death(self.zone)
            return {"result": "dead", "message": "You died. All run drops lost."}

        return {"result": "unknown"}

    # ─── Skill room ───────────────────────────────────────────────────────

    def complete_skill_room(self, precision: float) -> dict:
        """
        Attempt the skill-room challenge with a precision float (0.0–1.0).

        Returns:
          On pass : {"success": True, "xp": int, "quality": float,
                     "narrative": str, "bonus_items": list[str], "skill": str}
          On fail : {"blocked": True, "narrative": str, "xp": int, "skill": str}
          On error: {"error": str}
        """
        room = self.current_room
        if not room or room.room_type != RoomType.SKILL:
            return {"error": "Not a skill room"}

        from data.zones import ZONES
        from systems.skill_challenge import SkillChallenge
        zone_def = ZONES.get(self.zone)
        skill = zone_def.skill_challenge if zone_def else None
        if skill is None:
            from core.constants import SkillType
            skill = SkillType.MINING

        skill_level = self.player.skills.level(skill)
        challenge   = SkillChallenge()
        result      = challenge.attempt(skill, skill_level, precision)

        # Always grant at least consolation XP
        self.player.skills.add_xp(skill, result.xp_gained)

        if not result.passed:
            return {
                "blocked":   True,
                "narrative": result.narrative,
                "xp":        result.xp_gained,
                "skill":     skill.value,
            }

        # Bonus raw resource items (go to hub storage, not inventory)
        room.completed = True
        self.run.advance()
        return {
            "success":     True,
            "narrative":   result.narrative,
            "xp":          result.xp_gained,
            "quality":     result.quality,
            "bonus_items": result.bonus_items,
            "skill":       skill.value,
        }

    # ─── Loot room ────────────────────────────────────────────────────────

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

    # ─── Event rooms ──────────────────────────────────────────────────────

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
        return {"drops": drops, "zone_currency": loot_result.zone_currency}

    def get_merchant_shop(self) -> "MerchantShop | None":
        """
        Returns a MerchantShop for the current room if it is a merchant event.
        The shop is cached on the room so repeated calls return the same stock.
        """
        room = self.current_room
        if not room or room.event_type != EventType.MERCHANT:
            return None
        if not hasattr(room, "_merchant"):
            from systems.merchant import MerchantShop
            room._merchant = MerchantShop(self.zone)
        return room._merchant

    def dismiss_merchant(self) -> dict:
        """Advance past the merchant room without buying anything."""
        room = self.current_room
        if not room or room.event_type != EventType.MERCHANT:
            return {"error": "Not a merchant room"}
        room.completed = True
        self.run.advance()
        return {"dismissed": True}

    # ─── Internal helpers ─────────────────────────────────────────────────

    def _apply_loot(self, loot_result) -> list[str]:
        from systems.loot import LootResolver
        return LootResolver.apply_to_player(loot_result, self.player)

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
        out = {}
        for style in CombatStyle:
            default = "neutral"
            for w in monster.weaknesses:
                if hasattr(w, "style") and w.style == style:
                    default = w.weakness.value if hasattr(w.weakness, "value") else str(w.weakness)
            out[style.value] = default
        return out

    def status(self) -> str:
        r = self.run
        return (
            f"[{self.zone.upper()}] Room {r.current_room_index + 1}/{r.total_rooms} | "
            f"Player HP: {self.player.hp}/{self.player.max_hp}"
        )
