import random


class Character:
    def __init__(self, name, max_hp, attack, defense, speed, sprite_file,
                 sprite_size=(128, 128)):
        self.name        = name
        self.max_hp      = max_hp
        self.hp          = max_hp
        self.attack      = attack
        self.defense     = defense
        self.speed       = speed
        self.sprite_file = sprite_file
        self.sprite_size = sprite_size
        self._defending  = False

    # ------------------------------------------------------------------
    @property
    def alive(self):
        return self.hp > 0

    @property
    def hp_ratio(self):
        return self.hp / self.max_hp

    # ------------------------------------------------------------------
    def roll_damage(self):
        lo = max(1, int(self.attack * 0.8))
        hi = int(self.attack * 1.2)
        return random.randint(lo, hi)

    def receive_hit(self, raw):
        """Apply raw damage, returning the final amount actually dealt."""
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
# Factory functions — one source of truth for every character's stats
# ------------------------------------------------------------------

def make_warrior():
    return Character(
        name="Warrior", max_hp=120, attack=20, defense=6,  speed=10,
        sprite_file="warrior.png", sprite_size=(128, 128),
    )

def make_goblin():
    return Character(
        name="Goblin",  max_hp=50,  attack=12, defense=2,  speed=14,
        sprite_file="goblin.png",  sprite_size=(96, 96),
    )

def make_archer():
    return Character(
        name="Archer",  max_hp=65,  attack=16, defense=4,  speed=16,
        sprite_file="archer.png",  sprite_size=(110, 110),
    )

def make_mage():
    return Character(
        name="Mage",    max_hp=45,  attack=22, defense=1,  speed=8,
        sprite_file="mage.png",    sprite_size=(110, 110),
    )

def make_boss():
    return Character(
        name="Dark Lord", max_hp=160, attack=26, defense=8, speed=6,
        sprite_file="boss.png",    sprite_size=(140, 140),
    )
