import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from entities.player import Player
from data.items import WEAPONS
from systems.progression import ProgressionManager, ZoneStats, RunRecord
from systems.dungeon import DungeonRun, Room, RoomType


def make_player(cb_level: int = 1) -> Player:
    p = Player(name="Test")
    p.equipment.weapon = WEAPONS["bronze_sword"]
    if cb_level > 1:
        from core.constants import SkillType
        for sk in (SkillType.ATTACK, SkillType.DEFENSE, SkillType.STRENGTH):
            while p.skills.combat_level < cb_level:
                p.skills.add_xp(sk, 500_000)
    return p


def make_completed_run(zone: str, boss_completed: bool = False, died: bool = False) -> DungeonRun:
    rooms = [Room(room_type=RoomType.COMBAT, index=0, completed=True)]
    if boss_completed:
        rooms.append(Room(room_type=RoomType.BOSS, index=1, completed=True))
    run = DungeonRun(zone=zone, rooms=rooms)
    run.current_room_index = len(rooms)
    run.is_complete = not died
    run.player_died = died
    return run


# ─── Initial state ────────────────────────────────────────────────────────────

def test_progression_starts_empty():
    pm = ProgressionManager()
    assert pm.total_kills == 0
    assert pm.total_deaths == 0
    assert pm.defeated_bosses == set()


def test_global_stats_structure():
    pm = ProgressionManager()
    stats = pm.global_stats()
    assert "total_kills" in stats
    assert "total_deaths" in stats
    assert "defeated_bosses" in stats
    assert "zones_boss_cleared" in stats


# ─── Zone gating ──────────────────────────────────────────────────────────────

def test_can_enter_forest_always():
    pm = ProgressionManager()
    player = make_player()
    ok, _ = pm.can_enter("forest", player)
    assert ok is True


def test_cannot_enter_dungeon_1_without_boss():
    pm = ProgressionManager()
    player = make_player(cb_level=20)
    ok, reason = pm.can_enter("dungeon_1", player)
    assert ok is False
    assert "goblin" in reason.lower() or "defeat" in reason.lower()


def test_can_enter_dungeon_1_after_boss_kill():
    pm = ProgressionManager()
    pm.defeated_bosses.add("goblin_king")
    player = make_player(cb_level=20)
    ok, _ = pm.can_enter("dungeon_1", player)
    assert ok is True


def test_unlocked_zones_forest_only_at_start():
    pm = ProgressionManager()
    player = make_player()
    unlocked = pm.unlocked_zones(player)
    assert "forest" in unlocked
    assert "dungeon_1" not in unlocked


def test_locked_zones_has_reasons():
    pm = ProgressionManager()
    player = make_player()
    locked = pm.locked_zones(player)
    assert len(locked) >= 1
    for zone_id, reason in locked:
        assert isinstance(reason, str) and len(reason) > 0


# ─── Boss kills ───────────────────────────────────────────────────────────────

def test_record_boss_kill_adds_to_defeated():
    pm = ProgressionManager()
    pm.record_boss_kill("goblin_king", "forest")
    assert "goblin_king" in pm.defeated_bosses


def test_record_boss_kill_emits_zone_unlocked(monkeypatch):
    from core.events import bus
    events = []
    handler = lambda e: events.append(e)
    bus.subscribe("zone_unlocked", handler)
    pm = ProgressionManager()
    pm.record_boss_kill("goblin_king", "forest")
    bus.unsubscribe("zone_unlocked", handler)
    assert any(e.data.get("boss_id") == "goblin_king" for e in events)


def test_record_boss_kill_updates_zone_boss_killed():
    pm = ProgressionManager()
    pm.record_boss_kill("goblin_king", "forest")
    assert pm.zone_stats("forest").boss_killed is True


def test_total_boss_kills_increments():
    pm = ProgressionManager()
    pm.record_boss_kill("goblin_king", "forest")
    pm.record_boss_kill("grondar", "raid")
    assert pm.total_boss_kills == 2


# ─── Kill tracking ────────────────────────────────────────────────────────────

def test_record_kill_increments_total():
    pm = ProgressionManager()
    pm.record_kill("forest", count=5)
    assert pm.total_kills == 5


def test_record_kill_increments_zone_kills():
    pm = ProgressionManager()
    pm.record_kill("forest", count=3)
    pm.record_kill("dungeon_1", count=2)
    assert pm.zone_stats("forest").kills_in_zone == 3
    assert pm.zone_stats("dungeon_1").kills_in_zone == 2


def test_kill_milestone_emits_event(monkeypatch):
    from core.events import bus
    milestones = []
    handler = lambda e: milestones.append(e.data["milestone"])
    bus.subscribe("milestone_kills", handler)
    pm = ProgressionManager()
    pm.record_kill("forest", count=10)
    bus.unsubscribe("milestone_kills", handler)
    assert 10 in milestones


# ─── Run lifecycle ────────────────────────────────────────────────────────────

def test_record_run_start_increments_attempted():
    pm = ProgressionManager()
    pm.record_run_start("forest")
    assert pm.zone_stats("forest").runs_attempted == 1


def test_finalize_completed_run_increments_completed():
    pm = ProgressionManager()
    run = make_completed_run("forest", boss_completed=False)
    pm.finalize_run(run)
    assert pm.zone_stats("forest").runs_completed == 1


def test_finalize_death_increments_deaths():
    pm = ProgressionManager()
    run = make_completed_run("forest", died=True)
    pm.finalize_run(run)
    assert pm.total_deaths == 1
    assert pm.zone_stats("forest").deaths_in_zone == 1


def test_finalize_updates_best_rooms():
    pm = ProgressionManager()
    run = make_completed_run("forest")
    pm.finalize_run(run)
    assert pm.zone_stats("forest").best_rooms_cleared >= 1


def test_finalize_tracks_gold():
    pm = ProgressionManager()
    run = make_completed_run("forest")
    pm.finalize_run(run, gold_earned=50)
    assert pm.total_gold_earned == 50


# ─── Run history ──────────────────────────────────────────────────────────────

def test_run_history_stores_records():
    pm = ProgressionManager()
    pm.finalize_run(make_completed_run("forest"))
    pm.finalize_run(make_completed_run("forest"))
    assert len(pm.run_history()) == 2


def test_run_history_filtered_by_zone():
    pm = ProgressionManager()
    pm.finalize_run(make_completed_run("forest"))
    pm.finalize_run(make_completed_run("dungeon_1"))
    assert len(pm.run_history("forest")) == 1
    assert len(pm.run_history("dungeon_1")) == 1


# ─── Serialisation ────────────────────────────────────────────────────────────

def test_to_dict_round_trips():
    pm = ProgressionManager()
    pm.record_boss_kill("goblin_king", "forest")
    pm.record_kill("forest", count=7)
    pm.finalize_run(make_completed_run("forest"), gold_earned=20)

    data = pm.to_dict()
    pm2 = ProgressionManager.from_dict(data)

    assert pm2.total_kills == pm.total_kills
    assert pm2.total_boss_kills == pm.total_boss_kills
    assert "goblin_king" in pm2.defeated_bosses
    assert pm2.total_gold_earned == 20
    assert len(pm2.run_history()) == 1


def test_from_dict_empty_data():
    pm = ProgressionManager.from_dict({})
    assert pm.total_kills == 0
    assert pm.defeated_bosses == set()


# ─── Summary ─────────────────────────────────────────────────────────────────

def test_summary_string():
    pm = ProgressionManager()
    pm.record_kill("forest", 5)
    s = pm.summary()
    assert "Kills" in s
    assert "Deaths" in s
