from decimal import Decimal

from app.utils.qty_display import format_qty_plain


def test_format_qty_plain_scientific_zero():
    assert format_qty_plain(Decimal("0E-8")) == "0"


def test_format_qty_plain_strips_trailing_zeros():
    assert format_qty_plain(Decimal("3.00000000")) == "3"
    assert format_qty_plain(Decimal("4.0")) == "4"


def test_format_qty_plain_keeps_significant_fraction():
    s = format_qty_plain(Decimal("3.25"))
    assert s == "3.25"


def test_format_qty_plain_none():
    assert format_qty_plain(None) == "-"
