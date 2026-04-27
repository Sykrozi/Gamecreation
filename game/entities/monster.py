from __future__ import annotations
from dataclasses import dataclass, field
from core.constants import CombatStyle, WeaknessType, StatusEffect, WEAKNESS_MULTIPLIERS
from data.monsters import MonsterDefinition, BossDefinition, BossPhaseData
from entities.status_effects import StatusEffectManager


@dataclass
class MonsterInstance:
    definition: MonsterDefinition
    hp: int = field(init=False)
    effects: StatusEffectManager = field(default_factory=StatusEffectManager)

    def __post_init__(self):
        self.hp = self.definition.hp

    @property
    def max_hp(self) -> int:
        return self.definition.hp

    @property
    def hp_fraction(self) -> float:
        return self.hp / self.max_hp

    @property
    def is_alive(self) -> bool:
        return self.hp > 0

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def xp_reward(self) -> int:
        return self.definition.xp_reward

    def get_weakness(self, style: CombatStyle) -> WeaknessType:
        for w in self.definition.weaknesses:
            if w.style == style:
                return w.weakness
        return WeaknessType.NEUTRAL

    def damage_multiplier(self, style: CombatStyle) -> float:
        weakness = self.get_weakness(style)
        return WEAKNESS_MULTIPLIERS[weakness]

    def take_damage(self, raw_damage: int, style: CombatStyle) -> int:
        multiplier = self.damage_multiplier(style)
        reduction = self.effects.damage_reduction()
        defense = self.definition.defense
        def_reduction = min(defense / (defense + 80), 0.55)
        total_reduction = min(reduction + def_reduction, 0.80)
        damage = max(0, int(raw_damage * multiplier * (1 - total_reduction)))
        self.hp = max(0, self.hp - damage)
        return damage

    def calculate_attack_damage(self) -> int:
        import random
        base = self.definition.attack
        variance = max(1, base // 4)
        return random.randint(max(1, base - variance), base + variance)

    def __repr__(self) -> str:
        return f"Monster({self.name!r}, HP={self.hp}/{self.max_hp})"


@dataclass
class BossInstance(MonsterInstance):
    definition: BossDefinition
    current_phase: int = 1
    _phase_triggered: set[int] = field(default_factory=set)

    def __post_init__(self):
        self.hp = self.definition.hp
        self._phase_triggered.add(1)

    def check_phase_transition(self) -> BossPhaseData | None:
        """Return new phase data if a phase threshold was crossed, else None."""
        phases = sorted(self.definition.phases, key=lambda p: p.hp_threshold, reverse=True)
        for phase_data in phases:
            if (self.hp_fraction <= phase_data.hp_threshold
                    and phase_data.phase not in self._phase_triggered
                    and phase_data.phase > 1):
                self._phase_triggered.add(phase_data.phase)
                self.current_phase = phase_data.phase
                return phase_data
        return None

    def get_current_phase_data(self) -> BossPhaseData | None:
        return next(
            (p for p in self.definition.phases if p.phase == self.current_phase),
            None
        )

    def get_available_attacks(self) -> list[str]:
        attacks: list[str] = []
        for phase_data in self.definition.phases:
            if phase_data.phase <= self.current_phase:
                attacks.extend(phase_data.new_attacks)
        return attacks

    def is_immune_to(self, style: CombatStyle) -> bool:
        return style in self.definition.immune_to

    def take_damage(self, raw_damage: int, style: CombatStyle) -> int:
        if self.is_immune_to(style):
            return 0
        return super().take_damage(raw_damage, style)

    def __repr__(self) -> str:
        return (
            f"Boss({self.name!r}, "
            f"HP={self.hp}/{self.max_hp}, "
            f"Phase={self.current_phase})"
        )
