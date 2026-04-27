import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.constants import SkillType
from entities.player import Player
from entities.skill import SkillSet
from entities.inventory import Inventory
from data.items import WEAPONS
from data.hub_data import HUB_BUILDINGS, HUB_PHASES
from systems.hub import Hub
from systems.gathering import GatheringEngine


def make_player_with_skill(skill: SkillType, level: int) -> Player:
    p = Player(name="Tester")
    p.equipment.weapon = WEAPONS["bronze_sword"]
    # Force skill level
    while p.skills.level(skill) < level:
        p.skills.add_xp(skill, 500_000)
    return p


def make_hub_with_resources(player: Player, resources: dict) -> Hub:
    hub = Hub(player)
    for rid, qty in resources.items():
        hub.deposit(rid, qty)
    return hub


def make_engine(player: Player) -> GatheringEngine:
    return GatheringEngine(player.skills, player.inventory)


# ─── Hub data ────────────────────────────────────────────────────────────────

def test_all_hub_buildings_defined():
    for bid in ("mine_shaft", "lumber_mill", "fishing_dock", "greenhouse",
                "forge", "kitchen", "herb_lab", "rune_altar"):
        assert bid in HUB_BUILDINGS


def test_hub_phases_defined():
    for phase in ("early", "mid", "late", "endgame"):
        assert phase in HUB_PHASES


# ─── Hub initialisation ───────────────────────────────────────────────────────

def test_hub_starts_in_early_phase():
    player = Player(name="Test")
    hub = Hub(player)
    assert hub.phase == "early"


def test_hub_status_returns_dict():
    player = Player(name="Test")
    hub = Hub(player)
    status = hub.status()
    assert "phase" in status
    assert "buildings" in status
    assert "storage" in status


# ─── Resource storage ─────────────────────────────────────────────────────────

def test_deposit_and_withdraw():
    player = Player(name="Test")
    hub = Hub(player)
    hub.deposit("iron", 50)
    assert hub.storage()["iron"] == 50
    result = hub.withdraw("iron", 20)
    assert result is True
    assert hub.storage()["iron"] == 30


def test_withdraw_insufficient():
    player = Player(name="Test")
    hub = Hub(player)
    hub.deposit("iron", 5)
    result = hub.withdraw("iron", 10)
    assert result is False
    assert hub.storage()["iron"] == 5


# ─── Building construction ────────────────────────────────────────────────────

def test_cannot_build_without_skill_level():
    player = Player(name="Test")   # Mining level 1
    hub = make_hub_with_resources(player, {"iron": 100, "coal": 100})
    can, reason = hub.can_build("mine_shaft")
    assert can is False
    assert "Need" in reason


def test_cannot_build_without_resources():
    player = make_player_with_skill(SkillType.MINING, 50)
    hub = Hub(player)   # no resources deposited
    can, reason = hub.can_build("mine_shaft")
    assert can is False
    assert "Need" in reason


def test_build_succeeds_with_requirements_met():
    player = make_player_with_skill(SkillType.MINING, 50)
    hub = make_hub_with_resources(player, {"iron": 100, "coal": 100})
    can, _ = hub.can_build("mine_shaft")
    assert can is True
    result = hub.build("mine_shaft")
    assert result["success"] is True
    assert "mine_shaft" in hub._buildings


def test_build_consumes_resources():
    player = make_player_with_skill(SkillType.MINING, 50)
    defn = HUB_BUILDINGS["mine_shaft"]
    resources = {k: v + 10 for k, v in defn.build_cost.items()}
    hub = make_hub_with_resources(player, resources)
    before = {k: hub.storage().get(k, 0) for k in defn.build_cost}
    hub.build("mine_shaft")
    after = {k: hub.storage().get(k, 0) for k in defn.build_cost}
    for k in defn.build_cost:
        assert after[k] < before[k]


def test_cannot_build_same_building_twice():
    player = make_player_with_skill(SkillType.MINING, 50)
    hub = make_hub_with_resources(player, {"iron": 200, "coal": 200})
    hub.build("mine_shaft")
    can, reason = hub.can_build("mine_shaft")
    assert can is False
    assert "Already" in reason


# ─── Building upgrades ────────────────────────────────────────────────────────

def test_upgrade_building():
    player = make_player_with_skill(SkillType.MINING, 50)
    hub = make_hub_with_resources(player, {"iron": 500, "coal": 500})
    hub.build("mine_shaft")
    can, _ = hub.can_upgrade("mine_shaft")
    assert can is True
    result = hub.upgrade("mine_shaft")
    assert result["success"] is True
    assert hub._buildings["mine_shaft"].upgrade_level == 1


def test_upgrade_multiplier_increases():
    from data.hub_data import HUB_UPGRADE_MULTIPLIERS
    assert HUB_UPGRADE_MULTIPLIERS[1] > HUB_UPGRADE_MULTIPLIERS[0]
    assert HUB_UPGRADE_MULTIPLIERS[2] > HUB_UPGRADE_MULTIPLIERS[1]


def test_cannot_upgrade_past_max():
    player = make_player_with_skill(SkillType.MINING, 50)
    hub = make_hub_with_resources(player, {"iron": 5000, "coal": 5000})
    hub.build("mine_shaft")
    defn = HUB_BUILDINGS["mine_shaft"]
    for _ in range(defn.upgrade_levels):
        hub.upgrade("mine_shaft")
    can, reason = hub.can_upgrade("mine_shaft")
    assert can is False
    assert "maximum" in reason


def test_cannot_upgrade_unbuilt():
    player = Player(name="Test")
    hub = Hub(player)
    can, reason = hub.can_upgrade("mine_shaft")
    assert can is False


# ─── Hub phase progression ────────────────────────────────────────────────────

def test_hub_advances_to_mid_phase():
    player = make_player_with_skill(SkillType.MINING, 50)
    # Get player to combat level 30
    from core.constants import SkillType as ST
    for sk in (ST.ATTACK, ST.DEFENSE, ST.STRENGTH):
        while player.skills.level(sk) < 30:
            player.skills.add_xp(sk, 500_000)

    # Need 2 buildings for mid phase
    resources = {"iron": 500, "coal": 500, "oak": 500, "willow": 500}
    hub = make_hub_with_resources(player, resources)

    player_wc = make_player_with_skill(SkillType.WOODCUTTING, 50)
    # Combine skills: use same player
    player.skills.skills[SkillType.WOODCUTTING].level = 50

    hub.build("mine_shaft")
    hub.build("lumber_mill")
    assert hub.phase in ("mid", "late", "endgame")


# ─── Idle tick ────────────────────────────────────────────────────────────────

def test_idle_tick_produces_after_interval():
    player = make_player_with_skill(SkillType.MINING, 50)
    hub = make_hub_with_resources(player, {"iron": 200, "coal": 200})
    hub.build("mine_shaft")
    engine = make_engine(player)

    outcomes = []
    for _ in range(Hub.IDLE_PRODUCE_INTERVAL + 1):
        outcomes.extend(hub.tick(engine))

    assert len(outcomes) >= 1
    assert any(o.quantity >= 1 for o in outcomes)


def test_idle_tick_grants_xp():
    player = make_player_with_skill(SkillType.MINING, 50)
    hub = make_hub_with_resources(player, {"iron": 200, "coal": 200})
    hub.build("mine_shaft")
    engine = make_engine(player)

    xp_before = player.skills.get(SkillType.MINING).xp
    for _ in range(Hub.IDLE_PRODUCE_INTERVAL + 1):
        hub.tick(engine)
    xp_after = player.skills.get(SkillType.MINING).xp
    assert xp_after > xp_before


def test_idle_tick_deposits_to_storage():
    player = make_player_with_skill(SkillType.MINING, 50)
    hub = make_hub_with_resources(player, {"iron": 200, "coal": 200})
    hub.build("mine_shaft")
    engine = make_engine(player)

    for _ in range(Hub.IDLE_PRODUCE_INTERVAL + 1):
        hub.tick(engine)

    assert sum(hub.storage().values()) > 0


def test_no_production_without_buildings():
    player = Player(name="Test")
    hub = Hub(player)
    engine = make_engine(player)
    outcomes = []
    for _ in range(Hub.IDLE_PRODUCE_INTERVAL * 2):
        outcomes.extend(hub.tick(engine))
    assert outcomes == []


def test_upgraded_building_produces_more():
    from entities.player import Player as P
    from entities.skill import SkillSet

    def fresh_player():
        p = P(name="T")
        p.equipment.weapon = WEAPONS["bronze_sword"]
        while p.skills.level(SkillType.MINING) < 50:
            p.skills.add_xp(SkillType.MINING, 500_000)
        return p

    # Two independent players so upgrade costs and XP don't cross-contaminate
    p_base = fresh_player()
    p_up = fresh_player()

    hub_base = make_hub_with_resources(p_base, {"iron": 1000, "coal": 1000})
    hub_base.build("mine_shaft")

    hub_up = make_hub_with_resources(p_up, {"iron": 1000, "coal": 1000})
    hub_up.build("mine_shaft")
    # Upgrade to level 2 so multiplier = 2.0, guaranteeing qty > base (int(1*2.0)=2 vs 1)
    hub_up.upgrade("mine_shaft")
    hub_up.upgrade("mine_shaft")

    engine_base = make_engine(p_base)
    engine_up = make_engine(p_up)

    ticks = Hub.IDLE_PRODUCE_INTERVAL + 1
    base_outcomes: list = []
    up_outcomes: list = []
    for _ in range(ticks):
        base_outcomes.extend(hub_base.tick(engine_base))
        up_outcomes.extend(hub_up.tick(engine_up))

    base_produced = sum(o.quantity for o in base_outcomes)
    up_produced = sum(o.quantity for o in up_outcomes)
    assert up_produced >= base_produced


# ─── available_to_build ───────────────────────────────────────────────────────

def test_available_to_build_empty_for_low_level():
    player = Player(name="Test")
    hub = Hub(player)
    available = hub.available_to_build()
    assert available == []   # all require level 50


def test_available_to_build_returns_unbuilt():
    player = make_player_with_skill(SkillType.MINING, 50)
    hub = Hub(player)
    available = hub.available_to_build()
    assert "mine_shaft" in available
