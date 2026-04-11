from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app import db
from app.utils.decimal_scale import quantize_decimal
from app.models import (
    HrEmployeeScheduleBooking,
    MachineScheduleBooking,
    MachineScheduleDispatchLog,
    ProductionScheduleCommitRow,
    ProductionWorkOrder,
    ProductionWorkOrderOperation,
    ProductionWorkOrderOperationPlan,
)
from app.services.hr_employee_schedule_svc import is_employee_available
from app.services.machine_schedule_svc import is_machine_available
from app.services.production_schedule_svc import list_bom_work_order_gate_errors


def _dt_floor(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(second=0, microsecond=0)


def _intervals_overlap(
    a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime
) -> bool:
    return a_start < b_end and b_start < a_end


def _dispatch_window(log: MachineScheduleDispatchLog, booking: MachineScheduleBooking) -> Tuple[datetime, datetime]:
    s = log.dispatch_start_at or booking.start_at
    e = log.dispatch_end_at or booking.end_at
    return _dt_floor(s) or booking.start_at, _dt_floor(e) or booking.end_at


def load_plan_pairs(
    *, preplan_id: int
) -> List[Tuple[ProductionWorkOrderOperationPlan, ProductionWorkOrderOperation]]:
    rows = (
        db.session.query(ProductionWorkOrderOperationPlan, ProductionWorkOrderOperation)
        .join(
            ProductionWorkOrderOperation,
            ProductionWorkOrderOperation.id == ProductionWorkOrderOperationPlan.operation_id,
        )
        .filter(ProductionWorkOrderOperationPlan.preplan_id == preplan_id)
        .order_by(
            ProductionWorkOrderOperationPlan.es.asc(),
            ProductionWorkOrderOperationPlan.work_order_id.asc(),
            ProductionWorkOrderOperation.step_no.asc(),
        )
        .all()
    )
    return list(rows)


def _machine_dispatch_conflicts(
    *,
    machine_id: int,
    es: datetime,
    ef: datetime,
    ignore_dispatch_log_id: int = 0,
    ignore_booking_id: int = 0,
) -> List[str]:
    errs: List[str] = []
    if machine_id <= 0:
        return errs
    es, ef = _dt_floor(es), _dt_floor(ef)
    logs = (
        db.session.query(MachineScheduleDispatchLog, MachineScheduleBooking)
        .join(
            MachineScheduleBooking,
            MachineScheduleBooking.id == MachineScheduleDispatchLog.booking_id,
        )
        .filter(
            MachineScheduleDispatchLog.machine_id == machine_id,
            MachineScheduleDispatchLog.state.in_(("scheduled", "reported")),
        )
        .all()
    )
    for log, bk in logs:
        if ignore_dispatch_log_id and int(log.id) == int(ignore_dispatch_log_id):
            continue
        if ignore_booking_id and int(bk.id) == int(ignore_booking_id):
            continue
        ds, de = _dispatch_window(log, bk)
        if _intervals_overlap(es, ef, ds, de):
            errs.append(
                f"机台#{machine_id} 与已有派工/报工重叠：{ds.strftime('%m-%d %H:%M')}–{de.strftime('%m-%d %H:%M')}（dispatch_log_id={log.id}）"
            )
    return errs


def _employee_booking_conflicts(
    *,
    employee_id: int,
    es: datetime,
    ef: datetime,
    ignore_booking_id: int = 0,
) -> List[str]:
    errs: List[str] = []
    if employee_id <= 0:
        return errs
    es, ef = _dt_floor(es), _dt_floor(ef)
    rows = (
        HrEmployeeScheduleBooking.query.filter(
            HrEmployeeScheduleBooking.employee_id == employee_id,
            HrEmployeeScheduleBooking.start_at < ef,
            HrEmployeeScheduleBooking.end_at > es,
            HrEmployeeScheduleBooking.work_order_id.isnot(None),
        )
        .all()
    )
    for b in rows:
        if ignore_booking_id and int(b.id) == int(ignore_booking_id):
            continue
        if _intervals_overlap(es, ef, b.start_at, b.end_at):
            errs.append(
                f"人员#{employee_id} 已有工单占用时段：{b.start_at.strftime('%m-%d %H:%M')}–{b.end_at.strftime('%m-%d %H:%M')}（booking_id={b.id}）"
            )
    return errs


def _same_preplan_resource_overlap(rows: List[Dict[str, Any]]) -> List[str]:
    """
    rows: dict with keys machine_id, employee_id, es, ef, step_no, work_order_id
    """
    errs: List[str] = []
    by_m: Dict[int, List[Dict[str, Any]]] = {}
    by_e: Dict[int, List[Dict[str, Any]]] = {}
    for r in rows:
        mid = int(r.get("machine_id") or 0)
        eid = int(r.get("employee_id") or 0)
        if mid > 0:
            by_m.setdefault(mid, []).append(r)
        if eid > 0:
            by_e.setdefault(eid, []).append(r)

    def _check_group(items: List[Dict[str, Any]], label: str) -> None:
        items = [x for x in items if x.get("es") and x.get("ef")]
        items.sort(key=lambda x: (x["es"], x["ef"], x.get("operation_id", 0)))
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                if _intervals_overlap(a["es"], a["ef"], b["es"], b["ef"]):
                    errs.append(
                        f"{label} 在本预计划内时段重叠：WO#{a.get('work_order_id')} 工序{a.get('step_no')} 与 WO#{b.get('work_order_id')} 工序{b.get('step_no')}"
                    )

    for mid, lst in by_m.items():
        _check_group(lst, f"机台({mid})")
    for eid, lst in by_e.items():
        _check_group(lst, f"人员({eid})")
    return errs


def _rows_from_db(preplan_id: int) -> Tuple[List[Dict[str, Any]], List[str]]:
    errs: List[str] = []
    out: List[Dict[str, Any]] = []
    pairs = load_plan_pairs(preplan_id=preplan_id)
    for plan, op in pairs:
        es, ef = plan.es, plan.ef
        if not es or not ef:
            errs.append(f"工序 {op.step_no}（WO#{op.work_order_id}）缺少 ES/EF，请先测算。")
            continue
        rk = (op.resource_kind or "").strip()
        mid = int(op.budget_machine_id or 0) if rk == "machine_type" else 0
        eid = int(op.budget_operator_employee_id or 0)
        if rk == "machine_type" and mid <= 0:
            errs.append(f"工序 {op.step_no}（WO#{op.work_order_id}）为机台资源，请指定机台。")
        if rk in ("hr_department", "hr_work_type") and eid <= 0:
            errs.append(f"工序 {op.step_no}（WO#{op.work_order_id}）为人工资源，请指定人员。")
        if rk == "machine_type" and eid <= 0:
            pass
        out.append(
            {
                "operation_id": int(op.id),
                "plan_id": int(plan.id),
                "work_order_id": int(op.work_order_id),
                "step_no": op.step_no,
                "resource_kind": rk,
                "machine_id": mid,
                "employee_id": eid,
                "es": _dt_floor(es),
                "ef": _dt_floor(ef),
                "ignore_dispatch_log_id": 0,
                "ignore_machine_booking_id": int(plan.committed_machine_booking_id or 0),
                "ignore_employee_booking_id": int(plan.committed_employee_booking_id or 0),
            }
        )
    # attach ignore dispatch from commit row
    commits = ProductionScheduleCommitRow.query.filter(
        ProductionScheduleCommitRow.preplan_id == preplan_id
    ).all()
    op_to_log = {int(c.operation_id): int(c.machine_dispatch_log_id or 0) for c in commits}
    for r in out:
        oid = int(r["operation_id"])
        if oid in op_to_log and op_to_log[oid] > 0:
            r["ignore_dispatch_log_id"] = op_to_log[oid]
    return out, errs


def validate_preplan_schedule(
    preplan_id: int,
    *,
    row_dicts: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    """
    校验当前或拟提交的排程。row_dicts 若传入则替代 DB 中的 es/ef/预算（用于保存前验算）。
    """
    errs: List[str] = []
    if row_dicts is None:
        rows, e2 = _rows_from_db(preplan_id)
        errs.extend(e2)
    else:
        rows = row_dicts

    for r in rows:
        es, ef = r.get("es"), r.get("ef")
        if not es or not ef or es >= ef:
            errs.append(f"工序 {r.get('step_no', '?')}（WO#{r.get('work_order_id', '?')}）时间无效（要求 ES<EF）。")
            continue
        es, ef = _dt_floor(es), _dt_floor(ef)
        rk = (r.get("resource_kind") or "").strip()
        mid = int(r.get("machine_id") or 0)
        eid = int(r.get("employee_id") or 0)
        if rk == "machine_type" and mid > 0:
            if not is_machine_available(machine_id=mid, start_at=es, end_at=ef):
                errs.append(
                    f"机台资源：WO#{r.get('work_order_id')} 工序{r.get('step_no')} 时段不在可用排班窗内或机台不可用。"
                )
            errs.extend(
                _machine_dispatch_conflicts(
                    machine_id=mid,
                    es=es,
                    ef=ef,
                    ignore_dispatch_log_id=int(r.get("ignore_dispatch_log_id") or 0),
                    ignore_booking_id=int(r.get("ignore_machine_booking_id") or 0),
                )
            )
        if rk in ("hr_department", "hr_work_type") and eid > 0:
            if not is_employee_available(employee_id=eid, start_at=es, end_at=ef):
                errs.append(
                    f"人员资源：WO#{r.get('work_order_id')} 工序{r.get('step_no')} 时段不在可用排班窗内或员工不可用。"
                )
            errs.extend(
                _employee_booking_conflicts(
                    employee_id=eid,
                    es=es,
                    ef=ef,
                    ignore_booking_id=int(r.get("ignore_employee_booking_id") or 0),
                )
            )
        if rk == "machine_type" and mid > 0 and eid > 0:
            if not is_employee_available(employee_id=eid, start_at=es, end_at=ef):
                errs.append(
                    f"操作员：WO#{r.get('work_order_id')} 工序{r.get('step_no')} 所选操作员时段不可用。"
                )
            errs.extend(
                _employee_booking_conflicts(
                    employee_id=eid,
                    es=es,
                    ef=ef,
                    ignore_booking_id=int(r.get("ignore_employee_booking_id") or 0),
                )
            )

    errs.extend(_same_preplan_resource_overlap(rows))
    errs.extend(list_bom_work_order_gate_errors(preplan_id=preplan_id, rows=rows))
    return errs


def _find_containing_machine_booking(
    machine_id: int, es: datetime, ef: datetime
) -> Optional[MachineScheduleBooking]:
    es, ef = _dt_floor(es), _dt_floor(ef)
    rows = (
        MachineScheduleBooking.query.filter(
            MachineScheduleBooking.machine_id == machine_id,
            MachineScheduleBooking.state == "available",
            MachineScheduleBooking.start_at <= es,
            MachineScheduleBooking.end_at >= ef,
        )
        .order_by(MachineScheduleBooking.start_at.asc())
        .all()
    )
    for r in rows:
        if r.start_at <= es and r.end_at >= ef:
            return r
    return None


def _find_containing_employee_booking(
    employee_id: int, es: datetime, ef: datetime
) -> Optional[HrEmployeeScheduleBooking]:
    es, ef = _dt_floor(es), _dt_floor(ef)
    rows = (
        HrEmployeeScheduleBooking.query.filter(
            HrEmployeeScheduleBooking.employee_id == employee_id,
            HrEmployeeScheduleBooking.state == "available",
            HrEmployeeScheduleBooking.start_at <= es,
            HrEmployeeScheduleBooking.end_at >= ef,
        )
        .order_by(HrEmployeeScheduleBooking.start_at.asc())
        .all()
    )
    for r in rows:
        if r.start_at <= es and r.end_at >= ef:
            return r
    return None


def _runtime_hours_between(start_at: datetime, end_at: datetime) -> Decimal:
    sec = int((end_at - start_at).total_seconds())
    return quantize_decimal(Decimal(sec) / Decimal(3600))


def _upsert_machine_dispatch(
    *,
    machine_id: int,
    booking_id: int,
    start_at: datetime,
    end_at: datetime,
    work_order_id: int,
    user_id: int,
    remark: Optional[str] = None,
) -> MachineScheduleDispatchLog:
    log = MachineScheduleDispatchLog.query.filter_by(booking_id=booking_id).first()
    hrs = _runtime_hours_between(start_at, end_at)
    if not log:
        log = MachineScheduleDispatchLog(
            machine_id=machine_id,
            booking_id=booking_id,
            dispatch_start_at=start_at,
            dispatch_end_at=end_at,
            planned_runtime_hours=hrs,
            state="scheduled",
            work_order_id=work_order_id,
            remark=remark,
        )
        db.session.add(log)
        db.session.flush()
        return log
    log.dispatch_start_at = start_at
    log.dispatch_end_at = end_at
    log.planned_runtime_hours = hrs
    log.state = "scheduled"
    log.work_order_id = work_order_id
    if remark is not None:
        log.remark = remark
    db.session.add(log)
    db.session.flush()
    return log


def _revoke_commit_row(row: ProductionScheduleCommitRow) -> None:
    if row.machine_dispatch_log_id:
        log = db.session.get(MachineScheduleDispatchLog, int(row.machine_dispatch_log_id))
        if log and (log.state or "").strip() != "reported":
            db.session.delete(log)

    for bid in (int(row.delete_middle_booking_id or 0), int(row.delete_tail_booking_id or 0)):
        if bid > 0:
            b = db.session.get(MachineScheduleBooking, bid)
            if b:
                db.session.delete(b)

    if int(row.restore_parent_booking_id or 0) > 0 and row.restore_parent_end_at:
        parent = db.session.get(MachineScheduleBooking, int(row.restore_parent_booking_id))
        if parent:
            parent.end_at = row.restore_parent_end_at
            db.session.add(parent)
            plog = MachineScheduleDispatchLog.query.filter_by(booking_id=parent.id).first()
            if plog:
                plog.dispatch_start_at = parent.start_at
                plog.dispatch_end_at = parent.end_at
                plog.planned_runtime_hours = _runtime_hours_between(parent.start_at, parent.end_at)
                db.session.add(plog)

    if (row.emp_booking_mode or "") == "mask_parent" and int(row.employee_booking_id or 0) > 0:
        eb = db.session.get(HrEmployeeScheduleBooking, int(row.employee_booking_id))
        if eb:
            eb.state = "available"
            eb.work_order_id = None
            eb.remark = None
            db.session.add(eb)
    else:
        if int(row.emp_delete_middle_booking_id or 0) > 0:
            mb = db.session.get(HrEmployeeScheduleBooking, int(row.emp_delete_middle_booking_id))
            if mb:
                db.session.delete(mb)
        if int(row.emp_delete_tail_booking_id or 0) > 0:
            tb = db.session.get(HrEmployeeScheduleBooking, int(row.emp_delete_tail_booking_id))
            if tb:
                db.session.delete(tb)
        if int(row.emp_restore_parent_booking_id or 0) > 0 and row.emp_restore_parent_end_at:
            ep = db.session.get(HrEmployeeScheduleBooking, int(row.emp_restore_parent_booking_id))
            if ep:
                ep.end_at = row.emp_restore_parent_end_at
                db.session.add(ep)

    db.session.delete(row)


def revoke_preplan_commits_for_measure(*, preplan_id: int) -> None:
    rows = ProductionScheduleCommitRow.query.filter_by(preplan_id=preplan_id).all()
    for r in rows:
        _revoke_commit_row(r)

    plans = ProductionWorkOrderOperationPlan.query.filter_by(preplan_id=preplan_id).all()
    for p in plans:
        p.confirmed_at = None
        p.confirmed_by = None
        p.committed_machine_booking_id = 0
        p.committed_employee_booking_id = 0
        db.session.add(p)


def _commit_machine(
    *,
    machine_id: int,
    es: datetime,
    ef: datetime,
    work_order_id: int,
    user_id: int,
    preplan_id: int,
    operation_id: int,
) -> ProductionScheduleCommitRow:
    es, ef = _dt_floor(es), _dt_floor(ef)
    parent = _find_containing_machine_booking(machine_id, es, ef)
    if not parent:
        raise ValueError(
            "机台排程确认失败：未找到完全覆盖该时段的单一可用 booking，请先调整排班模板或人工时间。"
        )

    os, oe = parent.start_at, parent.end_at
    tpl_id = int(parent.template_id)
    st = (parent.state or "available").strip() or "available"
    rm = parent.remark
    created_by = int(parent.created_by or user_id)

    commit = ProductionScheduleCommitRow(
        preplan_id=preplan_id,
        operation_id=operation_id,
        machine_dispatch_log_id=0,
        dispatch_booking_id=0,
        restore_parent_booking_id=0,
        restore_parent_end_at=None,
        delete_middle_booking_id=0,
        delete_tail_booking_id=0,
        employee_booking_id=0,
        emp_restore_parent_booking_id=0,
        emp_restore_parent_end_at=None,
        emp_delete_middle_booking_id=0,
        emp_delete_tail_booking_id=0,
        emp_booking_mode="split",
    )

    if os == es and oe == ef:
        log = _upsert_machine_dispatch(
            machine_id=machine_id,
            booking_id=parent.id,
            start_at=es,
            end_at=ef,
            work_order_id=work_order_id,
            user_id=user_id,
            remark=f"preplan_commit:{preplan_id}:{operation_id}",
        )
        commit.machine_dispatch_log_id = int(log.id)
        commit.dispatch_booking_id = int(parent.id)
        return commit

    if es == os and ef < oe:
        orig_end = oe
        parent.end_at = ef
        db.session.add(parent)
        tail = MachineScheduleBooking(
            machine_id=machine_id,
            template_id=tpl_id,
            state=st,
            start_at=ef,
            end_at=orig_end,
            remark=rm,
            created_by=created_by,
        )
        db.session.add(tail)
        db.session.flush()
        _upsert_machine_dispatch(
            machine_id=machine_id,
            booking_id=tail.id,
            start_at=ef,
            end_at=orig_end,
            work_order_id=0,
            user_id=user_id,
            remark=rm,
        )
        log = _upsert_machine_dispatch(
            machine_id=machine_id,
            booking_id=parent.id,
            start_at=os,
            end_at=ef,
            work_order_id=work_order_id,
            user_id=user_id,
            remark=f"preplan_commit:{preplan_id}:{operation_id}",
        )
        commit.restore_parent_booking_id = int(parent.id)
        commit.restore_parent_end_at = orig_end
        commit.delete_tail_booking_id = int(tail.id)
        commit.dispatch_booking_id = int(parent.id)
        commit.machine_dispatch_log_id = int(log.id)
        return commit

    if es > os and ef == oe:
        orig_end = oe
        parent.end_at = es
        db.session.add(parent)
        db.session.flush()
        _upsert_machine_dispatch(
            machine_id=machine_id,
            booking_id=parent.id,
            start_at=os,
            end_at=es,
            work_order_id=0,
            user_id=user_id,
            remark=rm,
        )
        middle = MachineScheduleBooking(
            machine_id=machine_id,
            template_id=tpl_id,
            state=st,
            start_at=es,
            end_at=orig_end,
            remark=rm,
            created_by=created_by,
        )
        db.session.add(middle)
        db.session.flush()
        log = _upsert_machine_dispatch(
            machine_id=machine_id,
            booking_id=middle.id,
            start_at=es,
            end_at=orig_end,
            work_order_id=work_order_id,
            user_id=user_id,
            remark=f"preplan_commit:{preplan_id}:{operation_id}",
        )
        commit.restore_parent_booking_id = int(parent.id)
        commit.restore_parent_end_at = orig_end
        commit.delete_middle_booking_id = int(middle.id)
        commit.dispatch_booking_id = int(middle.id)
        commit.machine_dispatch_log_id = int(log.id)
        return commit

    if es > os and ef < oe:
        orig_end = oe
        parent.end_at = es
        db.session.add(parent)
        db.session.flush()
        _upsert_machine_dispatch(
            machine_id=machine_id,
            booking_id=parent.id,
            start_at=os,
            end_at=es,
            work_order_id=0,
            user_id=user_id,
            remark=rm,
        )
        middle = MachineScheduleBooking(
            machine_id=machine_id,
            template_id=tpl_id,
            state=st,
            start_at=es,
            end_at=ef,
            remark=rm,
            created_by=created_by,
        )
        tail = MachineScheduleBooking(
            machine_id=machine_id,
            template_id=tpl_id,
            state=st,
            start_at=ef,
            end_at=orig_end,
            remark=rm,
            created_by=created_by,
        )
        db.session.add_all([middle, tail])
        db.session.flush()
        _upsert_machine_dispatch(
            machine_id=machine_id,
            booking_id=tail.id,
            start_at=ef,
            end_at=orig_end,
            work_order_id=0,
            user_id=user_id,
            remark=rm,
        )
        log = _upsert_machine_dispatch(
            machine_id=machine_id,
            booking_id=middle.id,
            start_at=es,
            end_at=ef,
            work_order_id=work_order_id,
            user_id=user_id,
            remark=f"preplan_commit:{preplan_id}:{operation_id}",
        )
        commit.restore_parent_booking_id = int(parent.id)
        commit.restore_parent_end_at = orig_end
        commit.delete_middle_booking_id = int(middle.id)
        commit.delete_tail_booking_id = int(tail.id)
        commit.dispatch_booking_id = int(middle.id)
        commit.machine_dispatch_log_id = int(log.id)
        return commit

    raise ValueError("机台 booking 切分：时段未落在单一可用窗内。")


def _employee_commit_meta(
    *,
    employee_id: int,
    es: datetime,
    ef: datetime,
    work_order_id: int,
    user_id: int,
    preplan_id: int,
    operation_id: int,
    op: ProductionWorkOrderOperation,
) -> Tuple[int, str, int, int, int, int]:
    """返回 (employee_booking_id, emp_booking_mode, emp_parent, emp_end, emp_mid, emp_tail) 用于写入 commit 行。"""
    es, ef = _dt_floor(es), _dt_floor(ef)
    parent = _find_containing_employee_booking(employee_id, es, ef)
    if not parent:
        raise ValueError("人员排程确认失败：未找到完全覆盖该时段的单一可用 booking。")
    os, oe = parent.start_at, parent.end_at
    tpl_id = int(parent.template_id)
    created_by = int(parent.created_by or user_id)
    remark = f"preplan_commit:{preplan_id}:{operation_id}"

    if os == es and oe == ef:
        parent.state = "unavailable"
        parent.work_order_id = work_order_id
        parent.remark = remark
        db.session.add(parent)
        db.session.flush()
        return int(parent.id), "mask_parent", 0, 0, 0, 0

    orig_end = oe
    parent.end_at = es
    db.session.add(parent)
    middle = HrEmployeeScheduleBooking(
        employee_id=employee_id,
        template_id=tpl_id,
        state="unavailable",
        start_at=es,
        end_at=ef,
        remark=remark,
        created_by=created_by,
        work_order_id=work_order_id,
        hr_department_id=int(op.hr_department_id or 0) or None,
        work_type_id=int(op.effective_work_type_id or 0) or None,
    )
    tail = HrEmployeeScheduleBooking(
        employee_id=employee_id,
        template_id=tpl_id,
        state="available",
        start_at=ef,
        end_at=orig_end,
        remark=parent.remark,
        created_by=created_by,
    )
    db.session.add_all([middle, tail])
    db.session.flush()
    return (
        int(middle.id),
        "split",
        int(parent.id),
        orig_end,
        int(middle.id),
        int(tail.id),
    )


def apply_manual_plan_from_form(
    *,
    preplan_id: int,
    form_data: Dict[str, Any],
    user_id: int,
) -> List[str]:
    """
    form_data: request.form 或类 dict，键形如 es_{op_id}, ef_{op_id}, budget_machine_{op_id}, budget_emp_{op_id}
    """
    _ = user_id
    pairs = load_plan_pairs(preplan_id=preplan_id)
    tentative: List[Dict[str, Any]] = []
    for plan, op in pairs:
        oid = int(op.id)
        es_raw = (form_data.get(f"es_{oid}") or "").strip()
        ef_raw = (form_data.get(f"ef_{oid}") or "").strip()
        try:
            es = datetime.fromisoformat(es_raw) if es_raw else None
            ef = datetime.fromisoformat(ef_raw) if ef_raw else None
        except ValueError:
            return [f"工序 {op.step_no}（WO#{op.work_order_id}）时间格式错误。"]
        if not es or not ef:
            return [f"工序 {op.step_no}（WO#{op.work_order_id}）须填写 ES/EF。"]
        rk = (op.resource_kind or "").strip()
        mid = int(op.budget_machine_id or 0)
        eid = int(op.budget_operator_employee_id or 0)
        if rk == "machine_type":
            pair = (form_data.get(f"budget_pair_{oid}") or "").strip()
            if pair and ":" in pair:
                a, b = pair.split(":", 1)
                try:
                    mid = int(a)
                    eid = int(b)
                except ValueError:
                    mid, eid = 0, 0
        elif rk in ("hr_department", "hr_work_type"):
            eid = int(form_data.get(f"budget_emp_{oid}") or 0)

        c_row = ProductionScheduleCommitRow.query.filter_by(operation_id=oid).first()
        tentative.append(
            {
                "operation_id": oid,
                "plan_id": int(plan.id),
                "work_order_id": int(op.work_order_id),
                "step_no": op.step_no,
                "resource_kind": rk,
                "machine_id": mid if rk == "machine_type" else 0,
                "employee_id": eid,
                "es": _dt_floor(es),
                "ef": _dt_floor(ef),
                "ignore_dispatch_log_id": int(c_row.machine_dispatch_log_id or 0) if c_row else 0,
                "ignore_machine_booking_id": int(plan.committed_machine_booking_id or 0),
                "ignore_employee_booking_id": int(plan.committed_employee_booking_id or 0),
            }
        )

    errs = validate_preplan_schedule(preplan_id, row_dicts=tentative)
    if errs:
        return errs

    for plan, op in pairs:
        oid = int(op.id)
        tr = next(x for x in tentative if x["operation_id"] == oid)
        es, ef = tr["es"], tr["ef"]
        plan.es = es
        plan.ef = ef
        if (op.resource_kind or "").strip() == "machine_type":
            op.budget_machine_id = int(tr["machine_id"])
            op.budget_operator_employee_id = int(tr["employee_id"])
        elif (op.resource_kind or "").strip() in ("hr_department", "hr_work_type"):
            op.budget_operator_employee_id = int(tr["employee_id"])
            op.budget_machine_id = 0
        db.session.add_all([plan, op])

    db.session.commit()
    return []


def confirm_preplan_schedule(*, preplan_id: int, user_id: int) -> List[str]:
    errs = validate_preplan_schedule(preplan_id)
    if errs:
        return errs

    pairs = load_plan_pairs(preplan_id=preplan_id)
    now = datetime.now()

    for plan, op in pairs:
        oid = int(op.id)
        es, ef = _dt_floor(plan.es), _dt_floor(plan.ef)
        if not es or not ef:
            return ["存在缺少时间的工序行，无法确认。"]
        rk = (op.resource_kind or "").strip()

        existing = ProductionScheduleCommitRow.query.filter_by(operation_id=oid).first()
        if existing:
            _revoke_commit_row(existing)
            db.session.flush()
            plan.committed_machine_booking_id = 0
            plan.committed_employee_booking_id = 0
            plan.confirmed_at = None
            plan.confirmed_by = None

        m_commit: Optional[ProductionScheduleCommitRow] = None
        if rk == "machine_type" and int(op.budget_machine_id or 0) > 0:
            m_commit = _commit_machine(
                machine_id=int(op.budget_machine_id),
                es=es,
                ef=ef,
                work_order_id=int(op.work_order_id),
                user_id=user_id,
                preplan_id=preplan_id,
                operation_id=oid,
            )
            plan.committed_machine_booking_id = int(m_commit.dispatch_booking_id)

        emp_bid = 0
        emp_mode = "split"
        emp_p, emp_pe, emp_m, emp_t = 0, None, 0, 0
        eid = int(op.budget_operator_employee_id or 0)
        if eid > 0 and (rk == "machine_type" or rk in ("hr_department", "hr_work_type")):
            emp_bid, emp_mode, emp_p, emp_pe, emp_m, emp_t = _employee_commit_meta(
                employee_id=eid,
                es=es,
                ef=ef,
                work_order_id=int(op.work_order_id),
                user_id=user_id,
                preplan_id=preplan_id,
                operation_id=oid,
                op=op,
            )
            plan.committed_employee_booking_id = emp_bid

        if m_commit is None:
            m_commit = ProductionScheduleCommitRow(
                preplan_id=preplan_id,
                operation_id=oid,
                machine_dispatch_log_id=0,
                dispatch_booking_id=0,
                restore_parent_booking_id=0,
                restore_parent_end_at=None,
                delete_middle_booking_id=0,
                delete_tail_booking_id=0,
                employee_booking_id=0,
                emp_restore_parent_booking_id=0,
                emp_restore_parent_end_at=None,
                emp_delete_middle_booking_id=0,
                emp_delete_tail_booking_id=0,
                emp_booking_mode="split",
            )
        m_commit.preplan_id = preplan_id
        m_commit.operation_id = oid
        m_commit.employee_booking_id = emp_bid
        m_commit.emp_booking_mode = emp_mode
        m_commit.emp_restore_parent_booking_id = emp_p
        m_commit.emp_restore_parent_end_at = emp_pe
        m_commit.emp_delete_middle_booking_id = emp_m
        m_commit.emp_delete_tail_booking_id = emp_t
        db.session.add(m_commit)

        plan.confirmed_at = now
        plan.confirmed_by = user_id
        db.session.add(plan)

    db.session.commit()
    return []


def measure_blocked_by_reported_dispatch(*, preplan_id: int) -> bool:
    wo_ids = [
        int(r[0])
        for r in db.session.query(ProductionWorkOrder.id).filter_by(preplan_id=preplan_id).all()
    ]
    if not wo_ids:
        return False
    q = MachineScheduleDispatchLog.query.filter(
        MachineScheduleDispatchLog.work_order_id.in_(wo_ids),
        MachineScheduleDispatchLog.state == "reported",
    ).first()
    return q is not None
