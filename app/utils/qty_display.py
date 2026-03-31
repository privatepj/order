from __future__ import annotations

from decimal import Decimal, InvalidOperation


def format_qty_plain(val) -> str:
    """数量展示：去掉无意义尾随零，整数不显示小数点。"""
    if val is None:
        return "-"
    try:
        d = val if isinstance(val, Decimal) else Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return "-"
    d = d.normalize()
    if d.is_zero():
        return "0"
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s
