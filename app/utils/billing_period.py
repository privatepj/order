"""按转月日计算业务月起止（含月末日期裁剪）。"""
import calendar
from datetime import date, datetime
from typing import Tuple


def _safe_day(year: int, month: int, day: int) -> int:
    last = calendar.monthrange(year, month)[1]
    return min(max(1, day), last)


def period_start_containing(d: date, cycle_day: int) -> date:
    """包含日期 d 的业务周期起始日。"""
    if not cycle_day or cycle_day <= 1:
        return date(d.year, d.month, 1)
    y, m, day = d.year, d.month, d.day
    sd = _safe_day(y, m, cycle_day)
    if day >= sd:
        return date(y, m, sd)
    if m == 1:
        py, pm = y - 1, 12
    else:
        py, pm = y, m - 1
    return date(py, pm, _safe_day(py, pm, cycle_day))


def next_period_start(period_start: date, cycle_day: int) -> date:
    """下一业务周期起始日。"""
    if not cycle_day or cycle_day <= 1:
        y, m = period_start.year, period_start.month
        if m == 12:
            return date(y + 1, 1, 1)
        return date(y, m + 1, 1)
    y, m = period_start.year, period_start.month
    if m == 12:
        return date(y + 1, 1, _safe_day(y + 1, 1, cycle_day))
    return date(y, m + 1, _safe_day(y, m + 1, cycle_day))


def period_bounds_containing(d: date, cycle_day: int) -> Tuple[datetime, datetime]:
    """[start, end) 用于 created_at 比较。"""
    ps = period_start_containing(d, cycle_day)
    pe = next_period_start(ps, cycle_day)
    start_dt = datetime.combine(ps, datetime.min.time())
    end_dt = datetime.combine(pe, datetime.min.time())
    return start_dt, end_dt


def reconciliation_period(year: int, month: int, cycle_day: int) -> Tuple[date, date]:
    """
    对账所选「年月」对应的闭区间 [start, end]。
    cycle_day<=1：自然月。
    cycle_day>=2：上月 cycle_day 日 ~ 本月 cycle_day-1 日（如 2 月对账、26 日 -> 1/26~2/25）。
    """
    if not cycle_day or cycle_day <= 1:
        last = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last)
    end_day = cycle_day - 1
    end = date(year, month, _safe_day(year, month, end_day))
    if month == 1:
        py, pm = year - 1, 12
    else:
        py, pm = year, month - 1
    start = date(py, pm, _safe_day(py, pm, cycle_day))
    return start, end


def reconciliation_period_caption(year: int, month: int, cycle_day: int) -> str:
    """对账单副标题文案。"""
    if not cycle_day or cycle_day <= 1:
        last = calendar.monthrange(year, month)[1]
        return (
            f"{year}年{month}月份对帐单（从本月1日起至本月{last}日止）"
        )
    d2 = cycle_day - 1
    return (
        f"{year}年{month}月份对帐单（从上月{cycle_day}日起至本月{d2}日止）"
    )
