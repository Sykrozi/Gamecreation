import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from systems.bestiary import Bestiary, BestiaryEntry, STUDY_THRESHOLD
from data.monsters import MONSTERS, BOSSES


# ─── BestiaryEntry ────────────────────────────────────────────────────────────

def test_entry_starts_undiscovered():
    entry = BestiaryEntry("goblin", "Goblin", "A small green monster.")
    assert entry.is_discovered is False
    assert entry.is_studied is False
    assert entry.kill_count == 0


def test_record_kill_discovers_entry():
    entry = BestiaryEntry("goblin", "Goblin", "")
    newly_discovered, newly_studied = entry.record_kill("forest")
    assert entry.is_discovered is True
    assert newly_discovered is True
    assert entry.kill_count == 1


def test_record_kill_not_studied_below_threshold():
    entry = BestiaryEntry("goblin", "Goblin", "")
    for _ in range(STUDY_THRESHOLD - 1):
        entry.record_kill("forest")
    assert entry.is_studied is False


def test_record_kill_studied_at_threshold():
    entry = BestiaryEntry("goblin", "Goblin", "")
    newly_studied = False
    for _ in range(STUDY_THRESHOLD):
        _, ns = entry.record_kill("forest")
        if ns:
            newly_studied = True
    assert entry.is_studied is True
    assert newly_studied is True


def test_kills_to_study_decrements():
    entry = BestiaryEntry("goblin", "Goblin", "")
    entry.record_kill("forest")
    assert entry.kills_to_study == STUDY_THRESHOLD - 1


def test_zones_seen_accumulates():
    entry = BestiaryEntry("goblin", "Goblin", "")
    entry.record_kill("forest")
    entry.record_kill("swamp")
    entry.record_kill("forest")
    assert "forest" in entry.zones_seen
    assert "swamp" in entry.zones_seen
    assert entry.zones_seen.count("forest") == 1   # no duplicates


def test_weakness_summary_none_before_studied():
    entry = BestiaryEntry("goblin", "Goblin", "")
    assert entry.weakness_summary() is None


def test_weakness_summary_after_studied():
    entry = BestiaryEntry("goblin", "Goblin", "")
    entry.is_studied = True
    summary = entry.weakness_summary()
    assert summary is not None   # may be "None" string if no weaknesses, but not Python None


# ─── Bestiary class ───────────────────────────────────────────────────────────

def test_bestiary_empty_on_init():
    b = Bestiary()
    assert b.all_entries() == []
    assert b.total_kills() == 0


def test_record_kill_creates_entry():
    b = Bestiary()
    entry = b.record_kill("goblin", "forest")
    assert entry is not None
    assert entry.monster_id == "goblin"
    assert entry.kill_count == 1


def test_record_kill_uses_real_monster_name():
    b = Bestiary()
    entry = b.record_kill("goblin", "forest")
    assert entry.name == MONSTERS["goblin"].name


def test_record_boss_kill_flagged():
    b = Bestiary()
    entry = b.record_kill("goblin_king", "forest")
    assert entry.is_boss is True


def test_record_normal_kill_not_flagged_as_boss():
    b = Bestiary()
    entry = b.record_kill("goblin", "forest")
    assert entry.is_boss is False


def test_total_kills_across_monsters():
    b = Bestiary()
    b.record_kill("goblin", "forest")
    b.record_kill("goblin", "forest")
    b.record_kill("skeleton_archer", "dungeon_1")
    assert b.total_kills() == 3


def test_get_returns_none_for_unknown():
    b = Bestiary()
    assert b.get("dragon") is None


def test_get_returns_entry_after_kill():
    b = Bestiary()
    b.record_kill("goblin", "forest")
    entry = b.get("goblin")
    assert entry is not None
    assert entry.kill_count == 1


def test_discover_without_kill():
    b = Bestiary()
    entry = b.discover("forest_boar")
    assert entry.is_discovered is True
    assert entry.kill_count == 0


def test_discovered_entries_filtered():
    b = Bestiary()
    b.discover("goblin")
    b.discover("forest_boar")
    discovered = b.discovered_entries()
    ids = [e.monster_id for e in discovered]
    assert "goblin" in ids
    assert "forest_boar" in ids


def test_studied_entries_empty_below_threshold():
    b = Bestiary()
    for _ in range(STUDY_THRESHOLD - 1):
        b.record_kill("goblin", "forest")
    assert b.studied_entries() == []


def test_studied_entries_after_threshold():
    b = Bestiary()
    for _ in range(STUDY_THRESHOLD):
        b.record_kill("goblin", "forest")
    studied = b.studied_entries()
    assert any(e.monster_id == "goblin" for e in studied)


def test_completion_stats_structure():
    b = Bestiary()
    stats = b.completion_stats()
    assert "total" in stats
    assert "discovered" in stats
    assert "studied" in stats
    assert stats["total"] > 0


def test_completion_stats_increments_on_kill():
    b = Bestiary()
    before = b.completion_stats()["discovered"]
    b.record_kill("goblin", "forest")
    after = b.completion_stats()["discovered"]
    assert after == before + 1


def test_summary_string():
    b = Bestiary()
    s = b.summary()
    assert "Bestiary" in s
    assert "discovered" in s


def test_lore_populated_for_known_monster():
    b = Bestiary()
    entry = b._get_or_create("goblin")
    assert len(entry.lore) > 10


def test_lore_fallback_for_unknown_monster():
    b = Bestiary()
    entry = b._get_or_create("mystery_beast_xyz")
    assert entry.lore != ""
