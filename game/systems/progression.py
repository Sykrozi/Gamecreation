"""
Progression manager — tracks all player milestones across dungeon runs.

Persisted as a plain dict (JSON-serialisable) so the save system can write
it to disk without importing game classes.

Core responsibilities:
  - Record boss kills → gates zone unlock for future runs
  - Record run outcomes (complete / death / abandon)
  - Emit milestone events (kill counts, zone clears, deaths)
  - Expose unlock-gated zone list
  - Serialise / deserialise for save files
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.events import bus, GameEvent

if TYPE_CHECKING:
    from entities.player import Player
    from systems.dungeon import DungeonRun

EVT_ZONE_UNLOCKED       = "zone_unlocked"
EVT_MILESTONE_KILLS     = "milestone_kills"
EVT_MILESTONE_DEATHS    = "milestone_deaths"
EVT_MILESTONE_CLEARS    = "milestone_clears"

_KILL_MILESTONES   = (10, 50, 100, 250, 500, 1000, 5000)
_DEATH_MILESTONES  = (1, 5, 10, 25, 50, 100)
_CLEAR_MILESTONES  = (1, 5, 10, 25, 50)


@dataclass
class ZoneStats:
    zone_id: str
    runs_attempted: int = 0
    runs_completed: int = 0
    boss_killed: bool = False
    kills_in_zone: int = 0
    best_rooms_cleared: int = 0
    deaths_in_zone: int = 0


@dataclass
class RunRecord:
    zone_id: str
    rooms_cleared: int
    boss_killed: bool
    player_died: bool
    drops_count: int
    gold_earned: int
    currency_earned: int = 0


class ProgressionManager:
    """
    Attached to the player's save file. Persistent across sessions.

    Example integration with DungeonRunner:

        pm = ProgressionManager()
        runner = DungeonRunner(player, "forest", progression=pm)
        # pm is updated automatically during the run
        # After run ends:
        pm.finalize_run(runner.run, gold_earned=..., currency_earned=...)
    """

    def __init__(self) -> None:
        self.defeated_bosses: set[str] = set()
        self._zone_stats: dict[str, ZoneStats] = {}
        self._run_history: list[RunRecord] = []
        self.total_kills: int = 0
        self.total_deaths: int = 0
        self.total_gold_earned: int = 0
        self.total_currency_earned: int = 0
        self.total_boss_kills: int = 0

    # ─── Zone gating ──────────────────────────────────────────────────────

    def can_enter(self, zone_id: str, player: "Player") -> tuple[bool, str]:
        from systems.dungeon import can_enter_zone
        return can_enter_zone(zone_id, player, self.defeated_bosses)

    def unlocked_zones(self, player: "Player") -> list[str]:
        from data.zones import ZONES
        return [zid for zid in ZONES if self.can_enter(zid, player)[0]]

    def locked_zones(self, player: "Player") -> list[tuple[str, str]]:
        """Returns list of (zone_id, reason) for zones not yet accessible."""
        from data.zones import ZONES
        result = []
        for zid in ZONES:
            ok, reason = self.can_enter(zid, player)
            if not ok:
                result.append((zid, reason))
        return result

    # ─── Recording events ─────────────────────────────────────────────────

    def record_run_start(self, zone_id: str) -> None:
        self._get_zone(zone_id).runs_attempted += 1

    def record_boss_kill(self, boss_id: str, zone_id: str) -> list[str]:
        """
        Register a boss kill. Returns list of newly-unlocked zone IDs.
        Emits EVT_ZONE_UNLOCKED for each newly available zone.
        """
        self.defeated_bosses.add(boss_id)
        self.total_boss_kills += 1
        stats = self._get_zone(zone_id)
        stats.boss_killed = True

        from data.zones import ZONES
        newly_unlocked: list[str] = []
        for zid, zone in ZONES.items():
            if zone.unlock.previous_boss_id == boss_id:
                newly_unlocked.append(zid)
                bus.emit(GameEvent(EVT_ZONE_UNLOCKED, {
                    "zone_id": zid,
                    "zone_name": zone.name,
                    "boss_id": boss_id,
                }))
        return newly_unlocked

    def record_kill(self, zone_id: str, count: int = 1) -> None:
        self._get_zone(zone_id).kills_in_zone += count
        prev = self.total_kills
        self.total_kills += count
        for m in _KILL_MILESTONES:
            if prev < m <= self.total_kills:
                bus.emit(GameEvent(EVT_MILESTONE_KILLS, {
                    "milestone": m,
                    "message": f"You have slain {m} enemies!",
                }))

    def record_death(self, zone_id: str) -> None:
        self._get_zone(zone_id).deaths_in_zone += 1
        prev = self.total_deaths
        self.total_deaths += 1
        for m in _DEATH_MILESTONES:
            if prev < m <= self.total_deaths:
                bus.emit(GameEvent(EVT_MILESTONE_DEATHS, {
                    "milestone": m,
                    "message": f"You have died {m} time(s).",
                }))

    def finalize_run(
        self,
        run: "DungeonRun",
        gold_earned: int = 0,
        currency_earned: int = 0,
    ) -> None:
        """
        Call after a DungeonRun ends (complete or death).
        Updates zone stats and stores a RunRecord.
        """
        zone_id = run.zone
        stats = self._get_zone(zone_id)
        rooms_cleared = run.current_room_index

        if run.player_died:
            self.record_death(zone_id)
        elif run.is_complete:
            stats.runs_completed += 1
            prev = stats.runs_completed
            for m in _CLEAR_MILESTONES:
                if prev - 1 < m <= prev:
                    bus.emit(GameEvent(EVT_MILESTONE_CLEARS, {
                        "zone_id": zone_id,
                        "milestone": m,
                        "message": f"Cleared {zone_id} {m} time(s)!",
                    }))

        stats.best_rooms_cleared = max(stats.best_rooms_cleared, rooms_cleared)
        self.total_gold_earned += gold_earned
        self.total_currency_earned += currency_earned

        boss_killed = any(
            r.room_type.value == "boss" and r.completed for r in run.rooms
        )
        self._run_history.append(RunRecord(
            zone_id=zone_id,
            rooms_cleared=rooms_cleared,
            boss_killed=boss_killed,
            player_died=run.player_died,
            drops_count=len(run.drops_this_run),
            gold_earned=gold_earned,
            currency_earned=currency_earned,
        ))

    # ─── Stats / display ──────────────────────────────────────────────────

    def zone_stats(self, zone_id: str) -> ZoneStats:
        return self._zone_stats.get(zone_id, ZoneStats(zone_id))

    def global_stats(self) -> dict:
        return {
            "total_kills":          self.total_kills,
            "total_deaths":         self.total_deaths,
            "total_boss_kills":     self.total_boss_kills,
            "defeated_bosses":      sorted(self.defeated_bosses),
            "zones_boss_cleared":   sum(1 for s in self._zone_stats.values() if s.boss_killed),
            "total_runs_attempted": sum(s.runs_attempted for s in self._zone_stats.values()),
            "total_runs_completed": sum(s.runs_completed for s in self._zone_stats.values()),
            "total_gold_earned":    self.total_gold_earned,
            "total_currency":       self.total_currency_earned,
        }

    def run_history(self, zone_id: str | None = None) -> list[RunRecord]:
        if zone_id:
            return [r for r in self._run_history if r.zone_id == zone_id]
        return list(self._run_history)

    def summary(self) -> str:
        stats = self.global_stats()
        return (
            f"Kills: {stats['total_kills']} | "
            f"Deaths: {stats['total_deaths']} | "
            f"Bosses: {stats['total_boss_kills']} | "
            f"Zones cleared: {stats['zones_boss_cleared']}"
        )

    # ─── Persistence ──────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "defeated_bosses":       list(self.defeated_bosses),
            "total_kills":           self.total_kills,
            "total_deaths":          self.total_deaths,
            "total_boss_kills":      self.total_boss_kills,
            "total_gold_earned":     self.total_gold_earned,
            "total_currency_earned": self.total_currency_earned,
            "zone_stats": {
                zid: {
                    "runs_attempted":    s.runs_attempted,
                    "runs_completed":    s.runs_completed,
                    "boss_killed":       s.boss_killed,
                    "kills_in_zone":     s.kills_in_zone,
                    "best_rooms_cleared": s.best_rooms_cleared,
                    "deaths_in_zone":    s.deaths_in_zone,
                }
                for zid, s in self._zone_stats.items()
            },
            "run_history": [
                {
                    "zone_id":         r.zone_id,
                    "rooms_cleared":   r.rooms_cleared,
                    "boss_killed":     r.boss_killed,
                    "player_died":     r.player_died,
                    "drops_count":     r.drops_count,
                    "gold_earned":     r.gold_earned,
                    "currency_earned": r.currency_earned,
                }
                for r in self._run_history
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProgressionManager":
        pm = cls()
        pm.defeated_bosses      = set(data.get("defeated_bosses", []))
        pm.total_kills          = data.get("total_kills", 0)
        pm.total_deaths         = data.get("total_deaths", 0)
        pm.total_boss_kills     = data.get("total_boss_kills", 0)
        pm.total_gold_earned    = data.get("total_gold_earned", 0)
        pm.total_currency_earned = data.get("total_currency_earned", 0)

        for zid, sd in data.get("zone_stats", {}).items():
            pm._zone_stats[zid] = ZoneStats(
                zone_id=zid,
                runs_attempted=    sd.get("runs_attempted", 0),
                runs_completed=    sd.get("runs_completed", 0),
                boss_killed=       sd.get("boss_killed", False),
                kills_in_zone=     sd.get("kills_in_zone", 0),
                best_rooms_cleared=sd.get("best_rooms_cleared", 0),
                deaths_in_zone=    sd.get("deaths_in_zone", 0),
            )
        for rd in data.get("run_history", []):
            pm._run_history.append(RunRecord(**rd))
        return pm

    # ─── Internal ─────────────────────────────────────────────────────────

    def _get_zone(self, zone_id: str) -> ZoneStats:
        if zone_id not in self._zone_stats:
            self._zone_stats[zone_id] = ZoneStats(zone_id)
        return self._zone_stats[zone_id]
