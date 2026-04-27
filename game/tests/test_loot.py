import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from systems.loot import (
    LootResolver, LootResult, DroppedItem,
    Rarity, classify_rarity, RARITY_CHANCE_THRESHOLDS,
)
from data.monsters import MONSTERS, BOSSES, Drop
from data.items import WEAPONS, ARMORS, CONSUMABLES


# ─── Rarity classification ────────────────────────────────────────────────────

def test_classify_common():
    assert classify_rarity(0.6) == Rarity.COMMON


def test_classify_uncommon():
    assert classify_rarity(0.20) == Rarity.UNCOMMON


def test_classify_rare():
    assert classify_rarity(0.05) == Rarity.RARE


def test_classify_epic():
    assert classify_rarity(0.01) == Rarity.EPIC


def test_classify_legendary():
    assert classify_rarity(0.002) == Rarity.LEGENDARY


def test_classify_raid():
    assert classify_rarity(0.0001) == Rarity.RAID


# ─── LootResult helpers ───────────────────────────────────────────────────────

def test_loot_result_total_items():
    result = LootResult(dropped_items=[
        DroppedItem("a", 2, Rarity.COMMON),
        DroppedItem("b", 3, Rarity.UNCOMMON),
    ])
    assert result.total_items == 5


def test_loot_result_has_rare_or_better_true():
    result = LootResult(dropped_items=[
        DroppedItem("x", 1, Rarity.RARE),
    ])
    assert result.has_rare_or_better is True


def test_loot_result_has_rare_or_better_false():
    result = LootResult(dropped_items=[
        DroppedItem("x", 1, Rarity.COMMON),
        DroppedItem("y", 1, Rarity.UNCOMMON),
    ])
    assert result.has_rare_or_better is False


def test_loot_result_summary_empty():
    result = LootResult()
    assert result.summary() == "No drops."


def test_loot_result_summary_with_items():
    result = LootResult(
        dropped_items=[DroppedItem("bronze_sword", 1, Rarity.COMMON)],
        zone_currency=10,
    )
    s = result.summary()
    assert "bronze_sword" in s.lower() or "Bronze Sword" in s
    assert "10" in s


# ─── DroppedItem display_name ─────────────────────────────────────────────────

def test_dropped_item_display_name_with_item():
    from data.items import WEAPONS
    di = DroppedItem("bronze_sword", 1, Rarity.COMMON, item=WEAPONS["bronze_sword"])
    assert di.display_name == WEAPONS["bronze_sword"].name


def test_dropped_item_display_name_no_item():
    di = DroppedItem("raw_iron_ore", 1, Rarity.COMMON, item=None)
    assert di.display_name == "Raw Iron Ore"


# ─── Resolve kill ─────────────────────────────────────────────────────────────

def test_resolve_kill_returns_loot_result():
    resolver = LootResolver(zone_id="forest", luck=0.0, depth=0)
    monster = MONSTERS["goblin"]
    result = resolver.resolve_kill(monster)
    assert isinstance(result, LootResult)


def test_resolve_kill_grants_currency():
    resolver = LootResolver(zone_id="forest", luck=0.0, depth=0)
    monster = MONSTERS["goblin"]
    result = resolver.resolve_kill(monster)
    assert result.zone_currency >= 1


def test_resolve_kill_grants_gold():
    resolver = LootResolver(zone_id="forest", luck=0.0, depth=0)
    monster = MONSTERS["goblin"]
    result = resolver.resolve_kill(monster)
    assert result.gold >= 0


def test_boss_kill_is_flagged():
    resolver = LootResolver(zone_id="forest", luck=0.0, depth=0)
    boss = BOSSES["goblin_king"]
    result = resolver.resolve_kill(boss)
    assert result.is_boss_kill is True


def test_boss_kill_more_currency_than_normal():
    resolver = LootResolver(zone_id="forest", luck=0.0, depth=0)
    goblin = MONSTERS["goblin"]
    boss   = BOSSES["goblin_king"]
    # Run many samples to confirm boss gives more on average
    normal_total = sum(resolver.resolve_kill(goblin).zone_currency for _ in range(20))
    boss_total   = sum(resolver.resolve_kill(boss).zone_currency   for _ in range(20))
    assert boss_total > normal_total


# ─── Luck scaling ─────────────────────────────────────────────────────────────

def test_luck_increases_drop_rate():
    """High luck should produce more drops on average than no luck."""
    monster = MONSTERS["goblin"]
    no_luck  = LootResolver(zone_id="forest", luck=0.0, depth=0)
    max_luck = LootResolver(zone_id="forest", luck=1.0, depth=0)

    count_no   = sum(len(no_luck.resolve_kill(monster).dropped_items)  for _ in range(50))
    count_max  = sum(len(max_luck.resolve_kill(monster).dropped_items) for _ in range(50))
    assert count_max >= count_no


# ─── Loot room ────────────────────────────────────────────────────────────────

def test_resolve_loot_room():
    resolver = LootResolver(zone_id="forest", luck=0.0, depth=0)
    drops = [Drop(item_id="basic_potion", chance=1.0, quantity_min=1, quantity_max=2)]
    result = resolver.resolve_loot_room(drops)
    assert isinstance(result, LootResult)
    assert result.zone_currency >= 5
    assert len(result.dropped_items) == 1


# ─── Treasure event ──────────────────────────────────────────────────────────

def test_resolve_treasure():
    resolver = LootResolver(zone_id="forest", luck=0.0, depth=0)
    result = resolver.resolve_treasure()
    assert isinstance(result, LootResult)
    assert result.zone_currency >= 15
    assert len(result.dropped_items) >= 1


# ─── Trap event ───────────────────────────────────────────────────────────────

def test_resolve_trap_returns_damage():
    resolver = LootResolver(zone_id="forest", luck=0.0, depth=0)
    damage, loot = resolver.resolve_trap(player_hp=100)
    assert damage >= 10
    assert damage < 100
    assert isinstance(loot, LootResult)


def test_resolve_trap_damage_scales_with_hp():
    resolver = LootResolver(zone_id="forest", luck=0.0, depth=0)
    low_damage_avg  = sum(resolver.resolve_trap(50)[0]  for _ in range(20)) / 20
    high_damage_avg = sum(resolver.resolve_trap(200)[0] for _ in range(20)) / 20
    assert high_damage_avg >= low_damage_avg


# ─── Special monster ─────────────────────────────────────────────────────────

def test_special_monster_double_currency():
    resolver = LootResolver(zone_id="forest", luck=0.0, depth=0)
    monster = MONSTERS["elite_goblin"]
    normal_result  = resolver.resolve_kill(monster)
    special_result = resolver.resolve_special_monster(monster)
    assert special_result.zone_currency >= normal_result.zone_currency


# ─── Apply to player ─────────────────────────────────────────────────────────

def test_apply_to_player_credits_currency():
    from entities.player import Player
    player = Player(name="Test")
    before = player.inventory.zone_currency
    result = LootResult(zone_currency=50, gold=10)
    LootResolver.apply_to_player(result, player)
    assert player.inventory.zone_currency == before + 50
    assert player.inventory.gold == 10


def test_apply_to_player_adds_items():
    from entities.player import Player
    from copy import deepcopy
    player = Player(name="Test")
    item = deepcopy(WEAPONS["bronze_sword"])
    result = LootResult(
        dropped_items=[DroppedItem("bronze_sword", 1, Rarity.UNCOMMON, item=item)]
    )
    overflow = LootResolver.apply_to_player(result, player)
    assert len(overflow) == 0
    assert len([i for i in player.inventory.items if i is not None]) >= 1
