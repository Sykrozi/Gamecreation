import random

# Maps enemy sprite_key → available sprite filename (without .png)
_SPRITE_MAP = {
    "goblin":   "goblin",
    "bandit":   "archer",
    "wolf":     "goblin",
    "troll":    "boss",
    "boss":     "boss",
    "mage":     "mage",
    "serpent":  "goblin",
    "skeleton": "archer",
    "spider":   "goblin",
    "golem":    "boss",
    "warrior":  "archer",   # don't reuse the player sprite for enemies
    "ghost":    "mage",
    "drake":    "boss",
    "wyvern":   "boss",
}


class Enemy:
    def __init__(self, name, hp, attack, defense, xp_reward,
                 weakness=None, sprite_key=None,
                 loot_table=None, abilities=None, is_boss=False):
        self.name       = name
        self.max_hp     = hp
        self.hp         = hp
        self._atk       = attack
        self._def       = defense
        self.xp_reward  = xp_reward
        self.weakness   = weakness
        self.sprite_key = sprite_key or name.lower().replace(" ", "_")
        self.loot_table = loot_table or []
        self.abilities  = abilities or []
        self.is_boss    = is_boss
        self._defending = False

    # ── CombatSystem compatibility ──────────────────────────────────────

    @property
    def attack(self):
        return self._atk

    @property
    def defense(self):
        return self._def

    @property
    def alive(self):
        return self.hp > 0

    @property
    def hp_ratio(self):
        return self.hp / self.max_hp

    @property
    def speed(self):
        if self.is_boss:     return 6
        if self._atk >= 30:  return 8
        if self._atk <= 10:  return 14
        return 10

    @property
    def sprite_file(self):
        key = _SPRITE_MAP.get(self.sprite_key, "goblin")
        return f"{key}.png"

    @property
    def sprite_size(self):
        if self.is_boss:
            return (140, 140)
        if self.sprite_key in ("mage", "ghost"):
            return (110, 110)
        return (96, 96)

    def roll_damage(self):
        lo = max(1, int(self._atk * 0.8))
        hi = int(self._atk * 1.2)
        return random.randint(lo, hi)

    def receive_hit(self, raw):
        reduction = self._def if self._defending else self._def // 2
        dmg = max(1, raw - reduction)
        self.hp = max(0, self.hp - dmg)
        return dmg

    def start_defend(self):
        self._defending = True

    def end_turn(self):
        self._defending = False

    def full_reset(self):
        self.hp = self.max_hp
        self._defending = False

    # ── Utility ────────────────────────────────────────────────────────

    def clone(self):
        return Enemy(
            self.name, self.max_hp, self._atk, self._def,
            self.xp_reward, self.weakness, self.sprite_key,
            self.loot_table, self.abilities, self.is_boss,
        )

    def roll_loot(self):
        drops = []
        for item_name, chance, qty in self.loot_table:
            if random.random() < chance:
                drops.append((item_name, qty))
        return drops


# ── Enemy factories ─────────────────────────────────────────────────────

def _e(name, hp, atk, dfn, xp, weakness=None, sprite=None,
       loot=None, abilities=None, boss=False):
    return Enemy(name, hp, atk, dfn, xp, weakness, sprite,
                 loot or [], abilities or [], boss)


# Zone 1 — Greenwood Forest (Lv 1-3)
GOBLIN         = lambda: _e("Goblin",        40,  8,  2, 30, "magic", "goblin",
                            loot=[("Gold Coin",0.8,5), ("Health Potion",0.2,1)])
FOREST_BANDIT  = lambda: _e("Forest Bandit", 55, 10,  3, 40, "magic", "bandit",
                            loot=[("Gold Coin",0.9,8), ("Leather Scraps",0.4,1)])
WOLF           = lambda: _e("Dire Wolf",     50, 12,  1, 35, "range", "wolf",
                            loot=[("Wolf Pelt",0.7,1), ("Gold Coin",0.3,3)])
FOREST_TROLL   = lambda: _e("Forest Troll", 90, 14,  6, 60, "magic", "troll",
                            loot=[("Gold Coin",1.0,12), ("Troll Club",0.15,1)])
OAK_GOLEM_BOSS = lambda: _e("Oak Golem",   160, 18,  8,120, "magic", "boss",
                            loot=[("Forest Gem",1.0,1), ("Gold Coin",1.0,25)], boss=True)

# Zone 2 — Dark Swamp (Lv 4-6)
BOG_WITCH        = lambda: _e("Bog Witch",       70, 16,  4, 60, "melee", "mage",
                              loot=[("Poison Vial",0.5,1), ("Gold Coin",0.8,10)])
SWAMP_SERPENT    = lambda: _e("Swamp Serpent",   80, 18,  3, 55, "range", "serpent",
                              loot=[("Serpent Scale",0.6,2), ("Gold Coin",0.5,8)])
UNDEAD_WARRIOR   = lambda: _e("Undead Warrior",  85, 15,  7, 65, "magic", "skeleton",
                              loot=[("Bone Fragment",0.8,3), ("Gold Coin",0.7,10)])
SWAMP_HYDRA_BOSS = lambda: _e("Swamp Hydra",    200, 22, 10,180, "magic", "boss",
                              loot=[("Hydra Scale",1.0,1), ("Gold Coin",1.0,40)], boss=True)

# Zone 3 — Stonepeak Mines (Lv 7-10)
CAVE_SPIDER      = lambda: _e("Cave Spider",      75, 20,  5, 70, "fire",  "spider",
                              loot=[("Spider Silk",0.6,2), ("Gold Coin",0.6,8)])
ROCK_GOLEM       = lambda: _e("Rock Golem",      110, 16, 12, 80, "magic", "golem",
                              loot=[("Stone Chunk",0.8,3), ("Gold Coin",0.5,10)])
DWARF_BERSERKER  = lambda: _e("Dwarf Berserker",  90, 24,  6, 85, "range", "warrior",
                              loot=[("Iron Ore",0.7,2), ("Gold Coin",0.8,12)])
MINE_KING_BOSS   = lambda: _e("Mine King",       250, 28, 14,220, "magic", "boss",
                              loot=[("Mine Crown",1.0,1), ("Gold Coin",1.0,55)], boss=True)

# Zone 4 — Cursed Catacombs (Lv 11-15)
SKELETON_KNIGHT  = lambda: _e("Skeleton Knight", 100, 22, 10, 90, "magic", "skeleton",
                              loot=[("Bone Sword",0.3,1), ("Gold Coin",0.8,15)])
DEATH_MAGE       = lambda: _e("Death Mage",       90, 30,  5,100, "melee", "mage",
                              loot=[("Dark Scroll",0.4,1), ("Gold Coin",0.7,12)])
WRAITH           = lambda: _e("Wraith",           105, 26,  8, 95, "holy",  "ghost",
                              loot=[("Soul Essence",0.5,1), ("Gold Coin",0.6,10)])
LICH_BOSS        = lambda: _e("The Lich",         320, 35, 16,300, "holy",  "boss",
                              loot=[("Lich Crown",1.0,1), ("Gold Coin",1.0,80)], boss=True)

# Zone 5 — Dragon's Peak (Lv 16+)
DRAKE            = lambda: _e("Drake",            130, 30, 12,110, "ice",   "drake",
                              loot=[("Dragon Scale",0.5,1), ("Gold Coin",0.9,20)])
WYVERN_E         = lambda: _e("Wyvern",           140, 34, 10,120, "ice",   "wyvern",
                              loot=[("Wyvern Claw",0.4,1), ("Gold Coin",0.9,22)])
FIRE_CULTIST     = lambda: _e("Fire Cultist",     115, 38,  6,115, "water", "mage",
                              loot=[("Fire Crystal",0.5,1), ("Gold Coin",0.8,18)])
DRAGON_BOSS      = lambda: _e("Ancient Dragon",   500, 50, 20,500, "ice",   "boss",
                              loot=[("Dragon Heart",1.0,1), ("Gold Coin",1.0,150)], boss=True)


# ── Zone class ───────────────────────────────────────────────────────────

class Zone:
    def __init__(self, zone_id, name, description, min_level, max_level,
                 enemy_pool, boss_factory, background_key,
                 rooms=4, color_accent=None):
        self.zone_id        = zone_id
        self.name           = name
        self.description    = description
        self.min_level      = min_level
        self.max_level      = max_level
        self.enemy_pool     = enemy_pool
        self.boss_factory   = boss_factory
        self.background_key = background_key
        self.rooms          = rooms
        self.color_accent   = color_accent or (200, 200, 200)

    def build_encounter_list(self):
        """Returns [enemy, enemy, ..., boss] — `rooms` normal fights + final boss."""
        encounters = [random.choice(self.enemy_pool)() for _ in range(self.rooms)]
        encounters.append(self.boss_factory())
        return encounters

    @property
    def difficulty_label(self):
        if self.min_level <= 3:  return "Easy"
        if self.min_level <= 6:  return "Medium"
        if self.min_level <= 10: return "Hard"
        if self.min_level <= 15: return "Very Hard"
        return "Legendary"

    @property
    def stars(self):
        return min(5, max(1, (self.min_level // 3) + 1))


ALL_ZONES = [
    Zone(
        zone_id=0, name="Greenwood Forest",
        description="Ancient trees hide countless dangers. Perfect for new adventurers.",
        min_level=1, max_level=3,
        enemy_pool=[GOBLIN, FOREST_BANDIT, WOLF, FOREST_TROLL],
        boss_factory=OAK_GOLEM_BOSS,
        background_key="dungeon",
        rooms=3, color_accent=(80, 160, 80),
    ),
    Zone(
        zone_id=1, name="Dark Swamp",
        description="Fetid waters conceal ancient evil. Bring antidotes.",
        min_level=4, max_level=6,
        enemy_pool=[BOG_WITCH, SWAMP_SERPENT, UNDEAD_WARRIOR],
        boss_factory=SWAMP_HYDRA_BOSS,
        background_key="dungeon",
        rooms=4, color_accent=(80, 120, 60),
    ),
    Zone(
        zone_id=2, name="Stonepeak Mines",
        description="Deep tunnels rich in ore — and hungry creatures.",
        min_level=7, max_level=10,
        enemy_pool=[CAVE_SPIDER, ROCK_GOLEM, DWARF_BERSERKER],
        boss_factory=MINE_KING_BOSS,
        background_key="dungeon",
        rooms=4, color_accent=(150, 120, 80),
    ),
    Zone(
        zone_id=3, name="Cursed Catacombs",
        description="Where the dead refuse to rest. Only the brave dare enter.",
        min_level=11, max_level=15,
        enemy_pool=[SKELETON_KNIGHT, DEATH_MAGE, WRAITH],
        boss_factory=LICH_BOSS,
        background_key="dungeon",
        rooms=5, color_accent=(160, 80, 200),
    ),
    Zone(
        zone_id=4, name="Dragon's Peak",
        description="The mountain of eternal fire. Legends die here.",
        min_level=16, max_level=99,
        enemy_pool=[DRAKE, WYVERN_E, FIRE_CULTIST],
        boss_factory=DRAGON_BOSS,
        background_key="dungeon",
        rooms=5, color_accent=(220, 80, 40),
    ),
]


def zones_available_for_level(player_level: int):
    return [z for z in ALL_ZONES if player_level >= z.min_level]
