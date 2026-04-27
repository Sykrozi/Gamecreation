"""
Loot system — resolves drops from monsters, bosses, loot rooms, and events.

Rarity tiers:
  COMMON      — frequent drops, basic consumables/resources
  UNCOMMON    — occasional gear pieces and better consumables
  RARE        — notable drops, lower-tier gear upgrades
  EPIC        — significant pieces, mid-to-late gear
  LEGENDARY   — very rare, best-in-slot non-raid items
  RAID        — exclusive to raid bosses

Drop resolution follows this pipeline:
  1. Roll each entry in the monster/room drop table independently.
  2. Apply zone luck modifier (scales with run depth).
  3. Clamp quantity to [min, max].
  4. Return LootResult with all dropped items and total zone currency.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from copy import deepcopy

from core.constants import MaterialTier
from data.monsters import Drop, MonsterDefinition, BossDefinition
from data.items import Item, Weapon, Armor, Consumable, WEAPONS, ARMORS, CONSUMABLES


class Rarity(Enum):
    COMMON    = "common"
    UNCOMMON  = "uncommon"
    RARE      = "rare"
    EPIC      = "epic"
    LEGENDARY = "legendary"
    RAID      = "raid"


# Base drop-chance thresholds that define rarity category
RARITY_CHANCE_THRESHOLDS = {
    Rarity.COMMON:    0.50,
    Rarity.UNCOMMON:  0.20,
    Rarity.RARE:      0.05,
    Rarity.EPIC:      0.01,
    Rarity.LEGENDARY: 0.002,
    Rarity.RAID:      0.001,
}


def classify_rarity(chance: float) -> Rarity:
    for rarity, threshold in RARITY_CHANCE_THRESHOLDS.items():
        if chance >= threshold:
            return rarity
    return Rarity.RAID


@dataclass
class DroppedItem:
    item_id: str
    quantity: int
    rarity: Rarity
    item: Item | None = None      # resolved item object (None for raw resources)

    @property
    def display_name(self) -> str:
        return self.item.name if self.item else self.item_id.replace("_", " ").title()


@dataclass
class LootResult:
    dropped_items: list[DroppedItem] = field(default_factory=list)
    zone_currency: int = 0
    gold: int = 0
    is_boss_kill: bool = False

    @property
    def total_items(self) -> int:
        return sum(d.quantity for d in self.dropped_items)

    @property
    def has_rare_or_better(self) -> bool:
        return any(d.rarity in (Rarity.RARE, Rarity.EPIC, Rarity.LEGENDARY, Rarity.RAID)
                   for d in self.dropped_items)

    def summary(self) -> str:
        if not self.dropped_items and not self.zone_currency:
            return "No drops."
        parts = [f"{d.quantity}x {d.display_name} [{d.rarity.value}]"
                 for d in self.dropped_items]
        if self.zone_currency:
            parts.append(f"{self.zone_currency}x currency")
        return ", ".join(parts)


# ─── Zone-specific ambient drop tables ────────────────────────────────────────

def _ambient_drops(zone_id: str, depth: int) -> list[Drop]:
    """Filler drops that can appear in any room regardless of monster."""
    from data.zones import ZONES
    zone = ZONES.get(zone_id)
    if not zone:
        return []
    ambient: list[Drop] = []
    for item_id in zone.ambient_loot_table:
        # Chance scales down slightly with tier depth
        base_chance = max(0.05, 0.25 - depth * 0.01)
        ambient.append(Drop(item_id=item_id, chance=base_chance,
                            quantity_min=1, quantity_max=1))
    return ambient


# ─── Currency reward helpers ──────────────────────────────────────────────────

def _currency_reward(monster: MonsterDefinition, is_boss: bool, luck: float) -> int:
    base = monster.level * 2
    if is_boss:
        base *= 10
    return max(1, int(base * (1.0 + luck * 0.5) * random.uniform(0.8, 1.2)))


def _gold_reward(monster: MonsterDefinition, is_boss: bool) -> int:
    base = monster.level
    if is_boss:
        base *= 5
    return max(0, int(base * random.uniform(0.5, 1.5)))


# ─── Item resolver ────────────────────────────────────────────────────────────

def _resolve_item(item_id: str) -> Item | None:
    if item_id in WEAPONS:
        return deepcopy(WEAPONS[item_id])
    if item_id in ARMORS:
        return deepcopy(ARMORS[item_id])
    if item_id in CONSUMABLES:
        return deepcopy(CONSUMABLES[item_id])
    return None


# ─── Main loot resolver ───────────────────────────────────────────────────────

class LootResolver:
    """
    Resolves loot for a combat kill, loot room, or event.

    `luck` is a float in [0.0, 1.0] that scales rare drop probabilities.
    It can be driven by potions, zone bonuses, or skill unlocks later.
    """

    def __init__(self, zone_id: str = "forest", luck: float = 0.0, depth: int = 0):
        self.zone_id = zone_id
        self.luck = luck          # extra probability bonus
        self.depth = depth        # room index in dungeon (0 = first room)

    # ─── Combat kill ─────────────────────────────────────────────────────

    def resolve_kill(self, monster: MonsterDefinition) -> LootResult:
        is_boss = isinstance(monster, BossDefinition) or monster.is_boss
        result = LootResult(is_boss_kill=is_boss)
        result.zone_currency = _currency_reward(monster, is_boss, self.luck)
        result.gold = _gold_reward(monster, is_boss)

        # Monster's own drop table
        for drop in monster.drops:
            self._roll_drop(drop, result)

        # Ambient zone filler (only for non-boss kills)
        if not is_boss:
            for drop in _ambient_drops(self.zone_id, self.depth):
                self._roll_drop(drop, result, ambient=True)

        return result

    # ─── Loot room ────────────────────────────────────────────────────────

    def resolve_loot_room(self, drop_table: list[Drop]) -> LootResult:
        result = LootResult()
        result.zone_currency = random.randint(5, 20)
        for drop in drop_table:
            self._roll_drop(drop, result)
        return result

    # ─── Event: treasure ──────────────────────────────────────────────────

    def resolve_treasure(self) -> LootResult:
        result = LootResult()
        result.zone_currency = random.randint(15, 40)
        # Pick 2–4 random zone-appropriate items
        from data.zones import ZONES
        zone = ZONES.get(self.zone_id)
        pool = zone.ambient_loot_table if zone else list(CONSUMABLES.keys())
        picks = random.sample(pool, min(len(pool), random.randint(2, 4)))
        for item_id in picks:
            drop = Drop(item_id=item_id, chance=1.0, quantity_min=1, quantity_max=2)
            self._roll_drop(drop, result)
        return result

    # ─── Event: trap ──────────────────────────────────────────────────────

    def resolve_trap(self, player_hp: int) -> tuple[int, LootResult]:
        """Returns (damage, loot). Traps always give a small consolation drop."""
        damage = random.randint(10, max(11, player_hp // 5))
        result = LootResult()
        # Small chance of a useful drop to compensate
        consolation = random.choice(list(CONSUMABLES.keys()))
        if random.random() < 0.6:
            self._roll_drop(
                Drop(item_id=consolation, chance=1.0, quantity_min=1, quantity_max=1),
                result
            )
        return damage, result

    # ─── Rare / elite monster ─────────────────────────────────────────────

    def resolve_special_monster(self, monster: MonsterDefinition) -> LootResult:
        """Rare/elite kills get a bonus luck roll."""
        boosted = LootResolver(self.zone_id, min(1.0, self.luck + 0.3), self.depth)
        result = boosted.resolve_kill(monster)
        result.zone_currency = int(result.zone_currency * 2)
        return result

    # ─── Internal ─────────────────────────────────────────────────────────

    def _roll_drop(self, drop: Drop, result: LootResult,
                   ambient: bool = False) -> None:
        effective_chance = min(1.0, drop.chance * (1.0 + self.luck * 0.25))
        if random.random() > effective_chance:
            return
        qty = random.randint(drop.quantity_min, drop.quantity_max)
        rarity = classify_rarity(drop.chance)
        item = _resolve_item(drop.item_id)
        result.dropped_items.append(DroppedItem(
            item_id=drop.item_id,
            quantity=qty,
            rarity=rarity,
            item=item,
        ))

    # ─── Apply loot to player inventory ───────────────────────────────────

    @staticmethod
    def apply_to_player(loot: LootResult, player) -> list[str]:
        """
        Deposits items into player inventory and credits currency.
        Returns list of items that couldn't fit (inventory full).
        """
        overflow: list[str] = []
        for dropped in loot.dropped_items:
            if dropped.item:
                if not player.inventory.add(dropped.item):
                    overflow.append(dropped.item_id)
            # Raw resources (no item object) go to hub storage later

        player.inventory.zone_currency += loot.zone_currency
        player.inventory.gold += loot.gold
        return overflow
