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


def expand_waybill_range(start: str, end: str, step: int = 1) -> List[str]:
    """
    起止须为同一前缀、数字段等宽；从起始数字起每次加 step，生成不超过结束数字的单号列表（含起止范围内可达项）。
    step 默认为 1，即原先连续递增行为。
    """
    if not isinstance(step, int) or step < 1:
        raise ValueError("单号间隔须为正整数")
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
    if n1 > max_v or n2 > max_v:
        raise ValueError("结束单号超出数字位允许范围")
    nums: List[int] = []
    cur = n1
    while cur <= n2:
        if cur > max_v:
            raise ValueError("递增后单号超出数字位允许范围")
        nums.append(cur)
        cur += step
    count = len(nums)
    if count > 50000:
        raise ValueError("单次最多录入 50000 个单号")
    return [f"{p1}{n:0{width}d}" for n in nums]
