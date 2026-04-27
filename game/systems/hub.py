"""
Hub system — the player's persistent base between dungeon runs.

Responsibilities:
  - Track which buildings are built and at what upgrade level
  - Determine the hub's current phase (Camp → Outpost → Settlement → Village)
  - Process idle ticks: each built building produces resources + XP automatically
  - Gate building construction (skill level req + material cost)
  - Provide NPC slot tracking (future extension point)

Idle automation kicks in once a building exists, regardless of whether the
player is actively in the hub. The game loop calls `hub.tick()` each game tick.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from core.constants import SkillType
from core.events import bus, GameEvent
from data.hub_data import (
    HubBuilding, HUB_BUILDINGS, HUB_UPGRADE_MULTIPLIERS, HUB_PHASES,
)
from systems.gathering import GatheringEngine, GatherOutcome

EVT_BUILDING_BUILT = "building_built"
EVT_BUILDING_UPGRADED = "building_upgraded"
EVT_HUB_PHASE_CHANGE = "hub_phase_change"
EVT_IDLE_PRODUCE = "idle_produce"


@dataclass
class BuiltBuilding:
    building_id: str
    upgrade_level: int = 0          # 0 = base, max = building.upgrade_levels
    ticks_accumulated: int = 0      # ticks since last produce cycle

    @property
    def output_multiplier(self) -> float:
        idx = min(self.upgrade_level, len(HUB_UPGRADE_MULTIPLIERS) - 1)
        return HUB_UPGRADE_MULTIPLIERS[idx]


class Hub:
    """The player's persistent hub/base."""

    # Ticks between each idle produce cycle per building
    IDLE_PRODUCE_INTERVAL = 10

    def __init__(self, player):
        self._player = player
        self._buildings: dict[str, BuiltBuilding] = {}
        self._phase: str = "early"
        self._stored_resources: dict[str, int] = {}
        self._tick_count: int = 0

    # ─── Phase ────────────────────────────────────────────────────────────

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def phase_info(self) -> dict:
        return HUB_PHASES[self._phase]

    def _recalculate_phase(self) -> None:
        cb = self._player.skills.combat_level
        nb = len(self._buildings)
        new_phase = "early"
        for phase_id, data in reversed(list(HUB_PHASES.items())):
            if cb >= data["combat_level_req"] and nb >= data["buildings_req"]:
                new_phase = phase_id
                break
        if new_phase != self._phase:
            old = self._phase
            self._phase = new_phase
            bus.emit(GameEvent(EVT_HUB_PHASE_CHANGE, {
                "old_phase": old,
                "new_phase": new_phase,
                "name": HUB_PHASES[new_phase]["name"],
            }))

    # ─── Buildings ────────────────────────────────────────────────────────

    def can_build(self, building_id: str) -> tuple[bool, str]:
        """Returns (can_build, reason_if_not)."""
        defn = HUB_BUILDINGS.get(building_id)
        if not defn:
            return False, "Unknown building."
        if building_id in self._buildings:
            return False, "Already built."
        skill_level = self._player.skills.level(defn.skill)
        if skill_level < defn.skill_level_req:
            return False, (f"Need {defn.skill.value.capitalize()} "
                           f"level {defn.skill_level_req} (you have {skill_level}).")
        for item_id, qty in defn.build_cost.items():
            stored = self._stored_resources.get(item_id, 0)
            if stored < qty:
                return False, f"Need {qty}x {item_id} (have {stored})."
        return True, ""

    def build(self, building_id: str) -> dict:
        can, reason = self.can_build(building_id)
        if not can:
            return {"success": False, "reason": reason}
        defn = HUB_BUILDINGS[building_id]
        # Consume materials
        for item_id, qty in defn.build_cost.items():
            self._stored_resources[item_id] = (
                self._stored_resources.get(item_id, 0) - qty
            )
        self._buildings[building_id] = BuiltBuilding(building_id=building_id)
        self._recalculate_phase()
        bus.emit(GameEvent(EVT_BUILDING_BUILT, {
            "building": building_id,
            "name": defn.name,
            "message": defn.unlock_message,
        }))
        return {"success": True, "message": defn.unlock_message}

    def can_upgrade(self, building_id: str) -> tuple[bool, str]:
        built = self._buildings.get(building_id)
        if not built:
            return False, "Building not constructed."
        defn = HUB_BUILDINGS[building_id]
        if built.upgrade_level >= defn.upgrade_levels:
            return False, "Already at maximum upgrade level."
        cost = self._upgrade_cost(defn, built.upgrade_level + 1)
        for item_id, qty in cost.items():
            if self._stored_resources.get(item_id, 0) < qty:
                return False, f"Need {qty}x {item_id}."
        return True, ""

    def upgrade(self, building_id: str) -> dict:
        can, reason = self.can_upgrade(building_id)
        if not can:
            return {"success": False, "reason": reason}
        built = self._buildings[building_id]
        defn = HUB_BUILDINGS[building_id]
        cost = self._upgrade_cost(defn, built.upgrade_level + 1)
        for item_id, qty in cost.items():
            self._stored_resources[item_id] -= qty
        built.upgrade_level += 1
        bus.emit(GameEvent(EVT_BUILDING_UPGRADED, {
            "building": building_id,
            "new_level": built.upgrade_level,
        }))
        return {"success": True, "upgrade_level": built.upgrade_level}

    def _upgrade_cost(self, defn: HubBuilding, target_level: int) -> dict[str, int]:
        multiplier = target_level * 1.5
        return {k: int(v * multiplier) for k, v in defn.build_cost.items()}

    # ─── Resource storage ─────────────────────────────────────────────────

    def deposit(self, resource_id: str, quantity: int) -> None:
        self._stored_resources[resource_id] = (
            self._stored_resources.get(resource_id, 0) + quantity
        )

    def withdraw(self, resource_id: str, quantity: int) -> bool:
        stored = self._stored_resources.get(resource_id, 0)
        if stored < quantity:
            return False
        self._stored_resources[resource_id] = stored - quantity
        return True

    def storage(self) -> dict[str, int]:
        return {k: v for k, v in self._stored_resources.items() if v > 0}

    # ─── Idle tick ────────────────────────────────────────────────────────

    def tick(self, gathering_engine: GatheringEngine) -> list[GatherOutcome]:
        """
        Called once per game tick. Each built building accumulates ticks and
        produces resources every IDLE_PRODUCE_INTERVAL ticks.
        Returns list of outcomes for the UI to display.
        """
        self._tick_count += 1
        outcomes: list[GatherOutcome] = []

        for building_id, built in self._buildings.items():
            built.ticks_accumulated += 1
            if built.ticks_accumulated < self.IDLE_PRODUCE_INTERVAL:
                continue

            built.ticks_accumulated = 0
            defn = HUB_BUILDINGS[building_id]
            multiplier = built.output_multiplier

            # Determine what resource to produce
            resource_id = self._pick_idle_resource(defn.skill)
            if not resource_id:
                continue

            xp = int(defn.idle_xp_per_tick * multiplier)
            qty = max(1, int(defn.idle_resource_per_tick * multiplier))

            outcome = gathering_engine.idle_tick(defn.skill, resource_id, xp, qty)
            self.deposit(resource_id, qty)
            outcomes.append(outcome)

            bus.emit(GameEvent(EVT_IDLE_PRODUCE, {
                "building": building_id,
                "resource": resource_id,
                "quantity": qty,
                "xp": xp,
            }))

        return outcomes

    def _pick_idle_resource(self, skill: SkillType) -> str | None:
        """Pick the best resource the player can currently gather for this skill."""
        from data.resources import get_available_resources
        level = self._player.skills.level(skill)
        available = get_available_resources(skill, level)
        if not available:
            return None
        # Pick the highest tier available
        best = max(available, key=lambda r: r.level_req)
        return best.id

    # ─── Info / display ───────────────────────────────────────────────────

    def status(self) -> dict:
        return {
            "phase": self._phase,
            "phase_name": HUB_PHASES[self._phase]["name"],
            "buildings": {
                bid: {
                    "name": HUB_BUILDINGS[bid].name,
                    "upgrade_level": b.upgrade_level,
                    "skill": HUB_BUILDINGS[bid].skill.value,
                }
                for bid, b in self._buildings.items()
            },
            "storage": self.storage(),
            "tick": self._tick_count,
        }

    def available_to_build(self) -> list[str]:
        return [
            bid for bid in HUB_BUILDINGS
            if bid not in self._buildings
            and self._player.skills.level(HUB_BUILDINGS[bid].skill)
               >= HUB_BUILDINGS[bid].skill_level_req
        ]

    def __repr__(self) -> str:
        return (f"Hub(phase={self._phase!r}, "
                f"buildings={list(self._buildings.keys())})")
