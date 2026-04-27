import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from copy import deepcopy
from entities.player import Player
from data.items import WEAPONS, ARMORS, CONSUMABLES
from systems.inventory_manager import InventoryManager, StatSnapshot
from core.constants import SkillType


# ─── Fixtures ────────────────────────────────────────────────────────────────

def make_player() -> Player:
    p = Player(name="Tester")
    p.equipment.weapon = deepcopy(WEAPONS["bronze_sword"])
    return p


def make_player_with_items() -> tuple[Player, InventoryManager]:
    """Player with a level-1-accessible weapon (basic_staff), armor, and potion."""
    p = make_player()
    mgr = InventoryManager(p)
    p.inventory.add(deepcopy(WEAPONS["basic_staff"]))
    p.inventory.add(deepcopy(ARMORS["bronze_body"]))
    p.inventory.add(deepcopy(CONSUMABLES["basic_potion"]))
    return p, mgr


def make_leveled_player() -> tuple[Player, InventoryManager]:
    """Player with attack level 5 so iron_sword can be equipped."""
    p = Player(name="Leveled")
    p.equipment.weapon = deepcopy(WEAPONS["bronze_sword"])
    while p.skills.level(SkillType.ATTACK) < 5:
        p.skills.add_xp(SkillType.ATTACK, 500)
    mgr = InventoryManager(p)
    p.inventory.add(deepcopy(WEAPONS["iron_sword"]))
    return p, mgr


# ─── StatSnapshot ─────────────────────────────────────────────────────────────

def test_stat_snapshot_delta_positive():
    a = StatSnapshot(attack_bonus=10, defense_bonus=5)
    b = StatSnapshot(attack_bonus=3, defense_bonus=2)
    d = a.delta(b)
    assert d.attack_bonus == 7
    assert d.defense_bonus == 3


def test_stat_snapshot_delta_negative():
    a = StatSnapshot(attack_bonus=2)
    b = StatSnapshot(attack_bonus=10)
    d = a.delta(b)
    assert d.attack_bonus == -8


def test_stat_snapshot_to_dict_keys():
    s = StatSnapshot(attack_bonus=1, defense_bonus=2, strength_bonus=3,
                     range_bonus=4, magic_bonus=5)
    d = s.to_dict()
    assert set(d.keys()) == {"attack", "defense", "strength", "range", "magic"}
    assert d["attack"] == 1
    assert d["magic"] == 5


# ─── Read helpers ─────────────────────────────────────────────────────────────

def test_slots_used_counts_items():
    p, mgr = make_player_with_items()
    assert mgr.slots_used() == 3


def test_slots_free_decreases_with_items():
    p, mgr = make_player_with_items()
    free = mgr.slots_free()
    assert free == p.inventory.max_slots - 3


def test_equipped_summary_includes_weapon():
    p = make_player()
    mgr = InventoryManager(p)
    summary = mgr.equipped_summary()
    assert "weapon" in summary
    assert summary["weapon"] == p.equipment.weapon.name


def test_equipped_summary_none_slots_empty():
    p = make_player()
    mgr = InventoryManager(p)
    summary = mgr.equipped_summary()
    assert summary["head"] is None
    assert summary["body"] is None


def test_inventory_summary_structure():
    p, mgr = make_player_with_items()
    items = mgr.inventory_summary()
    assert len(items) == 3
    assert all("item_id" in i and "name" in i and "type" in i for i in items)


def test_full_view_keys():
    p, mgr = make_player_with_items()
    view = mgr.full_view()
    assert "equipped" in view
    assert "inventory" in view
    assert "slots_used" in view
    assert "slots_free" in view
    assert "gold" in view


# ─── item_info ────────────────────────────────────────────────────────────────

def test_item_info_weapon_in_inventory():
    p, mgr = make_player_with_items()
    info = mgr.item_info("basic_staff")
    assert info["item_id"] == "basic_staff"
    assert "damage_min" in info
    assert "combat_style" in info


def test_item_info_armor_in_inventory():
    p, mgr = make_player_with_items()
    info = mgr.item_info("bronze_body")
    assert info["item_id"] == "bronze_body"
    assert "slot" in info


def test_item_info_consumable_in_inventory():
    p, mgr = make_player_with_items()
    info = mgr.item_info("basic_potion")
    assert "heal_amount" in info


def test_item_info_from_global_db():
    p = make_player()
    mgr = InventoryManager(p)
    # item not in inventory but exists in item DB
    info = mgr.item_info("rune_sword")
    assert "item_id" in info
    assert info["item_id"] == "rune_sword"


def test_item_info_unknown():
    p = make_player()
    mgr = InventoryManager(p)
    info = mgr.item_info("no_such_item")
    assert "error" in info


# ─── equip ────────────────────────────────────────────────────────────────────

def test_equip_weapon_from_inventory():
    p, mgr = make_leveled_player()
    result = mgr.equip("iron_sword")
    assert result["success"] is True
    assert p.equipment.weapon.id == "iron_sword"


def test_equip_returns_old_weapon_to_inventory():
    p, mgr = make_leveled_player()
    old_weapon_id = p.equipment.weapon.id
    mgr.equip("iron_sword")
    inv_ids = [i.id for i in p.inventory.items]
    assert old_weapon_id in inv_ids


def test_equip_armor_body_slot():
    p, mgr = make_player_with_items()
    result = mgr.equip("bronze_body")
    assert result["success"] is True
    assert p.equipment.body.id == "bronze_body"


def test_equip_not_in_inventory():
    p = make_player()
    mgr = InventoryManager(p)
    result = mgr.equip("basic_staff")
    assert result["success"] is False
    assert "not in inventory" in result["reason"].lower()


def test_equip_level_req_fails():
    p = make_player()
    mgr = InventoryManager(p)
    # rune_sword requires high attack level — player is level 1
    p.inventory.add(deepcopy(WEAPONS["rune_sword"]))
    result = mgr.equip("rune_sword")
    assert result["success"] is False
    assert "level" in result["reason"].lower()


def test_equip_consumable_fails():
    p = make_player()
    mgr = InventoryManager(p)
    p.inventory.add(deepcopy(CONSUMABLES["basic_potion"]))
    result = mgr.equip("basic_potion")
    assert result["success"] is False


# ─── unequip ─────────────────────────────────────────────────────────────────

def test_unequip_weapon():
    p = make_player()
    mgr = InventoryManager(p)
    result = mgr.unequip("weapon")
    assert result["success"] is True
    assert p.equipment.weapon is None
    inv_ids = [i.id for i in p.inventory.items]
    assert "bronze_sword" in inv_ids


def test_unequip_empty_slot():
    p = make_player()
    mgr = InventoryManager(p)
    result = mgr.unequip("head")
    assert result["success"] is False
    assert "nothing" in result["reason"].lower()


def test_unequip_invalid_slot():
    p = make_player()
    mgr = InventoryManager(p)
    result = mgr.unequip("ring")
    assert result["success"] is False


# ─── compare ─────────────────────────────────────────────────────────────────

def test_compare_weapon_returns_delta():
    p, mgr = make_player_with_items()
    result = mgr.compare("basic_staff")
    assert "delta" in result
    assert "candidate" in result
    assert "equipped" in result
    assert "is_upgrade" in result


def test_compare_armor_returns_delta():
    p, mgr = make_player_with_items()
    result = mgr.compare("bronze_body")
    assert "delta" in result


def test_compare_consumable_returns_error():
    p, mgr = make_player_with_items()
    result = mgr.compare("basic_potion")
    assert "error" in result


def test_compare_not_in_inventory():
    p = make_player()
    mgr = InventoryManager(p)
    result = mgr.compare("iron_sword")
    assert "error" in result


# ─── use_item ────────────────────────────────────────────────────────────────

def test_use_potion_heals_player():
    p = make_player()
    mgr = InventoryManager(p)
    # Damage the player first
    p._hp = p.max_hp - 10
    p.inventory.add(deepcopy(CONSUMABLES["basic_potion"]))
    result = mgr.use_item("basic_potion")
    assert result.get("success") is True


def test_use_item_not_in_inventory():
    p = make_player()
    mgr = InventoryManager(p)
    result = mgr.use_item("basic_potion")
    assert result.get("success") is False


# ─── drop ─────────────────────────────────────────────────────────────────────

def test_drop_removes_item():
    p, mgr = make_player_with_items()
    result = mgr.drop("basic_potion")
    assert result["success"] is True
    assert all(i.id != "basic_potion" for i in p.inventory.items)


def test_drop_missing_item():
    p = make_player()
    mgr = InventoryManager(p)
    result = mgr.drop("basic_potion")
    assert result["success"] is False


# ─── sort ─────────────────────────────────────────────────────────────────────

def test_sort_by_type():
    p, mgr = make_player_with_items()
    mgr.sort("type")
    types = [type(i).__name__ for i in p.inventory.items]
    assert types == sorted(types)


def test_sort_by_name():
    p, mgr = make_player_with_items()
    mgr.sort("name")
    names = [i.name.lower() for i in p.inventory.items]
    assert names == sorted(names)


def test_sort_by_level():
    p, mgr = make_player_with_items()
    mgr.sort("level")
    levels = [i.level_req for i in p.inventory.items]
    assert levels == sorted(levels)


# ─── filter_by_type ───────────────────────────────────────────────────────────

def test_filter_weapons():
    p, mgr = make_player_with_items()
    weapons = mgr.filter_by_type("weapon")
    assert len(weapons) == 1
    assert weapons[0]["item_id"] == "basic_staff"


def test_filter_armors():
    p, mgr = make_player_with_items()
    armors = mgr.filter_by_type("armor")
    assert len(armors) == 1
    assert armors[0]["item_id"] == "bronze_body"


def test_filter_consumables():
    p, mgr = make_player_with_items()
    cons = mgr.filter_by_type("consumable")
    assert len(cons) == 1


def test_filter_unknown_type_empty():
    p, mgr = make_player_with_items()
    result = mgr.filter_by_type("spell")
    assert result == []
