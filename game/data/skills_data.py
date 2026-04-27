from dataclasses import dataclass, field
from core.constants import SkillType, CombatStyle


@dataclass
class SkillUnlock:
    level: int
    description: str


@dataclass
class SkillDefinition:
    skill_type: SkillType
    name: str
    is_combat: bool
    unlocks: list[SkillUnlock] = field(default_factory=list)


SKILLS: dict[SkillType, SkillDefinition] = {
    SkillType.ATTACK: SkillDefinition(
        skill_type=SkillType.ATTACK,
        name="Attack",
        is_combat=True,
        unlocks=[
            SkillUnlock(1, "Bronze sword"),
            SkillUnlock(5, "Iron sword"),
            SkillUnlock(25, "Steel/Mithril weapons + combo attacks"),
            SkillUnlock(40, "Crit chance unlocked"),
            SkillUnlock(50, "Adamantite/Rune weapons + area attacks"),
            SkillUnlock(60, "Counter-attack"),
            SkillUnlock(80, "Legendary weapons"),
            SkillUnlock(95, "Dual wield"),
            SkillUnlock(99, "Execution below threshold HP"),
        ],
    ),
    SkillType.DEFENSE: SkillDefinition(
        skill_type=SkillType.DEFENSE,
        name="Defense",
        is_combat=True,
        unlocks=[
            SkillUnlock(1, "No armor"),
            SkillUnlock(5, "Bronze/Iron armor"),
            SkillUnlock(20, "Steel/Mithril armor + shield slot"),
            SkillUnlock(30, "Basic block"),
            SkillUnlock(50, "Adamantite/Rune armor + set bonus"),
            SkillUnlock(60, "Reflect damage"),
            SkillUnlock(80, "Legendary armor"),
            SkillUnlock(90, "Full block"),
            SkillUnlock(99, "Temporary invincibility"),
        ],
    ),
    SkillType.STRENGTH: SkillDefinition(
        skill_type=SkillType.STRENGTH,
        name="Strength",
        is_combat=True,
        unlocks=[
            SkillUnlock(1, "+5-10% melee damage + basic knockback"),
            SkillUnlock(20, "+20-30% melee damage + Power Strike + stun chance"),
            SkillUnlock(50, "+40-50% melee damage + ignore % defense + Rage buff"),
            SkillUnlock(80, "+60% melee damage + one-hit chance + Strength Aura"),
        ],
    ),
    SkillType.RESISTANCE: SkillDefinition(
        skill_type=SkillType.RESISTANCE,
        name="Resistance",
        is_combat=True,
        unlocks=[
            SkillUnlock(1, "100-150 base HP + regen out of combat"),
            SkillUnlock(20, "200-250 HP + poison resist + elemental resist"),
            SkillUnlock(50, "300-350 HP + combat regen + HP barrier"),
            SkillUnlock(80, "400-450 HP + boss effect resist + barrier absorbs 1 hit"),
        ],
    ),
    SkillType.RANGE: SkillDefinition(
        skill_type=SkillType.RANGE,
        name="Range",
        is_combat=True,
        unlocks=[
            SkillUnlock(1, "Wood bow + arrows"),
            SkillUnlock(20, "Maple/Yew bow + multi-shot + poison shot"),
            SkillUnlock(50, "Magic bow + rain of arrows"),
            SkillUnlock(80, "Legendary/raid ranged weapons + armor pierce"),
            SkillUnlock(95, "Infinite quiver"),
        ],
    ),
    SkillType.MAGIC: SkillDefinition(
        skill_type=SkillType.MAGIC,
        name="Magic",
        is_combat=True,
        unlocks=[
            SkillUnlock(1, "Basic runes + basic staff + simple spells"),
            SkillUnlock(20, "Earth/air runes + intermediate staff + debuffs + AoE"),
            SkillUnlock(50, "Special runes + rare drop staves + combat teleport"),
            SkillUnlock(80, "Legendary staves + basic summoning + full control spells"),
        ],
    ),
    SkillType.MINING: SkillDefinition(
        skill_type=SkillType.MINING,
        name="Mining",
        is_combat=False,
        unlocks=[
            SkillUnlock(1, "Copper/Tin rocks + bronze pickaxe"),
            SkillUnlock(20, "Iron, coal, mithril + iron/steel pickaxe"),
            SkillUnlock(30, "Overcharge mechanic"),
            SkillUnlock(60, "Adamantite/Runite + deep mining"),
            SkillUnlock(80, "Dragon pickaxe"),
            SkillUnlock(90, "Legendary ore"),
            SkillUnlock(95, "Auto-mining (hub)"),
        ],
    ),
    SkillType.WOODCUTTING: SkillDefinition(
        skill_type=SkillType.WOODCUTTING,
        name="Woodcutting",
        is_combat=False,
        unlocks=[
            SkillUnlock(1, "Pine/oak + bronze axe"),
            SkillUnlock(20, "Willow/maple + iron/steel axe"),
            SkillUnlock(30, "Combo cutting"),
            SkillUnlock(60, "Yew/magic tree + silent cutting"),
            SkillUnlock(70, "Enchanted wood"),
            SkillUnlock(80, "Dragon axe"),
            SkillUnlock(90, "Legendary trees"),
            SkillUnlock(95, "Auto-cutting (hub)"),
        ],
    ),
    SkillType.FISHING: SkillDefinition(
        skill_type=SkillType.FISHING,
        name="Fishing",
        is_combat=False,
        unlocks=[
            SkillUnlock(1, "Sardines/trout + basic rod"),
            SkillUnlock(20, "Salmon/tuna + mithril rod"),
            SkillUnlock(30, "Special bait"),
            SkillUnlock(60, "Swordfish/squid + storm fishing"),
            SkillUnlock(80, "Abyssal fish + legendary fish + dragon rod"),
            SkillUnlock(95, "Auto-fishing (hub)"),
        ],
    ),
    SkillType.FARMING: SkillDefinition(
        skill_type=SkillType.FARMING,
        name="Farming",
        is_combat=False,
        unlocks=[
            SkillUnlock(1, "Basic seeds + simple herbs"),
            SkillUnlock(20, "Intermediate herbs + fruits + advanced composting"),
            SkillUnlock(60, "Greenhouse + unique medicinal plants + raid ingredients"),
            SkillUnlock(70, "Legendary seeds"),
            SkillUnlock(95, "Auto-farming (hub)"),
        ],
    ),
    SkillType.SMITHING: SkillDefinition(
        skill_type=SkillType.SMITHING,
        name="Smithing",
        is_combat=False,
        unlocks=[
            SkillUnlock(1, "Forge bronze weapons/armor + basic repair"),
            SkillUnlock(20, "Forge steel/mithril + item reinforcement"),
            SkillUnlock(30, "Basic enchanting"),
            SkillUnlock(60, "Forge adamantite/rune + unique weapons"),
            SkillUnlock(70, "Masterwork items"),
            SkillUnlock(80, "Legendary gear + raid gear + enchanted ore infusion"),
            SkillUnlock(95, "Auto-smithing (hub)"),
        ],
    ),
    SkillType.COOKING: SkillDefinition(
        skill_type=SkillType.COOKING,
        name="Cooking",
        is_combat=False,
        unlocks=[
            SkillUnlock(1, "Fish/meat + simple HP restore"),
            SkillUnlock(20, "Farming dishes + soup (HP + stat)"),
            SkillUnlock(60, "Multi-buff meals + group feast"),
            SkillUnlock(80, "Legendary dishes + unique combat buffs"),
            SkillUnlock(95, "Auto-cooking (hub)"),
        ],
    ),
    SkillType.HERBLORE: SkillDefinition(
        skill_type=SkillType.HERBLORE,
        name="Herblore",
        is_combat=False,
        unlocks=[
            SkillUnlock(1, "Basic healing potion + anti-venom"),
            SkillUnlock(20, "Strength/defense potion (4 dose)"),
            SkillUnlock(30, "Combined potions"),
            SkillUnlock(60, "Elemental potions + Overload"),
            SkillUnlock(70, "Group potions"),
            SkillUnlock(80, "Raid potions + invisibility potion"),
            SkillUnlock(95, "Auto-herblore (hub)"),
        ],
    ),
    SkillType.RUNECRAFT: SkillDefinition(
        skill_type=SkillType.RUNECRAFT,
        name="Runecraft",
        is_combat=False,
        unlocks=[
            SkillUnlock(1, "Fire/water runes"),
            SkillUnlock(10, "Earth/air runes"),
            SkillUnlock(20, "Intermediate runes + elemental combos"),
            SkillUnlock(50, "Special runes"),
            SkillUnlock(70, "Advanced runes + dual-element runes"),
            SkillUnlock(80, "Raid runes"),
            SkillUnlock(90, "Legendary runes + endgame runes"),
            SkillUnlock(95, "Auto-runecraft (hub)"),
        ],
    ),
}


def get_combat_style_skills(style: CombatStyle) -> list[SkillType]:
    mapping = {
        CombatStyle.MELEE: [SkillType.ATTACK, SkillType.DEFENSE, SkillType.STRENGTH],
        CombatStyle.RANGE: [SkillType.RANGE, SkillType.DEFENSE],
        CombatStyle.MAGIC: [SkillType.MAGIC, SkillType.DEFENSE],
    }
    return mapping[style]
