from dataclasses import dataclass, field
from data.items import Item, Weapon, Armor, Consumable


@dataclass
class Equipment:
    weapon: Weapon | None = None
    head: Armor | None = None
    body: Armor | None = None
    legs: Armor | None = None
    hands: Armor | None = None
    feet: Armor | None = None
    shield: Armor | None = None

    @property
    def total_attack_bonus(self) -> int:
        return sum(
            (p.stats.attack_bonus if p else 0)
            for p in [self.weapon, self.head, self.body, self.legs,
                       self.hands, self.feet, self.shield]
        )

    @property
    def total_defense_bonus(self) -> int:
        return sum(
            (p.stats.defense_bonus if p else 0)
            for p in [self.head, self.body, self.legs,
                       self.hands, self.feet, self.shield]
        )

    @property
    def total_strength_bonus(self) -> int:
        return self.weapon.stats.strength_bonus if self.weapon else 0

    @property
    def total_range_bonus(self) -> int:
        return self.weapon.stats.range_bonus if self.weapon else 0

    @property
    def total_magic_bonus(self) -> int:
        return self.weapon.stats.magic_bonus if self.weapon else 0

    def apply_durability_loss(self, amount: int = 1) -> None:
        for piece in [self.weapon, self.head, self.body, self.legs,
                      self.hands, self.feet, self.shield]:
            if piece:
                piece.durability = max(0, piece.durability - amount)

    def equipped_pieces(self) -> list[Item]:
        return [p for p in [self.weapon, self.head, self.body, self.legs,
                             self.hands, self.feet, self.shield] if p]


@dataclass
class Inventory:
    items: list[Item] = field(default_factory=list)
    max_slots: int = 28
    zone_currency: int = 0
    gold: int = 0

    def add(self, item: Item) -> bool:
        if item.stackable:
            for existing in self.items:
                if existing.id == item.id:
                    existing.quantity += item.quantity
                    return True
        if len(self.items) >= self.max_slots:
            return False
        self.items.append(item)
        return True

    def remove(self, item_id: str, quantity: int = 1) -> bool:
        for item in self.items:
            if item.id == item_id:
                if item.stackable and item.quantity > quantity:
                    item.quantity -= quantity
                    return True
                self.items.remove(item)
                return True
        return False

    def has(self, item_id: str) -> bool:
        return any(i.id == item_id for i in self.items)

    def get_consumables(self) -> list[Consumable]:
        return [i for i in self.items if isinstance(i, Consumable)]

    def clear_run_drops(self) -> None:
        """Called on player death — keeps equipped gear, removes run loot."""
        self.items.clear()
        self.zone_currency = 0
