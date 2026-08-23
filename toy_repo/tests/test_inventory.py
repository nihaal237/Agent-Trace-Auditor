import pytest
from inventory import Inventory, Item


@pytest.fixture
def inv():
    i = Inventory()
    i.add_item(Item(sku="WIDGET", name="Widget", price=10.0, stock=5, max_capacity=20))
    i.add_item(Item(sku="SAMPLE", name="Free Sample", price=0.0, stock=5, max_capacity=20))
    return i


def test_restock_caps_at_max_capacity(inv):
    # BUG_B: currently fails, restock overflows past max_capacity
    inv.restock("WIDGET", 50)
    assert inv.items["WIDGET"].stock <= inv.items["WIDGET"].max_capacity


def test_restock_normal_case(inv):
    inv.restock("WIDGET", 3)
    assert inv.items["WIDGET"].stock == 8


def test_apply_discount_rounds_correctly(inv):
    # BUG_A: truncation vs rounding diverge here.
    # 1.999 * (1 - 0/100) = 1.999 -> should ROUND to 2.0, buggy code TRUNCATES to 1.99
    inv.items["WIDGET"].price = 1.999
    result = inv.apply_discount("WIDGET", 0)
    assert result == 2.0


def test_free_sample_checkout_is_zero(inv):
    # Guards against the regression: a careless fix to apply_discount's
    # rounding must not change how "free" items are detected in checkout.
    total = inv.checkout("SAMPLE", 2)
    assert total == 0.0
    assert inv.items["SAMPLE"].stock == 3


def test_normal_checkout_charges_correct_total(inv):
    total = inv.checkout("WIDGET", 2)
    assert total == 20.0
    assert inv.items["WIDGET"].stock == 3