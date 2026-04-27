from dataclasses import dataclass, field
from core.constants import CombatStyle, MaterialTier, SkillType


@dataclass
class ItemStat:
    attack_bonus: int = 0
    defense_bonus: int = 0
    strength_bonus: int = 0
    range_bonus: int = 0
    magic_bonus: int = 0
    hp_bonus: int = 0


@dataclass
class Item:
    id: str
    name: str
    tier: MaterialTier
    level_req: int
    stats: ItemStat = field(default_factory=ItemStat)
    durability: int = 100
    max_durability: int = 100
    stackable: bool = False
    quantity: int = 1

    @property
    def durability_pct(self) -> float:
        return self.durability / self.max_durability


@dataclass
class Weapon(Item):
    combat_style: CombatStyle = CombatStyle.MELEE
    damage_min: int = 1
    damage_max: int = 3
    special_cost: int = 100  # special bar cost


@dataclass
class Armor(Item):
    slot: str = "body"  # head, body, legs, hands, feet, shield


@dataclass
class Consumable(Item):
    heal_amount: int = 0
    effect: str = ""  # "anti-venom", "strength", "defense", etc.
    effect_duration: int = 0  # turns (0 = instant)
    effect_magnitude: float = 0.0
    doses: int = 1
    stackable: bool = True


# --- Weapons by tier ---
WEAPONS: dict[str, Weapon] = {
    # Melee
    "bronze_sword": Weapon(
        id="bronze_sword", name="Bronze Sword", tier=MaterialTier.BRONZE,
        level_req=1, combat_style=CombatStyle.MELEE,
        damage_min=2, damage_max=5,
        stats=ItemStat(attack_bonus=5, strength_bonus=3),
    ),
    "iron_sword": Weapon(
        id="iron_sword", name="Iron Sword", tier=MaterialTier.IRON,
        level_req=5, combat_style=CombatStyle.MELEE,
        damage_min=4, damage_max=9,
        stats=ItemStat(attack_bonus=10, strength_bonus=6),
    ),
    "steel_sword": Weapon(
        id="steel_sword", name="Steel Sword", tier=MaterialTier.STEEL,
        level_req=25, combat_style=CombatStyle.MELEE,
        damage_min=8, damage_max=16,
        stats=ItemStat(attack_bonus=20, strength_bonus=12),
    ),
    "mithril_sword": Weapon(
        id="mithril_sword", name="Mithril Sword", tier=MaterialTier.MITHRIL,
        level_req=35, combat_style=CombatStyle.MELEE,
        damage_min=14, damage_max=26,
        stats=ItemStat(attack_bonus=35, strength_bonus=20),
    ),
    "adamantite_sword": Weapon(
        id="adamantite_sword", name="Adamantite Sword", tier=MaterialTier.ADAMANTITE,
        level_req=50, combat_style=CombatStyle.MELEE,
        damage_min=22, damage_max=40,
        stats=ItemStat(attack_bonus=55, strength_bonus=32),
    ),
    "rune_sword": Weapon(
        id="rune_sword", name="Rune Sword", tier=MaterialTier.RUNE,
        level_req=55, combat_style=CombatStyle.MELEE,
        damage_min=30, damage_max=55,
        stats=ItemStat(attack_bonus=70, strength_bonus=45),
    ),
    # Range
    "wood_bow": Weapon(
        id="wood_bow", name="Wood Bow", tier=MaterialTier.BRONZE,
        level_req=1, combat_style=CombatStyle.RANGE,
        damage_min=2, damage_max=6,
        stats=ItemStat(range_bonus=5),
    ),
    "maple_bow": Weapon(
        id="maple_bow", name="Maple Bow", tier=MaterialTier.MITHRIL,
        level_req=35, combat_style=CombatStyle.RANGE,
        damage_min=12, damage_max=24,
        stats=ItemStat(range_bonus=32),
    ),
    "magic_bow": Weapon(
        id="magic_bow", name="Magic Bow", tier=MaterialTier.RUNE,
        level_req=55, combat_style=CombatStyle.RANGE,
        damage_min=28, damage_max=50,
        stats=ItemStat(range_bonus=65),
    ),
    # Magic
    "basic_staff": Weapon(
        id="basic_staff", name="Basic Staff", tier=MaterialTier.BRONZE,
        level_req=1, combat_style=CombatStyle.MAGIC,
        damage_min=3, damage_max=8,
        stats=ItemStat(magic_bonus=8),
    ),
    "mithril_staff": Weapon(
        id="mithril_staff", name="Mithril Staff", tier=MaterialTier.MITHRIL,
        level_req=35, combat_style=CombatStyle.MAGIC,
        damage_min=15, damage_max=30,
        stats=ItemStat(magic_bonus=40),
    ),
    "rune_staff": Weapon(
        id="rune_staff", name="Rune Staff", tier=MaterialTier.RUNE,
        level_req=55, combat_style=CombatStyle.MAGIC,
        damage_min=32, damage_max=58,
        stats=ItemStat(magic_bonus=72),
    ),
}

# --- Armor by tier ---
ARMORS: dict[str, Armor] = {
    "bronze_body": Armor(
        id="bronze_body", name="Bronze Platebody", tier=MaterialTier.BRONZE,
        level_req=1, slot="body",
        stats=ItemStat(defense_bonus=8),
    ),
    "iron_body": Armor(
        id="iron_body", name="Iron Platebody", tier=MaterialTier.IRON,
        level_req=15, slot="body",
        stats=ItemStat(defense_bonus=16),
    ),
    "steel_body": Armor(
        id="steel_body", name="Steel Platebody", tier=MaterialTier.STEEL,
        level_req=25, slot="body",
        stats=ItemStat(defense_bonus=28),
    ),
    "mithril_body": Armor(
        id="mithril_body", name="Mithril Platebody", tier=MaterialTier.MITHRIL,
        level_req=35, slot="body",
        stats=ItemStat(defense_bonus=44),
    ),
    "adamantite_body": Armor(
        id="adamantite_body", name="Adamantite Platebody", tier=MaterialTier.ADAMANTITE,
        level_req=50, slot="body",
        stats=ItemStat(defense_bonus=65),
    ),
    "rune_body": Armor(
        id="rune_body", name="Rune Platebody", tier=MaterialTier.RUNE,
        level_req=55, slot="body",
        stats=ItemStat(defense_bonus=88),
    ),
}

# --- Consumables ---
CONSUMABLES: dict[str, Consumable] = {
    "basic_potion": Consumable(
        id="basic_potion", name="Healing Potion", tier=MaterialTier.BRONZE,
        level_req=1, heal_amount=30, doses=4,
        stats=ItemStat(hp_bonus=0),
    ),
    "super_potion": Consumable(
        id="super_potion", name="Super Healing Potion", tier=MaterialTier.STEEL,
        level_req=25, heal_amount=75, doses=4,
    ),
    "anti_venom": Consumable(
        id="anti_venom", name="Anti-Venom", tier=MaterialTier.BRONZE,
        level_req=1, effect="anti-venom", doses=1,
    ),
    "strength_potion": Consumable(
        id="strength_potion", name="Strength Potion", tier=MaterialTier.IRON,
        level_req=20, effect="strength", effect_duration=5,
        effect_magnitude=0.15, doses=4,
    ),
    "defense_potion": Consumable(
        id="defense_potion", name="Defense Potion", tier=MaterialTier.IRON,
        level_req=20, effect="defense", effect_duration=5,
        effect_magnitude=0.15, doses=4,
    ),
    "overload": Consumable(
        id="overload", name="Overload", tier=MaterialTier.RUNE,
        level_req=60, effect="overload", effect_duration=10,
        effect_magnitude=0.25, doses=4,
    ),
    "cooked_trout": Consumable(
        id="cooked_trout", name="Cooked Trout", tier=MaterialTier.IRON,
        level_req=1, heal_amount=20, stackable=True,
    ),
    "swordfish": Consumable(
        id="swordfish", name="Swordfish", tier=MaterialTier.STEEL,
        level_req=1, heal_amount=50, stackable=True,
    ),
}
