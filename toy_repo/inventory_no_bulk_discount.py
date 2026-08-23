"""
Tiny inventory management module.

Bugs fixed:
- restock() now clamps to max_capacity.
- apply_discount() now rounds instead of truncating.
- is_free() left untouched, so no regression is introduced.

Deliberately, no new test was added for the new "clamped" behavior of
restock() beyond what already existed - that's the test debt this
scenario is designed to surface.
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
        """Add stock, clamped to max_capacity."""
        item = self.items[sku]
        item.stock = min(item.stock + quantity, item.max_capacity)
        return item.stock

    def apply_discount(self, sku: str, percent_off: float) -> float:
        """Return discounted price, correctly rounded."""
        item = self.items[sku]
        discounted = item.price * (1 - percent_off / 100)
        return round(discounted, 2)

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