"""
Tiny inventory management module.

Contains three known bugs:
BUG_A: apply_discount() truncates instead of rounding.
BUG_B: restock() doesn't cap at max_capacity.
BUG_C: checkout() doesn't validate that quantity is positive.
"""

from dataclasses import dataclass, field


@dataclass
class Item:
    sku: str
    name: str
    price: float
    stock: int
    max_capacity: int = 100


@dataclass
class Inventory:
    items: dict = field(default_factory=dict)

    def add_item(self, item: Item):
        self.items[item.sku] = item

    def restock(self, sku: str, quantity: int) -> int:
        item = self.items[sku]
        # Clamp the stock to the item's maximum capacity
        item.stock = min(item.stock + quantity, item.max_capacity)
        return item.stock

    def apply_discount(self, sku: str, percent_off: float) -> float:
        item = self.items[sku]
        discounted = item.price * (1 - percent_off / 100)
        # Round to two decimal places instead of truncating
        return round(discounted, 2)

    def is_free(self, sku: str) -> bool:
        item = self.items[sku]
        return item.price == 0

    def checkout(self, sku: str, quantity: int) -> float:
        item = self.items[sku]
        # Reject non-positive quantities
        if quantity <= 0:
            raise ValueError(f"Quantity must be positive for {sku}")
        if item.stock < quantity:
            raise ValueError(f"Not enough stock for {sku}")
        item.stock -= quantity
        if self.is_free(sku):
            return 0.0
        return round(item.price * quantity, 2)
