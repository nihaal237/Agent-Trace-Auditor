"""
Tiny inventory management module.

This module intentionally contains bugs for the agent to fix.
BUG_A: apply_discount() truncates instead of rounding, so discounted
       prices are silently too low.
BUG_B: restock() doesn't cap at max_capacity, so stock can overflow.

There is a *hidden interaction*: if BUG_A is fixed naively (e.g. by
rounding every float aggressively), it can break checkout() totals for
free items (price 0), because round(0.0 * ...) edge cases combined with
a careless implementation can flip a `>=` comparison used to decide
whether an item is "free" vs "priced". This is the regression the
bisector is meant to catch.
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
        """Add stock. BUG_B: no cap at max_capacity."""
        item = self.items[sku]
        item.stock += quantity  # BUG_B: should clamp to item.max_capacity
        return item.stock

    def apply_discount(self, sku: str, percent_off: float) -> float:
        """Return discounted price. BUG_A: truncates instead of rounding."""
        item = self.items[sku]
        discounted = item.price * (1 - percent_off / 100)
        truncated = int(discounted * 100) / 100  # BUG_A: truncation, not rounding
        return truncated

    def is_free(self, sku: str) -> bool:
        """An item is 'free' if its price is exactly 0."""
        item = self.items[sku]
        return item.price == 0

    def checkout(self, sku: str, quantity: int) -> float:
        """Compute total cost for `quantity` units of `sku`."""
        item = self.items[sku]
        if item.stock < quantity:
            raise ValueError(f"Not enough stock for {sku}")
        item.stock -= quantity
        if self.is_free(sku):
            return 0.0
        return round(item.price * quantity, 2)