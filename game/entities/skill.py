from dataclasses import dataclass, field
from core.constants import SkillType, XP_TABLE, MAX_LEVEL
from core.events import bus, GameEvent, EVT_LEVEL_UP


@dataclass
class Skill:
    skill_type: SkillType
    xp: int = 0
    level: int = 1

    def add_xp(self, amount: int) -> list[int]:
        """Add XP and return list of new levels reached."""
        self.xp += amount
        leveled_up = []
        while self.level < MAX_LEVEL and self.xp >= XP_TABLE.get(self.level + 1, 0):
            self.level += 1
            leveled_up.append(self.level)
            bus.emit(GameEvent(EVT_LEVEL_UP, {
                "skill": self.skill_type.value,
                "new_level": self.level,
            }))
        return leveled_up

    def xp_to_next_level(self) -> int:
        if self.level >= MAX_LEVEL:
            return 0
        return max(0, XP_TABLE.get(self.level + 1, 0) - self.xp)


@dataclass
class SkillSet:
    skills: dict[SkillType, Skill] = field(default_factory=dict)

    def __post_init__(self):
        for st in SkillType:
            if st not in self.skills:
                self.skills[st] = Skill(skill_type=st)

    def get(self, skill_type: SkillType) -> Skill:
        return self.skills[skill_type]

    def level(self, skill_type: SkillType) -> int:
        return self.skills[skill_type].level

    def add_xp(self, skill_type: SkillType, amount: int) -> list[int]:
        return self.skills[skill_type].add_xp(amount)

    @property
    def combat_level(self) -> int:
        atk = self.level(SkillType.ATTACK)
        dfn = self.level(SkillType.DEFENSE)
        str_ = self.level(SkillType.STRENGTH)
        rng = self.level(SkillType.RANGE)
        mag = self.level(SkillType.MAGIC)
        res = self.level(SkillType.RESISTANCE)
        base = (dfn + res + (str_ + atk) // 2) / 4
        melee_cb = (atk + str_) * 0.325
        range_cb = rng * 0.325
        magic_cb = mag * 0.325
        return int(base + max(melee_cb, range_cb, magic_cb))
