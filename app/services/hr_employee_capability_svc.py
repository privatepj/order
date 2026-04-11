from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional

from sqlalchemy import func, or_

from app import db
from app.models import (
    HrEmployee,
    HrEmployeeCapability,
    HrEmployeeScheduleBooking,
    HrPayrollLine,
    HrWorkTypePieceRate,
)


def _floor_to_minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


def _parse_period(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _hourly_wage_for_employee_month(*, payroll: HrPayrollLine) -> Decimal:
    if payroll.wage_kind == "hourly":
        return Decimal(payroll.hourly_rate or 0)
    work_hours = payroll.work_hours or Decimal(0)
    if work_hours <= 0:
        return Decimal(0)
    return Decimal(payroll.net_pay) / Decimal(work_hours)


def hourly_wage_for_employee_period(*, company_id: int, employee_id: int, period: str) -> Decimal:
    payroll = HrPayrollLine.query.filter_by(
        company_id=company_id,
        employee_id=employee_id,
        period=period,
    ).first()
    if not payroll:
        return Decimal(0)
    return _hourly_wage_for_employee_month(payroll=payroll)


def _resolved_work_type_id(booking: HrEmployeeScheduleBooking) -> int:
    return int(booking.work_type_id or booking.hr_department_id or 0)


def _booking_dimension_filter(employee_id: int, work_type_id: int):
    return (
        HrEmployeeScheduleBooking.employee_id == employee_id,
        HrEmployeeScheduleBooking.state == "available",
        HrEmployeeScheduleBooking.work_order_id.isnot(None),
        or_(
            HrEmployeeScheduleBooking.work_type_id == work_type_id,
            (HrEmployeeScheduleBooking.work_type_id.is_(None) & (HrEmployeeScheduleBooking.hr_department_id == work_type_id)),
        ),
    )


def _update_employee_capability_one_minute(*, window_end: datetime) -> Dict[str, int]:
    window_start = window_end - timedelta(minutes=1)
    if window_end <= window_start:
        return {"groups_updated": 0, "cap_rows_created": 0}

    booking_rows = (
        HrEmployeeScheduleBooking.query.filter(
            HrEmployeeScheduleBooking.state == "available",
            HrEmployeeScheduleBooking.work_order_id.isnot(None),
            or_(
                HrEmployeeScheduleBooking.work_type_id.isnot(None),
                HrEmployeeScheduleBooking.hr_department_id.isnot(None),
            ),
            HrEmployeeScheduleBooking.start_at < window_end,
            HrEmployeeScheduleBooking.end_at > window_start,
        )
        .order_by(HrEmployeeScheduleBooking.start_at.asc(), HrEmployeeScheduleBooking.id.asc())
        .all()
    )
    if not booking_rows:
        return {"groups_updated": 0, "cap_rows_created": 0}

    pair_keys = {
        (int(row.employee_id), _resolved_work_type_id(row))
        for row in booking_rows
        if int(row.employee_id or 0) > 0 and _resolved_work_type_id(row) > 0
    }
    if not pair_keys:
        return {"groups_updated": 0, "cap_rows_created": 0}

    employee_ids = {employee_id for employee_id, _ in pair_keys}
    employees: list[HrEmployee] = HrEmployee.query.filter(HrEmployee.id.in_(employee_ids)).all()
    company_by_employee = {int(row.id): int(row.company_id) for row in employees}

    groups_updated = 0
    cap_rows_created = 0

    for employee_id, work_type_id in pair_keys:
        company_id = company_by_employee.get(employee_id)
        if not company_id:
            continue

        cap = HrEmployeeCapability.query.filter_by(
            company_id=company_id,
            employee_id=employee_id,
            work_type_id=work_type_id,
        ).first()
        if cap:
            from_ts = cap.processed_to or window_start
            if cap.processed_to and cap.processed_to >= window_end:
                continue
        else:
            earliest_start = (
                HrEmployeeScheduleBooking.query.filter(
                    *_booking_dimension_filter(employee_id, work_type_id),
                )
                .order_by(HrEmployeeScheduleBooking.start_at.asc())
                .with_entities(HrEmployeeScheduleBooking.start_at)
                .first()
            )
            from_ts = earliest_start[0] if earliest_start is not None else window_start
            cap = HrEmployeeCapability(
                company_id=company_id,
                employee_id=employee_id,
                hr_department_id=work_type_id,
                work_type_id=work_type_id,
                processed_to=from_ts,
            )
            db.session.add(cap)
            cap_rows_created += 1

        scoped_rows = (
            HrEmployeeScheduleBooking.query.filter(
                *_booking_dimension_filter(employee_id, work_type_id),
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
        work_order_ids_to_add = set()

        for booking in scoped_rows:
            booking_start = booking.start_at
            booking_end = booking.end_at
            if booking_end <= booking_start:
                continue
            overlap_start = max(booking_start, from_ts)
            overlap_end = min(booking_end, window_end)
            if overlap_end <= overlap_start:
                continue

            overlap_seconds = int((overlap_end - overlap_start).total_seconds())
            booking_seconds = int((booking_end - booking_start).total_seconds())
            if overlap_seconds <= 0 or booking_seconds <= 0:
                continue

            factor = Decimal(overlap_seconds) / Decimal(booking_seconds)
            good_delta = Decimal(booking.good_qty or 0) * factor
            bad_delta = Decimal(booking.bad_qty or 0) * factor
            produced = good_delta + bad_delta

            good_delta_total += good_delta
            bad_delta_total += bad_delta
            produced_delta += produced
            worked_seconds_delta += overlap_seconds

            if (
                booking.work_order_id is not None
                and booking.start_at >= from_ts
                and booking.start_at < window_end
            ):
                work_order_ids_to_add.add(int(booking.work_order_id))

        if worked_seconds_delta > 0:
            worked_minutes_delta = Decimal(worked_seconds_delta) / Decimal(60)
            cap.good_qty_total = Decimal(cap.good_qty_total or 0) + good_delta_total
            cap.bad_qty_total = Decimal(cap.bad_qty_total or 0) + bad_delta_total
            cap.produced_qty_total = Decimal(cap.produced_qty_total or 0) + produced_delta
            cap.worked_minutes_total = Decimal(cap.worked_minutes_total or 0) + worked_minutes_delta
            cap.work_order_cnt_total = int(cap.work_order_cnt_total or 0) + len(work_order_ids_to_add)

            payroll_period = _parse_period(window_start)
            payroll: Optional[HrPayrollLine] = HrPayrollLine.query.filter_by(
                company_id=company_id,
                employee_id=employee_id,
                period=payroll_period,
            ).first()
            if payroll and payroll.wage_kind == "piece_rate":
                piece_rate_row = HrWorkTypePieceRate.query.filter_by(
                    company_id=company_id,
                    work_type_id=work_type_id,
                    period=payroll_period,
                ).first()
                rate = Decimal(piece_rate_row.rate_per_unit) if piece_rate_row else Decimal(0)
                labor_cost_delta = rate * produced_delta
            else:
                hourly_wage = _hourly_wage_for_employee_month(payroll=payroll) if payroll else Decimal(0)
                labor_cost_delta = hourly_wage * (worked_minutes_delta / Decimal(60))
            cap.labor_cost_total = Decimal(cap.labor_cost_total or 0) + labor_cost_delta

        cap.processed_to = window_end
        groups_updated += 1

    db.session.flush()
    return {"groups_updated": groups_updated, "cap_rows_created": cap_rows_created}


def update_employee_capability(*, to_dt: datetime, max_backfill_minutes: int = 10080) -> Dict[str, int]:
    last_we = _floor_to_minute(to_dt)
    min_start = (
        db.session.query(func.min(HrEmployeeScheduleBooking.start_at))
        .filter(
            HrEmployeeScheduleBooking.state == "available",
            HrEmployeeScheduleBooking.work_order_id.isnot(None),
            or_(
                HrEmployeeScheduleBooking.work_type_id.isnot(None),
                HrEmployeeScheduleBooking.hr_department_id.isnot(None),
            ),
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
