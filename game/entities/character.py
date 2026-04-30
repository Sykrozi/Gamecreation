import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from combat_skills import PlayerCombatSkills
from gathering_skills import PlayerGatheringSkills


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

class Item:
    def __init__(self, name, kind, value):
        self.name  = name
        self.kind  = kind
        self.value = value

    def describe(self):
        if self.kind == "potion":   return f"Restores {self.value} HP"
        if self.kind == "weapon":   return f"+{self.value} ATK"
        if self.kind == "armor":    return f"+{self.value} DEF"
        if self.kind == "material": return f"x{self.value}" if self.value > 1 else "material"
        return ""


def make_health_potion(): return Item("Health Potion", "potion", 40)
def make_iron_sword():    return Item("Iron Sword",    "weapon",  8)
def make_wooden_shield(): return Item("Wooden Shield", "armor",   5)

MAX_INVENTORY = 5


# ---------------------------------------------------------------------------
# Character
# ---------------------------------------------------------------------------

class Character:
    def __init__(self, name, max_hp, attack, defense, speed, sprite_file,
                 sprite_size=(128, 128), xp_reward=0):
        self.name        = name
        self._base_hp    = max_hp
        self.hp          = max_hp
        self._base_atk   = attack
        self._base_def   = defense
        self.speed       = speed
        self.sprite_file = sprite_file
        self.sprite_size = sprite_size
        self._defending  = False
        self.xp_reward   = xp_reward

        self.level      = 1
        self.xp         = 0
        self.xp_to_next = 100
        self.inventory  = []
        self._wpn       = None
        self._arm       = None
        self.gold        = 0
        self._play_time  = 0.0
        self.combat_skills = PlayerCombatSkills()
        self.gathering     = PlayerGatheringSkills()

    # ------------------------------------------------------------------

    @property
    def max_hp(self) -> int:
        return self._base_hp + self.combat_skills.max_hp_bonus

    @property
    def attack(self) -> int:
        base = (self._base_atk
                + (self._wpn.value if self._wpn else 0)
                + self.combat_skills.attack_bonus)
        if self.combat_skills.berserk_active:
            base = int(base * 1.5)
        return base

    @property
    def defense(self) -> int:
        return (self._base_def
                + (self._arm.value if self._arm else 0)
                + self.combat_skills.defense_bonus)

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def hp_ratio(self) -> float:
        return self.hp / self.max_hp

    # ------------------------------------------------------------------

    def roll_damage(self) -> int:
        lo = max(1, int(self.attack * 0.8))
        hi = int(self.attack * 1.2)
        return random.randint(lo, hi)

    def receive_hit(self, raw: int) -> int:
        cs = self.combat_skills
        if cs.iron_skin_active:
            raw = int(raw * 0.4)
            cs.consume_iron_skin()
        reduction = self.defense if self._defending else self.defense // 2
        dmg = max(1, raw - reduction)
        self.hp = max(0, self.hp - dmg)
        return dmg

    def start_defend(self):
        self._defending = True

    def end_turn(self):
        self._defending = False

    def full_reset(self):
        self.hp         = self.max_hp
        self._defending = False

    # ------------------------------------------------------------------
    # Progression
    # ------------------------------------------------------------------

    def gain_xp(self, amount: int) -> bool:
        self.xp += amount
        if self.xp >= self.xp_to_next:
            self.xp        -= self.xp_to_next
            self.level     += 1
            self.xp_to_next = 100 * self.level
            self._base_atk += 2
            self._base_def += 1
            bonus           = 10
            self._base_hp  += bonus
            self.hp         = min(self.max_hp, self.hp + bonus)
            return True
        return False

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------

    def add_item(self, item) -> bool:
        if len(self.inventory) < MAX_INVENTORY:
            self.inventory.append(item)
            return True
        return False

    def use_item(self, item):
        if item.kind == "potion":
            healed = min(item.value, self.max_hp - self.hp)
            self.hp += healed
            self.inventory.remove(item)
            return f"Used {item.name} — restored {healed} HP.", True

        if item.kind == "weapon":
            if self._wpn is item:
                self._wpn = None
                return f"{item.name} unequipped.", False
            self._wpn = item
            return f"{item.name} equipped (+{item.value} ATK).", False

        if item.kind == "armor":
            if self._arm is item:
                self._arm = None
                return f"{item.name} unequipped.", False
            self._arm = item
            return f"{item.name} equipped (+{item.value} DEF).", False

        return "Nothing happened.", False


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def make_warrior():
    c = Character(
        name="Warrior", max_hp=120, attack=20, defense=6, speed=10,
        sprite_file="warrior.png", sprite_size=(128, 128),
    )
    c.add_item(make_health_potion())
    c.add_item(make_health_potion())
    return c

def make_goblin():
    return Character(
        name="Goblin", max_hp=50, attack=12, defense=2, speed=14,
        sprite_file="goblin.png", sprite_size=(96, 96), xp_reward=30,
    )

def make_archer():
    return Character(
        name="Archer", max_hp=65, attack=16, defense=4, speed=16,
        sprite_file="archer.png", sprite_size=(110, 110), xp_reward=50,
    )

def make_mage():
    return Character(
        name="Mage", max_hp=45, attack=22, defense=1, speed=8,
        sprite_file="mage.png", sprite_size=(110, 110), xp_reward=60,
    )

def make_boss():
    return Character(
        name="Dark Lord", max_hp=160, attack=26, defense=8, speed=6,
        sprite_file="boss.png", sprite_size=(140, 140), xp_reward=100,
    )
