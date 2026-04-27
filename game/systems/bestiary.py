"""
Bestiary — tracks all monster encounters and surfaces lore/weakness data.

Per-monster records store:
  - Total kill count
  - First/last seen zone
  - Whether the player has 'studied' this monster (unlocks weakness display)

A monster becomes fully studied once the player has killed it enough times
(STUDY_THRESHOLD kills) OR after examining it mid-combat (future UI hook).

Discovery flow:
  1. First kill → entry created, is_discovered = True, is_studied = False
  2. After STUDY_THRESHOLD kills → is_studied = True, weaknesses visible in UI
  3. Boss variants share their base monster entry but have a separate boss flag
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.events import bus, GameEvent
from data.monsters import MonsterDefinition, BossDefinition, MONSTERS, BOSSES

EVT_BESTIARY_DISCOVER  = "bestiary_discover"
EVT_BESTIARY_STUDIED   = "bestiary_studied"

STUDY_THRESHOLD = 10   # kills required to fully study a monster


@dataclass
class BestiaryEntry:
    monster_id: str
    name: str
    lore: str
    kill_count: int = 0
    is_discovered: bool = False
    is_studied: bool = False
    is_boss: bool = False
    zones_seen: list[str] = field(default_factory=list)

    @property
    def kills_to_study(self) -> int:
        return max(0, STUDY_THRESHOLD - self.kill_count)

    def record_kill(self, zone_id: str) -> tuple[bool, bool]:
        """
        Register a kill. Returns (newly_discovered, newly_studied).
        """
        newly_discovered = not self.is_discovered
        self.is_discovered = True
        self.kill_count += 1

        if zone_id not in self.zones_seen:
            self.zones_seen.append(zone_id)

        newly_studied = False
        if not self.is_studied and self.kill_count >= STUDY_THRESHOLD:
            self.is_studied = True
            newly_studied = True

        return newly_discovered, newly_studied

    def weakness_summary(self) -> str | None:
        """Returns a human-readable weakness string once the monster is studied."""
        if not self.is_studied:
            return None
        from data.monsters import MONSTERS, BOSSES
        defn = BOSSES.get(self.monster_id) or MONSTERS.get(self.monster_id)
        if defn is None:
            return "No data."
        parts: list[str] = []
        for w in defn.weaknesses:
            parts.append(f"{w.style.value}: {w.weakness.value}")
        return ", ".join(parts) if parts else "None"


# ─── Lore strings ─────────────────────────────────────────────────────────────

_LORE: dict[str, str] = {
    "goblin": (
        "Goblins are scrawny green humanoids that prowl the Goblin Forest in "
        "loose raiding bands. They fight dirty and scatter when outmatched."
    ),
    "stone_goblin": (
        "Stone Goblins have hardened their skin through crude alchemical rituals. "
        "Their rocky hide resists piercing arrows but shatters under blunt blows."
    ),
    "forest_boar": (
        "Wild boars that have grown massive feasting on enchanted forest roots. "
        "A charging boar can knock the unwary flat before they raise a shield."
    ),
    "skeleton_archer": (
        "Animated bones imbued with dark energy. The void between their ribs "
        "makes most slashing weapons slide harmlessly through."
    ),
    "dark_mage": (
        "Former scholars who delved too deep into forbidden rune-work. "
        "They thrive on magical counter-spells but crumble to honest steel."
    ),
    "elite_goblin": (
        "A goblin who survived long enough to steal decent armour. Still a goblin, "
        "but one that has learned patience — and occasionally, tactics."
    ),
    "rare_spider": (
        "A colossal spider that glows faintly violet. Venom seeps from its fangs "
        "constantly; even a glancing bite delivers a lethal dose."
    ),
    "goblin_king": (
        "King Gruk rules the Goblin Forest through fear and a very large club. "
        "He grows enraged as battle wears on, trading accuracy for raw savagery."
    ),
    "grondar": (
        "An ancient war-golem sealed in the Eternal Raid. Grondar's stone fists "
        "have crushed armies; only fire and focused magic peel his armour."
    ),
    "sylvara": (
        "A spectral elven archon imprisoned for betraying her own people. "
        "Magic slides off her ward-runes as if it never existed."
    ),
    "zythera": (
        "The Void Caller. Zythera tears open pockets of nothingness to heal and "
        "to hurl destruction. She has no weakness — only escalating fury."
    ),
}

_DEFAULT_LORE = "A creature of the dungeon depths. Study it to learn more."


# ─── Bestiary class ───────────────────────────────────────────────────────────

class Bestiary:
    """
    Persistent bestiary attached to a player's save file.

    Entries are created lazily on first kill. The bestiary can also be
    pre-populated at zone entry so the player sees undiscovered stubs for
    monsters known to inhabit a zone.
    """

    def __init__(self) -> None:
        self._entries: dict[str, BestiaryEntry] = {}

    # ─── Public API ───────────────────────────────────────────────────────

    def record_kill(self, monster_id: str, zone_id: str = "unknown") -> BestiaryEntry:
        """
        Register a combat kill. Creates the entry if it doesn't exist.
        Emits discovery/study events as appropriate.
        """
        entry = self._get_or_create(monster_id)
        newly_discovered, newly_studied = entry.record_kill(zone_id)

        if newly_discovered:
            bus.emit(GameEvent(EVT_BESTIARY_DISCOVER, {
                "monster_id": monster_id,
                "name": entry.name,
                "is_boss": entry.is_boss,
            }))

        if newly_studied:
            bus.emit(GameEvent(EVT_BESTIARY_STUDIED, {
                "monster_id": monster_id,
                "name": entry.name,
            }))

        return entry

    def get(self, monster_id: str) -> BestiaryEntry | None:
        return self._entries.get(monster_id)

    def discover(self, monster_id: str) -> BestiaryEntry:
        """Mark a monster as discovered without a kill (e.g. zone preview)."""
        entry = self._get_or_create(monster_id)
        if not entry.is_discovered:
            entry.is_discovered = True
            bus.emit(GameEvent(EVT_BESTIARY_DISCOVER, {
                "monster_id": monster_id,
                "name": entry.name,
                "is_boss": entry.is_boss,
            }))
        return entry

    def all_entries(self) -> list[BestiaryEntry]:
        return sorted(self._entries.values(), key=lambda e: e.monster_id)

    def discovered_entries(self) -> list[BestiaryEntry]:
        return [e for e in self.all_entries() if e.is_discovered]

    def studied_entries(self) -> list[BestiaryEntry]:
        return [e for e in self.all_entries() if e.is_studied]

    def total_kills(self) -> int:
        return sum(e.kill_count for e in self._entries.values())

    def completion_stats(self) -> dict:
        all_monsters = set(MONSTERS) | set(BOSSES)
        discovered = sum(1 for mid in all_monsters
                         if self._entries.get(mid, BestiaryEntry("", "", "")).is_discovered)
        studied    = sum(1 for mid in all_monsters
                         if self._entries.get(mid, BestiaryEntry("", "", "")).is_studied)
        return {
            "total":      len(all_monsters),
            "discovered": discovered,
            "studied":    studied,
        }

    def summary(self) -> str:
        stats = self.completion_stats()
        return (f"Bestiary: {stats['discovered']}/{stats['total']} discovered, "
                f"{stats['studied']}/{stats['total']} studied")

    # ─── Internal ─────────────────────────────────────────────────────────

    def _get_or_create(self, monster_id: str) -> BestiaryEntry:
        if monster_id in self._entries:
            return self._entries[monster_id]

        # Resolve definition for name + boss flag
        defn: MonsterDefinition | None = (
            BOSSES.get(monster_id) or MONSTERS.get(monster_id)
        )
        name    = defn.name if defn else monster_id.replace("_", " ").title()
        is_boss = isinstance(defn, BossDefinition) if defn else False
        lore    = _LORE.get(monster_id, _DEFAULT_LORE)

        entry = BestiaryEntry(
            monster_id=monster_id,
            name=name,
            lore=lore,
            is_boss=is_boss,
        )
        self._entries[monster_id] = entry
        return entry
