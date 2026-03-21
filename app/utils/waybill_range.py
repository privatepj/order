"""快递单号起止区间解析与展开。"""
import re
from typing import List, Tuple


def _split_trailing_digits(s: str) -> Tuple[str, str]:
    s = (s or "").strip()
    if not s:
        raise ValueError("单号不能为空")
    m = re.match(r"^(.*?)(\d+)$", s)
    if not m:
        raise ValueError("单号须以数字结尾，例如 SF1234567890123")
    prefix, digits = m.group(1), m.group(2)
    if not digits:
        raise ValueError("末尾数字段无效")
    return prefix, digits


def expand_waybill_range(start: str, end: str) -> List[str]:
    """
    起止须为同一前缀、数字段等宽；按数字递增生成闭区间 [start, end]。
    """
    p1, d1 = _split_trailing_digits(start)
    p2, d2 = _split_trailing_digits(end)
    if p1 != p2:
        raise ValueError("起始与结束单号的前缀必须一致")
    if len(d1) != len(d2):
        raise ValueError("起始与结束单号的数字位数必须一致")
    n1, n2 = int(d1), int(d2)
    if n2 < n1:
        raise ValueError("结束单号不能小于起始单号")
    width = len(d1)
    max_v = 10**width - 1
    if n2 > max_v:
        raise ValueError("结束单号超出数字位允许范围")
    count = n2 - n1 + 1
    if count > 50000:
        raise ValueError("单次最多录入 50000 个单号")
    return [f"{p1}{n1 + i:0{width}d}" for i in range(count)]
