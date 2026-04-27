from dataclasses import dataclass, field
from core.constants import StatusEffect, POISON_DAMAGE_PER_TURN


@dataclass
class ActiveEffect:
    effect: StatusEffect
    duration: int           # turns remaining (-1 = permanent until removed)
    magnitude: float = 1.0  # multiplier or flat value depending on effect

    @property
    def is_expired(self) -> bool:
        return self.duration == 0

    def tick(self) -> None:
        if self.duration > 0:
            self.duration -= 1


class StatusEffectManager:
    def __init__(self):
        self._effects: dict[StatusEffect, ActiveEffect] = {}

    def apply(self, effect: StatusEffect, duration: int, magnitude: float = 1.0) -> None:
        self._effects[effect] = ActiveEffect(effect, duration, magnitude)

    def remove(self, effect: StatusEffect) -> None:
        self._effects.pop(effect, None)

    def has(self, effect: StatusEffect) -> bool:
        return effect in self._effects

    def get(self, effect: StatusEffect) -> ActiveEffect | None:
        return self._effects.get(effect)

    def tick_all(self) -> list[StatusEffect]:
        """Advance all effect durations; return list of expired effects."""
        expired = []
        for eff in list(self._effects.values()):
            eff.tick()
            if eff.is_expired:
                expired.append(eff.effect)
        for e in expired:
            self._effects.pop(e, None)
        return expired

    def get_poison_damage(self, max_hp: int) -> int:
        eff = self._effects.get(StatusEffect.POISON)
        if not eff:
            return 0
        return max(1, int(max_hp * POISON_DAMAGE_PER_TURN * eff.magnitude))

    def is_stunned(self) -> bool:
        return self.has(StatusEffect.STUN)

    def is_defending(self) -> bool:
        return self.has(StatusEffect.DEFENDING)

    def is_slowed(self) -> bool:
        return self.has(StatusEffect.SLOW)

    def damage_reduction(self) -> float:
        """Aggregate flat damage reduction fraction from active effects."""
        reduction = 0.0
        if self.has(StatusEffect.DEFENDING):
            from core.constants import DEFEND_DAMAGE_REDUCTION
            reduction += DEFEND_DAMAGE_REDUCTION
        if self.has(StatusEffect.MAGIC_SHIELD):
            shield = self._effects[StatusEffect.MAGIC_SHIELD]
            reduction += shield.magnitude
        return min(reduction, 0.85)  # cap at 85%

    def all_active(self) -> list[StatusEffect]:
        return list(self._effects.keys())
