import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from entities.player import Player
from data.items import WEAPONS
from systems.dungeon import DungeonRunner, DungeonGenerator, RoomType
from core.constants import CombatStyle


def make_player() -> Player:
    p = Player(name="Tester")
    p.equipment.weapon = WEAPONS["bronze_sword"]
    return p


def test_dungeon_always_ends_with_boss():
    gen = DungeonGenerator()
    run = gen.generate("forest")
    assert run.rooms[-1].room_type == RoomType.BOSS


def test_dungeon_has_exactly_one_skill_room():
    gen = DungeonGenerator()
    run = gen.generate("forest")
    skill_rooms = [r for r in run.rooms if r.room_type == RoomType.SKILL]
    assert len(skill_rooms) == 1


def test_dungeon_has_combat_rooms():
    gen = DungeonGenerator()
    run = gen.generate("forest")
    combat_rooms = [r for r in run.rooms if r.room_type == RoomType.COMBAT]
    assert len(combat_rooms) >= 1


def test_dungeon_runner_initializes():
    player = make_player()
    runner = DungeonRunner(player, "forest")
    assert runner.run.total_rooms > 0
    assert not runner.run.is_complete


def test_enter_room_returns_info():
    player = make_player()
    runner = DungeonRunner(player, "forest")
    info = runner.enter_current_room()
    assert "type" in info


def test_skill_room_advance_on_success():
    gen = DungeonGenerator()
    run = gen.generate("forest")
    player = make_player()

    from systems.dungeon import DungeonRunner
    runner = DungeonRunner.__new__(DungeonRunner)
    runner.player = player
    runner.zone = "forest"
    runner.run = run

    # Find the skill room and navigate to it
    original_idx = run.current_room_index
    for i, room in enumerate(run.rooms):
        if room.room_type == RoomType.SKILL:
            run.current_room_index = i
            break

    result = runner.complete_skill_room(success=True)
    assert result.get("success") is True
    assert run.rooms[run.current_room_index - 1].completed is True


def test_skill_room_blocks_on_failure():
    gen = DungeonGenerator()
    run = gen.generate("forest")
    player = make_player()

    from systems.dungeon import DungeonRunner
    runner = DungeonRunner.__new__(DungeonRunner)
    runner.player = player
    runner.zone = "forest"
    runner.run = run

    for i, room in enumerate(run.rooms):
        if room.room_type == RoomType.SKILL:
            run.current_room_index = i
            break

    result = runner.complete_skill_room(success=False)
    assert result.get("blocked") is True


def test_loot_room_gives_drops():
    gen = DungeonGenerator()
    player = make_player()

    from systems.dungeon import DungeonRunner, Room, RoomType
    from data.monsters import Drop
    runner = DungeonRunner.__new__(DungeonRunner)
    runner.player = player
    runner.zone = "forest"

    from systems.dungeon import DungeonRun
    loot_room = Room(room_type=RoomType.LOOT, index=0, loot=[
        Drop(item_id="basic_potion", chance=1.0, quantity_min=1, quantity_max=1),
    ])
    runner.run = DungeonRun(zone="forest", rooms=[loot_room])
    result = runner.collect_loot_room()
    assert "drops" in result
    assert any(d["item_id"] == "basic_potion" for d in result["drops"])


def test_combat_engine_starts_from_runner():
    player = make_player()
    runner = DungeonRunner(player, "forest")

    # Navigate to first combat room
    for i, room in enumerate(runner.run.rooms):
        if room.room_type == RoomType.COMBAT and room.monster:
            runner.run.current_room_index = i
            break

    engine = runner.start_combat()
    assert engine is not None
    assert engine.result.name == "ONGOING"
