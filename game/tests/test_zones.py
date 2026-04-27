import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from data.zones import ZONES, ZONE_ORDER, get_next_zone, get_zone, Zone
from core.constants import SkillType


# ─── Data integrity ───────────────────────────────────────────────────────────

def test_all_zones_defined():
    for zid in ("forest", "dungeon_1", "swamp", "desert", "mountain", "void", "raid"):
        assert zid in ZONES


def test_zone_order_covers_all_zones():
    assert set(ZONE_ORDER) == set(ZONES.keys())


def test_first_zone_has_no_boss_requirement():
    forest = ZONES["forest"]
    assert forest.unlock.previous_boss_id is None


def test_later_zones_require_previous_boss():
    for zid in ("dungeon_1", "swamp", "desert", "mountain", "void", "raid"):
        zone = ZONES[zid]
        assert zone.unlock.previous_boss_id is not None


def test_zones_have_ambient_loot():
    for zid, zone in ZONES.items():
        assert len(zone.ambient_loot_table) >= 1, f"{zid} has empty ambient_loot_table"


def test_zones_have_skill_challenge():
    for zid, zone in ZONES.items():
        assert isinstance(zone.skill_challenge, SkillType)


def test_zones_have_currency():
    for zid, zone in ZONES.items():
        assert zone.currency is not None
        assert zone.currency.id


def test_zones_have_boss():
    for zid, zone in ZONES.items():
        assert zone.boss_id, f"{zid} missing boss_id"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def test_get_next_zone_forest_to_dungeon():
    nxt = get_next_zone("forest")
    assert nxt == "dungeon_1"


def test_get_next_zone_last_is_none():
    last = ZONE_ORDER[-1]
    assert get_next_zone(last) is None


def test_get_next_zone_invalid():
    assert get_next_zone("nonexistent") is None


def test_get_zone_returns_zone():
    z = get_zone("forest")
    assert isinstance(z, Zone)
    assert z.id == "forest"


def test_get_zone_unknown_returns_none():
    assert get_zone("atlantis") is None


# ─── Unlock gating (via DungeonRunner helper) ─────────────────────────────────

def test_can_enter_starting_zone_always():
    from entities.player import Player
    from systems.dungeon import can_enter_zone
    player = Player(name="Test")
    ok, _ = can_enter_zone("forest", player, defeated_boss_ids=set())
    assert ok is True


def test_cannot_enter_dungeon_without_boss_kill():
    from entities.player import Player
    from systems.dungeon import can_enter_zone
    player = Player(name="Test")
    while player.skills.combat_level < 15:
        from core.constants import SkillType
        player.skills.add_xp(SkillType.ATTACK, 500_000)
    ok, reason = can_enter_zone("dungeon_1", player, defeated_boss_ids=set())
    assert ok is False
    assert "goblin" in reason.lower() or "defeat" in reason.lower()


def test_cannot_enter_zone_below_combat_level():
    from entities.player import Player
    from systems.dungeon import can_enter_zone
    player = Player(name="Test")   # combat level ~4
    ok, reason = can_enter_zone("dungeon_1", player, defeated_boss_ids={"goblin_king"})
    assert ok is False
    assert "Combat Level" in reason


def test_can_enter_zone_with_all_requirements():
    from entities.player import Player
    from systems.dungeon import can_enter_zone
    from core.constants import SkillType
    player = Player(name="Test")
    for sk in (SkillType.ATTACK, SkillType.DEFENSE, SkillType.STRENGTH):
        while player.skills.combat_level < 20:
            player.skills.add_xp(sk, 500_000)
    ok, reason = can_enter_zone("dungeon_1", player, defeated_boss_ids={"goblin_king"})
    assert ok is True, reason
