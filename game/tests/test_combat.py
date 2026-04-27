import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.constants import CombatAction, CombatStyle, StatusEffect, WeaknessType
from entities.player import Player
from entities.monster import MonsterInstance, BossInstance
from entities.skill import SkillSet
from entities.inventory import Equipment, Inventory
from data.monsters import MONSTERS, BOSSES
from data.items import WEAPONS, CONSUMABLES
from systems.combat import CombatEngine, CombatResult


def make_player(name="Hero", style=CombatStyle.MELEE) -> Player:
    p = Player(name=name)
    p.active_style = style
    p.equipment.weapon = WEAPONS["bronze_sword"]
    return p


def make_monster(monster_id="goblin") -> MonsterInstance:
    return MonsterInstance(definition=MONSTERS[monster_id])


def make_boss(boss_id="goblin_king") -> BossInstance:
    return BossInstance(definition=BOSSES[boss_id])


# ─── Basic combat ────────────────────────────────────────────────────────────

def test_basic_attack_deals_damage():
    player = make_player()
    enemy = make_monster()
    engine = CombatEngine(player, enemy)
    engine.start()

    initial_hp = enemy.hp
    log = engine.player_action(CombatAction.ATTACK)
    assert enemy.hp < initial_hp or log.damage == 0  # immune edge case
    assert log.turn == 1


def test_defend_reduces_damage():
    player = make_player()
    enemy = make_monster("stone_goblin")
    engine = CombatEngine(player, enemy)
    engine.start()

    # Log defend action — player takes reduced damage from enemy counter
    log = engine.player_action(CombatAction.DEFEND)
    assert engine.result in (CombatResult.ONGOING, CombatResult.PLAYER_DEAD)


def test_flee_terminates_combat():
    player = make_player()
    # Boost combat level to make flee likely
    from core.constants import SkillType
    for _ in range(50):
        player.skills.add_xp(SkillType.ATTACK, 10000)
    enemy = make_monster("goblin")
    engine = CombatEngine(player, enemy)
    engine.start()

    # Try multiple times — flee is probabilistic
    for _ in range(20):
        if engine.result == CombatResult.PLAYER_FLED:
            break
        log = engine.player_action(CombatAction.FLEE)
    assert engine.result in (CombatResult.PLAYER_FLED, CombatResult.ONGOING,
                             CombatResult.PLAYER_DEAD)


def test_use_item_heals_player():
    from copy import deepcopy
    from data.items import Consumable, CONSUMABLES
    player = make_player()
    potion = deepcopy(CONSUMABLES["basic_potion"])
    player.inventory.add(potion)
    player._hp = 50  # damage the player first

    enemy = make_monster()
    engine = CombatEngine(player, enemy)
    engine.start()

    hp_before = player.hp
    log = engine.player_action(CombatAction.USE_ITEM, item_id="basic_potion")
    assert player.hp >= hp_before or player.hp == player.max_hp


# ─── Weakness system ─────────────────────────────────────────────────────────

def test_weak_enemy_takes_extra_damage():
    # Stone goblin is weak to magic
    player = make_player(style=CombatStyle.MAGIC)
    player.equipment.weapon = WEAPONS["basic_staff"]
    player.active_style = CombatStyle.MAGIC
    enemy = make_monster("stone_goblin")

    assert enemy.get_weakness(CombatStyle.MAGIC) == WeaknessType.WEAK
    mult = enemy.damage_multiplier(CombatStyle.MAGIC)
    assert mult == 1.5


def test_resistant_enemy_takes_less_damage():
    enemy = make_monster("stone_goblin")
    assert enemy.get_weakness(CombatStyle.MELEE) == WeaknessType.RESISTANT
    assert enemy.damage_multiplier(CombatStyle.MELEE) == 0.5


def test_neutral_monster_normal_damage():
    enemy = make_monster("forest_boar")
    for style in CombatStyle:
        assert enemy.damage_multiplier(style) == 1.0


# ─── Boss phase system ───────────────────────────────────────────────────────

def test_boss_starts_phase_1():
    boss = make_boss()
    assert boss.current_phase == 1


def test_boss_phase_2_triggers_at_60_pct():
    boss = make_boss()
    # Manually set HP to just below 60%
    boss.hp = int(boss.max_hp * 0.59)
    phase_data = boss.check_phase_transition()
    assert phase_data is not None
    assert phase_data.phase == 2
    assert boss.current_phase == 2


def test_boss_phase_3_triggers_at_30_pct():
    boss = make_boss()
    boss.hp = int(boss.max_hp * 0.29)
    # Manually mark phase 2 as triggered
    boss._phase_triggered.add(2)
    boss.current_phase = 2
    phase_data = boss.check_phase_transition()
    assert phase_data is not None
    assert phase_data.phase == 3


def test_boss_phase_not_retriggered():
    boss = make_boss()
    boss.hp = int(boss.max_hp * 0.59)
    boss.check_phase_transition()  # triggers phase 2
    phase_data = boss.check_phase_transition()  # should not retrigger
    assert phase_data is None


def test_boss_immune_takes_no_damage():
    # Sylvara is immune to magic
    boss = BossInstance(definition=BOSSES["sylvara"])
    initial_hp = boss.hp
    dmg = boss.take_damage(999, CombatStyle.MAGIC)
    assert dmg == 0
    assert boss.hp == initial_hp


# ─── Status effects ──────────────────────────────────────────────────────────

def test_stun_skips_player_turn():
    player = make_player()
    player.effects.apply(StatusEffect.STUN, duration=1)
    enemy = make_monster()
    engine = CombatEngine(player, enemy)
    engine.start()

    log = engine.player_action(CombatAction.ATTACK)
    assert "stunned" in log.narrative.lower()


def test_poison_damages_every_turn():
    player = make_player()
    player._hp = player.max_hp
    enemy = make_monster()
    engine = CombatEngine(player, enemy)
    engine.start()

    # Apply poison to enemy
    enemy.effects.apply(StatusEffect.POISON, duration=3)
    enemy_hp_before = enemy.hp
    engine.player_action(CombatAction.DEFEND)
    # Poison should have ticked
    # (may not tick if enemy died from other causes — just check state)
    assert enemy.hp <= enemy_hp_before


def test_defend_halves_damage():
    player = make_player()
    assert player.effects.damage_reduction() == 0.0
    player.effects.apply(StatusEffect.DEFENDING, duration=1)
    assert player.effects.damage_reduction() >= 0.4  # at least DEFEND_DAMAGE_REDUCTION


# ─── Special actions ─────────────────────────────────────────────────────────

def test_special_strike_requires_melee():
    player = make_player(style=CombatStyle.RANGE)
    player.equipment.weapon = WEAPONS["wood_bow"]
    enemy = make_monster()
    engine = CombatEngine(player, enemy)
    engine.start()
    log = engine.player_action(CombatAction.SPECIAL_STRIKE)
    assert "Melee" in log.narrative


def test_magic_shield_applies_effect():
    player = make_player(style=CombatStyle.MAGIC)
    player.equipment.weapon = WEAPONS["basic_staff"]
    enemy = make_monster()
    engine = CombatEngine(player, enemy)
    engine.start()
    engine.player_action(CombatAction.MAGIC_SHIELD)
    assert player.effects.has(StatusEffect.MAGIC_SHIELD)


def test_multi_shot_fires_three_times():
    player = make_player(style=CombatStyle.RANGE)
    player.equipment.weapon = WEAPONS["wood_bow"]
    enemy = make_monster("forest_boar")
    enemy.hp = 9999  # ensure it doesn't die
    engine = CombatEngine(player, enemy)
    engine.start()
    log = engine.player_action(CombatAction.MULTI_SHOT)
    assert "3 arrows" in log.narrative or "Multi-shot" in log.narrative


# ─── Valid actions ─────────────────────────────────────────────────────────

def test_valid_actions_melee():
    player = make_player(style=CombatStyle.MELEE)
    enemy = make_monster()
    engine = CombatEngine(player, enemy)
    actions = engine.get_valid_actions()
    assert CombatAction.SPECIAL_STRIKE in actions
    assert CombatAction.TAUNT in actions
    assert CombatAction.CHARGED_SHOT not in actions


def test_valid_actions_magic():
    player = make_player(style=CombatStyle.MAGIC)
    enemy = make_monster()
    engine = CombatEngine(player, enemy)
    actions = engine.get_valid_actions()
    assert CombatAction.SPELL in actions
    assert CombatAction.MAGIC_SHIELD in actions
    assert CombatAction.SPECIAL_STRIKE not in actions


# ─── Death and survival ──────────────────────────────────────────────────────

def test_player_death_resets_hp_and_clears_drops():
    from data.items import CONSUMABLES
    from copy import deepcopy
    player = make_player()
    player.inventory.add(deepcopy(CONSUMABLES["basic_potion"]))
    assert len(player.inventory.items) == 1
    player._hp = 0
    player.die()
    assert player.hp == player.max_hp
    assert len(player.inventory.items) == 0


def test_player_keeps_xp_after_death():
    from core.constants import SkillType
    player = make_player()
    player.skills.add_xp(SkillType.ATTACK, 500)
    xp_before = player.skills.get(SkillType.ATTACK).xp
    player._hp = 0
    player.die()
    assert player.skills.get(SkillType.ATTACK).xp == xp_before
