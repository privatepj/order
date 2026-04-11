"""全库业务数值统一标度（与 MySQL decimal(26,8) 一致）。"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

DECIMAL_SCALE = 8
QUANT = Decimal("1e-8")


def quantize_decimal(val: Any, rounding=ROUND_HALF_UP) -> Decimal:
    """将 Decimal 或可转字符串的数值量化到 DECIMAL_SCALE 位小数。"""
    if val is None:
        return Decimal(0)
    try:
        d = val if isinstance(val, Decimal) else Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(0)
    return d.quantize(QUANT, rounding=rounding)


def to_decimal(val: Any) -> Decimal:
    """解析为 Decimal（失败则 0），不主动 quantize。"""
    if val is None:
        return Decimal(0)
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(0)


def json_decimal(val: Any) -> str:
    """JSON / OpenClaw 等对外输出：十进制字符串（最多 8 位小数，去无意义尾随零），避免 float。"""
    d = quantize_decimal(val)
    s = format(d, "f").rstrip("0").rstrip(".")
    return s if s else "0"
