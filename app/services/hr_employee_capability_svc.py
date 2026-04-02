from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional

from sqlalchemy import func

from app import db
from app.models import HrEmployee, HrEmployeeCapability, HrEmployeeScheduleBooking, HrPayrollLine


def _floor_to_minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


def _overlap_seconds(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> int:
    # [a_start, a_end) 与 [b_start, b_end) 的重叠秒数（向下取整到秒；入参均为分钟粒度）
    s = max(a_start, b_start)
    e = min(a_end, b_end)
    if e <= s:
        return 0
    return int((e - s).total_seconds())


def _parse_period(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _hourly_wage_for_employee_month(*, payroll: HrPayrollLine) -> Decimal:
    if payroll.wage_kind == "hourly":
        return Decimal(payroll.hourly_rate or 0)
    # monthly：按 net_pay / work_hours 换算成时薪
    wh = payroll.work_hours or Decimal(0)
    if wh <= 0:
        return Decimal(0)
    return Decimal(payroll.net_pay) / Decimal(wh)


def hourly_wage_for_employee_period(*, company_id: int, employee_id: int, period: str) -> Decimal:
    """指定账期工资行换算时薪（无记录则 0）。"""
    payroll = HrPayrollLine.query.filter_by(
        company_id=company_id, employee_id=employee_id, period=period
    ).first()
    if not payroll:
        return Decimal(0)
    return _hourly_wage_for_employee_month(payroll=payroll)


def _update_employee_capability_one_minute(*, window_end: datetime) -> Dict[str, int]:
    """
    处理单个分钟窗口 [window_end-1min, window_end)。
    以 hr_employee_capability.processed_to 做增量边界，避免重复统计历史 log。
    """

    window_start = window_end - timedelta(minutes=1)
    if window_end <= window_start:
        return {"groups_updated": 0, "cap_rows_created": 0}

    # 找出本分钟窗口内参与统计的 (employee_id, hr_department_id)
    pairs = (
        HrEmployeeScheduleBooking.query.with_entities(
            HrEmployeeScheduleBooking.employee_id, HrEmployeeScheduleBooking.hr_department_id
        )
        .filter(
            HrEmployeeScheduleBooking.state == "available",
            HrEmployeeScheduleBooking.work_order_id.isnot(None),
            HrEmployeeScheduleBooking.hr_department_id.isnot(None),
            HrEmployeeScheduleBooking.start_at < window_end,
            HrEmployeeScheduleBooking.end_at > window_start,
        )
        .distinct()
        .all()
    )

    if not pairs:
        return {"groups_updated": 0, "cap_rows_created": 0}

    employee_ids = {int(emp_id) for emp_id, _ in pairs if emp_id is not None}
    employees: list[HrEmployee] = HrEmployee.query.filter(HrEmployee.id.in_(employee_ids)).all()
    company_by_employee = {int(e.id): int(e.company_id) for e in employees}

    groups_updated = 0
    cap_rows_created = 0

    for employee_id, hr_department_id in pairs:
        if employee_id is None or hr_department_id is None:
            continue
        employee_id = int(employee_id)
        hr_department_id = int(hr_department_id)

        company_id = company_by_employee.get(employee_id)
        if not company_id:
            # 不完整数据兜底：无法确定主体则跳过
            continue

        cap: Optional[HrEmployeeCapability] = (
            HrEmployeeCapability.query.filter_by(
                company_id=company_id, employee_id=employee_id, hr_department_id=hr_department_id
            ).first()
        )

        if cap:
            # 增量边界：cap.processed_to 之前已覆盖，无需重复统计
            from_ts = cap.processed_to or window_start
            if cap.processed_to and cap.processed_to >= window_end:
                continue
        else:
            # 首次出现：回填该 employee+工位 的历史（直到当前 window_end）
            earliest_start = (
                HrEmployeeScheduleBooking.query.filter(
                    HrEmployeeScheduleBooking.employee_id == employee_id,
                    HrEmployeeScheduleBooking.hr_department_id == hr_department_id,
                    HrEmployeeScheduleBooking.state == "available",
                    HrEmployeeScheduleBooking.work_order_id.isnot(None),
                )
                .order_by(HrEmployeeScheduleBooking.start_at.asc())
                .with_entities(HrEmployeeScheduleBooking.start_at)
                .first()
            )
            # .first() 在 SQLAlchemy 2 为 Row，不是 tuple；须取 [0] 得到 datetime
            from_ts = earliest_start[0] if earliest_start is not None else None
            if not from_ts:
                from_ts = window_start

            cap = HrEmployeeCapability(
                company_id=company_id,
                employee_id=employee_id,
                hr_department_id=hr_department_id,
                processed_to=from_ts,
            )
            db.session.add(cap)
            cap_rows_created += 1

        # 读取未覆盖区间上的排产工作log
        # 条件：booking 与 [from_ts, window_end) 有重叠
        booking_rows: list[HrEmployeeScheduleBooking] = (
            HrEmployeeScheduleBooking.query.filter(
                HrEmployeeScheduleBooking.employee_id == employee_id,
                HrEmployeeScheduleBooking.hr_department_id == hr_department_id,
                HrEmployeeScheduleBooking.state == "available",
                HrEmployeeScheduleBooking.work_order_id.isnot(None),
                HrEmployeeScheduleBooking.start_at < window_end,
                HrEmployeeScheduleBooking.end_at > from_ts,
            )
            .order_by(HrEmployeeScheduleBooking.start_at.asc(), HrEmployeeScheduleBooking.id.asc())
            .all()
        )

        worked_seconds_delta = 0
        produced_delta = Decimal("0")
        good_delta_total = Decimal("0")
        bad_delta_total = Decimal("0")

        # 工单数：仅在 booking.start_at 落入“本次增量区间”时计入，避免同一工单跨多个统计窗口重复计数
        work_order_ids_to_add = set()

        for b in booking_rows:
            booking_start = b.start_at
            booking_end = b.end_at
            if booking_end <= booking_start:
                continue
            overlap_s = max(booking_start, from_ts)
            overlap_e = min(booking_end, window_end)
            if overlap_e <= overlap_s:
                continue

            overlap_seconds = int((overlap_e - overlap_s).total_seconds())
            if overlap_seconds <= 0:
                continue
            booking_seconds = int((booking_end - booking_start).total_seconds())
            if booking_seconds <= 0:
                continue

            factor = Decimal(overlap_seconds) / Decimal(booking_seconds)
            gd = Decimal(b.good_qty) * factor
            bd = Decimal(b.bad_qty) * factor
            pd = gd + bd

            good_delta_total += gd
            bad_delta_total += bd
            produced_delta += pd
            worked_seconds_delta += overlap_seconds

            if (
                b.work_order_id is not None
                and overlap_seconds > 0
                and b.start_at >= from_ts
                and b.start_at < window_end
            ):
                work_order_ids_to_add.add(int(b.work_order_id))

        # 工时/产能为增量；若本分钟无重叠，则仅推进 processed_to
        if worked_seconds_delta > 0:
            worked_minutes_delta = Decimal(worked_seconds_delta) / Decimal(60)
            cap.good_qty_total = Decimal(cap.good_qty_total) + good_delta_total
            cap.bad_qty_total = Decimal(cap.bad_qty_total) + bad_delta_total
            cap.produced_qty_total = Decimal(cap.produced_qty_total) + produced_delta
            cap.worked_minutes_total = Decimal(cap.worked_minutes_total) + worked_minutes_delta

            cap.work_order_cnt_total = int(cap.work_order_cnt_total or 0) + len(work_order_ids_to_add)

            # 劳动力成本：按本分钟窗口起点的账期换算时薪
            payroll_period = _parse_period(window_start)
            payroll: Optional[HrPayrollLine] = (
                HrPayrollLine.query.filter_by(company_id=company_id, employee_id=employee_id, period=payroll_period)
                .first()
            )
            hourly_wage = _hourly_wage_for_employee_month(payroll=payroll) if payroll else Decimal(0)
            labor_cost_delta = hourly_wage * (worked_minutes_delta / Decimal(60))
            cap.labor_cost_total = Decimal(cap.labor_cost_total) + labor_cost_delta

        cap.processed_to = window_end
        groups_updated += 1

    db.session.flush()
    return {"groups_updated": groups_updated, "cap_rows_created": cap_rows_created}


def update_employee_capability(*, to_dt: datetime, max_backfill_minutes: int = 10080) -> Dict[str, int]:
    """
    按分钟增量更新人员能力表。
    单次调用会从「最早一条符合条件的排班」起，顺序处理到 to_dt 对齐的分钟（最多回溯 max_backfill_minutes 个分钟窗口），
    避免只扫「当前这一分钟」导致手动执行时 groups_updated 恒为 0。
    """
    last_we = _floor_to_minute(to_dt)
    min_start = (
        db.session.query(func.min(HrEmployeeScheduleBooking.start_at))
        .filter(
            HrEmployeeScheduleBooking.state == "available",
            HrEmployeeScheduleBooking.work_order_id.isnot(None),
            HrEmployeeScheduleBooking.hr_department_id.isnot(None),
        )
        .scalar()
    )
    if not min_start:
        return {"groups_updated": 0, "cap_rows_created": 0}

    first_we = _floor_to_minute(min_start) + timedelta(minutes=1)
    earliest_we = last_we - timedelta(minutes=max(1, max_backfill_minutes) - 1)
    we_start = max(first_we, earliest_we)
    if we_start > last_we:
        return {"groups_updated": 0, "cap_rows_created": 0}

    total_groups = 0
    total_created = 0
    we = we_start
    while we <= last_we:
        sub = _update_employee_capability_one_minute(window_end=we)
        total_groups += int(sub.get("groups_updated") or 0)
        total_created += int(sub.get("cap_rows_created") or 0)
        we += timedelta(minutes=1)

    return {"groups_updated": total_groups, "cap_rows_created": total_created}

