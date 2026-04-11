from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import List, Set, Tuple

from sqlalchemy import or_

from app import db
from app.utils.decimal_scale import quantize_decimal
from app.models import (
    Machine,
    MachineRuntimeLog,
    MachineScheduleBooking,
    MachineScheduleDispatchLog,
    MachineScheduleTemplate,
)


_MACHINE_SCHEDULE_STATE_AVAILABLE = "available"
_MACHINE_SCHEDULE_STATE_UNAVAILABLE = "unavailable"


def _dt_minute_floor(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


def _parse_days_of_week_csv(days_of_week: str) -> Set[int]:
    """
    days_of_week: "0,1,2,3,4,5,6" 其中 0=周日 ... 6=周六
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


def _template_interval_for_date(*, tpl: MachineScheduleTemplate, d: date) -> Tuple[datetime, datetime]:
    start_dt = datetime.combine(d, tpl.start_time)
    end_dt = datetime.combine(d, tpl.end_time)
    # 跨日：结束时间 <= 开始时间，视为次日结束
    if end_dt <= start_dt:
        end_dt = end_dt + timedelta(days=1)
    return _dt_minute_floor(start_dt), _dt_minute_floor(end_dt)


def _intervals_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    # [a_start, a_end) 与 [b_start, b_end) 是否重叠
    return a_start < b_end and b_start < a_end


def generate_bookings_for_range(
    *,
    machine_id: int,
    from_date: date,
    to_date: date,
    created_by: int,
) -> None:
    """
    将某机台在 [from_date, to_date]（日期含边界）上的“每周模板”展开为分钟粒度时间窗。

    - 幂等：同一 `template_id + start_at` 若已存在则跳过。
    - 冲突：同一机台的任意时间窗不得重叠；一旦检测到重叠直接抛错由上层处理。
    """
    if not machine_id:
        raise ValueError("machine_id 必填。")
    if from_date > to_date:
        raise ValueError("from_date 不能晚于 to_date。")

    machine = Machine.query.get(machine_id)
    if not machine:
        raise ValueError("机台不存在。")

    tpl_rows: List[MachineScheduleTemplate] = (
        MachineScheduleTemplate.query.filter(
            MachineScheduleTemplate.machine_id == machine_id,
            MachineScheduleTemplate.valid_from <= to_date,
            or_(
                MachineScheduleTemplate.valid_to.is_(None),
                MachineScheduleTemplate.valid_to >= from_date,
            ),
        )
        .order_by(MachineScheduleTemplate.id.asc())
        .all()
    )
    if not tpl_rows:
        return

    # 生成窗口（分钟级）与现有窗口的冲突检查
    existing_rows = (
        MachineScheduleBooking.query.filter(
            MachineScheduleBooking.machine_id == machine_id,
            MachineScheduleBooking.start_at < datetime.combine(to_date + timedelta(days=1), time.min),
            MachineScheduleBooking.end_at > datetime.combine(from_date, time.min),
        )
        .order_by(MachineScheduleBooking.start_at.asc(), MachineScheduleBooking.id.asc())
        .all()
    )

    # 用于快速判断幂等：template_id + start_at
    existing_key_set = {(int(r.template_id), r.start_at) for r in existing_rows}

    existing_intervals = [(r.start_at, r.end_at, int(r.id)) for r in existing_rows]

    try:
        for tpl in tpl_rows:
            days_set = _parse_days_of_week_csv(tpl.days_of_week)
            if not days_set:
                continue

            # 只遍历模板有效期与目标范围的交集日期
            s = max(from_date, tpl.valid_from)
            e = min(to_date, tpl.valid_to) if tpl.valid_to else to_date
            cur = s
            while cur <= e:
                code = _py_date_weekday_code(cur)
                if code in days_set:
                    start_at, end_at = _template_interval_for_date(tpl=tpl, d=cur)
                    # idempotent: 若已存在则跳过（不再检查冲突）
                    key = (int(tpl.id), start_at)
                    if key in existing_key_set:
                        # 如果 booking 已存在但 dispatch log 不存在（例如：新增迁移后历史数据），补写 scheduled log
                        existing_booking = (
                            MachineScheduleBooking.query.filter_by(
                                template_id=int(tpl.id), start_at=start_at
                            ).first()
                        )
                        if existing_booking:
                            existing_dispatch = MachineScheduleDispatchLog.query.filter_by(
                                booking_id=existing_booking.id
                            ).first()
                            if not existing_dispatch:
                                duration_seconds = int((end_at - start_at).total_seconds())
                                duration_hours = quantize_decimal(
                                    Decimal(duration_seconds) / Decimal(3600)
                                )
                                db.session.add(
                                    MachineScheduleDispatchLog(
                                        machine_id=machine_id,
                                        booking_id=existing_booking.id,
                                        dispatch_start_at=start_at,
                                        dispatch_end_at=end_at,
                                        planned_runtime_hours=duration_hours,
                                        state="scheduled",
                                        remark=tpl.remark,
                                    )
                                )
                        cur = cur + timedelta(days=1)
                        continue

                    # 冲突：新窗口与现有窗口任意重叠则报错
                    for ex_s, ex_e, ex_id in existing_intervals:
                        if _intervals_overlap(start_at, end_at, ex_s, ex_e):
                            raise ValueError(
                                f"机台排班窗口冲突：新窗口[{start_at},{end_at}) 与现有 booking_id={ex_id} 重叠。"
                            )

                    row = MachineScheduleBooking(
                        machine_id=machine_id,
                        template_id=int(tpl.id),
                        state=tpl.state,
                        start_at=start_at,
                        end_at=end_at,
                        remark=tpl.remark,
                        created_by=created_by,
                    )
                    db.session.add(row)
                    db.session.flush()  # 让 id 可用于后续异常信息

                # 新增 booking 时同步插入 dispatch log（planned）
                existing_dispatch = MachineScheduleDispatchLog.query.filter_by(booking_id=row.id).first()
                if not existing_dispatch:
                    duration_seconds = int((end_at - start_at).total_seconds())
                    duration_hours = quantize_decimal(Decimal(duration_seconds) / Decimal(3600))
                    db.session.add(
                        MachineScheduleDispatchLog(
                            machine_id=machine_id,
                            booking_id=row.id,
                            dispatch_start_at=start_at,
                            dispatch_end_at=end_at,
                            planned_runtime_hours=duration_hours,
                            state="scheduled",
                            remark=tpl.remark,
                        )
                    )

                    # 更新用于后续循环的缓存
                    existing_key_set.add(key)
                    existing_intervals.append((start_at, end_at, int(row.id)))

                cur = cur + timedelta(days=1)

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def is_machine_available(*, machine_id: int, start_at: datetime, end_at: datetime) -> bool:
    """
    判断机台在 [start_at, end_at) 是否可用。

    策略：
    - 若机台非 `enabled`：不可用。
    - 若存在运行中 `machine_runtime_log` 与区间重叠：不可用。
    - 若区间内没有任何排班 booking：回退到机台状态（enabled）视为可用。
    - 若区间内存在 booking：
      - 任意不可用窗口（state != available）与区间重叠则不可用
      - 要求 available 窗口对区间覆盖无 gap，否则不可用
    """
    if machine_id <= 0:
        return False
    if start_at >= end_at:
        return False

    machine = Machine.query.get(machine_id)
    if not machine or machine.status != "enabled":
        return False

    start_at = _dt_minute_floor(start_at)
    end_at = _dt_minute_floor(end_at)

    # 运行中占用（ended_at 为空视为一直占用）
    runtime_running_exists = (
        MachineRuntimeLog.query.filter(
            MachineRuntimeLog.machine_id == machine_id,
            MachineRuntimeLog.runtime_status == "running",
            MachineRuntimeLog.started_at < end_at,
            or_(
                MachineRuntimeLog.ended_at.is_(None),
                MachineRuntimeLog.ended_at > start_at,
            ),
        )
        .limit(1)
        .first()
    )
    if runtime_running_exists:
        return False

    booking_rows: List[MachineScheduleBooking] = (
        MachineScheduleBooking.query.filter(
            MachineScheduleBooking.machine_id == machine_id,
            MachineScheduleBooking.start_at < end_at,
            MachineScheduleBooking.end_at > start_at,
        )
        .order_by(MachineScheduleBooking.start_at.asc(), MachineScheduleBooking.id.asc())
        .all()
    )

    # 无排班定义：回退到机台 enabled 即可用（已排除运行中占用）
    if not booking_rows:
        return True

    # 若存在不可用窗口重叠：不可用
    for b in booking_rows:
        if (b.state or "").strip() != _MACHINE_SCHEDULE_STATE_AVAILABLE:
            return False

    # 合并 available 区间，要求覆盖无 gap
    cursor = start_at
    for b in booking_rows:
        if b.state != _MACHINE_SCHEDULE_STATE_AVAILABLE:
            continue
        bs = max(b.start_at, start_at)
        be = min(b.end_at, end_at)
        if be <= cursor:
            continue
        if bs > cursor:
            return False
        cursor = max(cursor, be)
        if cursor >= end_at:
            return True
    return cursor >= end_at

