from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import List, Set, Tuple

from sqlalchemy import or_

from app import db
from app.models import HrEmployee, HrEmployeeScheduleBooking, HrEmployeeScheduleTemplate


def _dt_minute_floor(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


def _parse_days_of_week_csv(days_of_week: str) -> Set[int]:
    """
    days_of_week: "0,1,2,3,4,5,6" 其中 0=周日 .. 6=周六
    """
    raw = (days_of_week or "").strip()
    if not raw:
        return set()
    out: Set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            v = int(part)
        except ValueError:
            continue
        if 0 <= v <= 6:
            out.add(v)
    return out


def _py_date_weekday_code(d: date) -> int:
    """
    Python weekday: Mon=0..Sun=6
    业务要求：0=周日..6=周六
    """
    wd = d.weekday()
    return 0 if wd == 6 else wd + 1


def _template_interval_for_date(
    *, tpl: HrEmployeeScheduleTemplate, d: date
) -> Tuple[datetime, datetime]:
    start_dt = datetime.combine(d, tpl.start_time)
    end_dt = datetime.combine(d, tpl.end_time)
    # 跨日：结束时间 <= 开始时间，视为次日结束
    if end_dt <= start_dt:
        end_dt = end_dt + timedelta(days=1)
    return _dt_minute_floor(start_dt), _dt_minute_floor(end_dt)


def _intervals_overlap(
    a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime
) -> bool:
    # [a_start, a_end) 与 [b_start, b_end) 是否重叠
    return a_start < b_end and b_start < a_end


def generate_bookings_for_range(
    *,
    employee_id: int,
    from_date: date,
    to_date: date,
    created_by: int,
) -> None:
    """
    将某人员在 [from_date, to_date]（日期含边界）上的“每周模板”展开为分钟粒度时间窗。

    - 幂等：同一 `template_id + start_at` 若已存在则跳过。
    - 冲突：同一 employee 的任意时间窗不得重叠；一旦检测到重叠直接抛错由上层处理。
    """
    if employee_id <= 0:
        raise ValueError("employee_id 必填。")
    if from_date > to_date:
        raise ValueError("from_date 不能晚于 to_date。")

    employee = HrEmployee.query.get(employee_id)
    if not employee:
        raise ValueError("人员不存在。")

    tpl_rows: List[HrEmployeeScheduleTemplate] = (
        HrEmployeeScheduleTemplate.query.filter(
            HrEmployeeScheduleTemplate.employee_id == employee_id,
            HrEmployeeScheduleTemplate.valid_from <= to_date,
            or_(
                HrEmployeeScheduleTemplate.valid_to.is_(None),
                HrEmployeeScheduleTemplate.valid_to >= from_date,
            ),
        )
        .order_by(HrEmployeeScheduleTemplate.id.asc())
        .all()
    )
    if not tpl_rows:
        return

    existing_rows = (
        HrEmployeeScheduleBooking.query.filter(
            HrEmployeeScheduleBooking.employee_id == employee_id,
            HrEmployeeScheduleBooking.start_at
            < datetime.combine(to_date + timedelta(days=1), time.min),
            HrEmployeeScheduleBooking.end_at > datetime.combine(from_date, time.min),
        )
        .order_by(HrEmployeeScheduleBooking.start_at.asc(), HrEmployeeScheduleBooking.id.asc())
        .all()
    )

    # 用于快速判断幂等：template_id + start_at
    existing_key_set = {
        (int(r.template_id), r.start_at)  # datetime 直接用于 key：调用处已 floor to minute
        for r in existing_rows
    }
    existing_intervals = [(r.start_at, r.end_at, int(r.id)) for r in existing_rows]

    try:
        for tpl in tpl_rows:
            days_set = _parse_days_of_week_csv(tpl.days_of_week)
            if not days_set:
                continue

            s = max(from_date, tpl.valid_from)
            e = min(to_date, tpl.valid_to) if tpl.valid_to else to_date

            cur = s
            while cur <= e:
                code = _py_date_weekday_code(cur)
                if code in days_set:
                    start_at, end_at = _template_interval_for_date(tpl=tpl, d=cur)
                    key = (int(tpl.id), start_at)
                    if key in existing_key_set:
                        cur = cur + timedelta(days=1)
                        continue

                    # 冲突：新窗口与现有窗口任意重叠则报错
                    for ex_s, ex_e, ex_id in existing_intervals:
                        if _intervals_overlap(start_at, end_at, ex_s, ex_e):
                            raise ValueError(
                                f"人员排产窗口冲突：新窗口[{start_at},{end_at}) 与现有 booking_id={ex_id} 重叠。"
                            )

                    row = HrEmployeeScheduleBooking(
                        employee_id=employee_id,
                        template_id=int(tpl.id),
                        state=tpl.state,
                        start_at=start_at,
                        end_at=end_at,
                        # 由模板继承 remark，用户可后续编辑填工作log字段
                        remark=tpl.remark,
                        created_by=created_by,
                    )
                    db.session.add(row)
                    db.session.flush()

                    existing_key_set.add(key)
                    existing_intervals.append((start_at, end_at, int(row.id)))

                cur = cur + timedelta(days=1)

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

