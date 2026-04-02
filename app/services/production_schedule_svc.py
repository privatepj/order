from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

from app import db
from app.models import (
    HrEmployee,
    HrEmployeeScheduleBooking,
    Machine,
    MachineScheduleBooking,
    ProductionProcessEdge,
    ProductionProcessNode,
    ProductionProductRouting,
    ProductionWorkOrder,
    ProductionWorkOrderOperation,
    ProductionWorkOrderOperationPlan,
)


def _d(val) -> Decimal:
    if val is None:
        return Decimal(0)
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def _dt_floor_minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


def _merge_sorted_intervals(
    intervals: List[Tuple[datetime, datetime]]
) -> List[Tuple[datetime, datetime]]:
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda x: (x[0], x[1]))
    out: List[Tuple[datetime, datetime]] = []
    cs, ce = intervals[0]
    for s, e in intervals[1:]:
        if s <= ce:
            ce = max(ce, e)
        else:
            out.append((cs, ce))
            cs, ce = s, e
    out.append((cs, ce))
    return out


def _load_machine_available_intervals(
    *,
    machine_id: int,
    horizon_start: datetime,
    horizon_end: datetime,
) -> List[Tuple[datetime, datetime]]:
    if machine_id <= 0:
        return []
    rows = (
        MachineScheduleBooking.query.filter(
            MachineScheduleBooking.machine_id == machine_id,
            MachineScheduleBooking.state == "available",
            MachineScheduleBooking.start_at < horizon_end,
            MachineScheduleBooking.end_at > horizon_start,
        )
        .order_by(MachineScheduleBooking.start_at.asc(), MachineScheduleBooking.id.asc())
        .all()
    )
    raw = [(r.start_at, r.end_at) for r in rows]
    return _merge_sorted_intervals(raw)


def _load_employee_available_intervals(
    *,
    employee_id: int,
    horizon_start: datetime,
    horizon_end: datetime,
) -> List[Tuple[datetime, datetime]]:
    if employee_id <= 0:
        return []
    rows = (
        HrEmployeeScheduleBooking.query.filter(
            HrEmployeeScheduleBooking.employee_id == employee_id,
            HrEmployeeScheduleBooking.state == "available",
            HrEmployeeScheduleBooking.start_at < horizon_end,
            HrEmployeeScheduleBooking.end_at > horizon_start,
        )
        .order_by(HrEmployeeScheduleBooking.start_at.asc(), HrEmployeeScheduleBooking.id.asc())
        .all()
    )
    raw = [(r.start_at, r.end_at) for r in rows]
    return _merge_sorted_intervals(raw)


def _consume_minutes_on_calendar(
    t_start: datetime,
    minutes: float,
    intervals: List[Tuple[datetime, datetime]],
) -> datetime:
    """
    在合并后的 available 区间内消耗 minutes；无区间时视为连续墙钟。
    若区间内分钟耗尽后仍有剩余，在最后一个可用片段之后按连续墙钟补足（无排班数据时的回退）。
    """
    if minutes <= 0:
        return t_start
    remaining = float(minutes)
    t = _dt_floor_minute(t_start)
    if not intervals:
        return t + timedelta(minutes=remaining)

    i = 0
    n = len(intervals)
    while remaining > 1e-9:
        while i < n and intervals[i][1] <= t:
            i += 1
        if i >= n:
            return t + timedelta(minutes=remaining)
        seg_start, seg_end = intervals[i]
        cur = max(t, seg_start)
        if cur >= seg_end:
            i += 1
            continue
        avail_min = (seg_end - cur).total_seconds() / 60.0
        take = min(remaining, avail_min)
        remaining -= take
        t = cur + timedelta(minutes=take)
        if take >= avail_min - 1e-9:
            i += 1
    return t


def _resource_key(op: ProductionWorkOrderOperation) -> Optional[Tuple[str, int]]:
    rk = (op.resource_kind or "").strip()
    if rk == "machine_type":
        mid = int(op.budget_machine_id or 0)
        if mid > 0:
            return ("machine", mid)
    elif rk == "hr_department":
        eid = int(op.budget_operator_employee_id or 0)
        if eid > 0:
            return ("employee", eid)
    return None


def plan_operations_for_preplan(*, preplan_id: int) -> None:
    """
    排程 v3：
    - 工序依赖：模板 DAG，否则按 step_no 串行；
    - 前向计算 ES/EF，后向计算 LS/LF 与关键工序；
    - 资源：按 budget 机台/人员做 list scheduling；
    - 日历：有机台/人员 available 排班窗时，仅在窗内累计有效作业分钟（跨多日、跳过非工作 gap）。
    """
    db.session.query(ProductionWorkOrderOperationPlan).filter_by(preplan_id=preplan_id).delete(
        synchronize_session=False
    )
    db.session.flush()

    work_orders: List[ProductionWorkOrder] = (
        ProductionWorkOrder.query.filter_by(preplan_id=preplan_id)
        .order_by(ProductionWorkOrder.id.asc())
        .all()
    )
    if not work_orders:
        return

    min_d = min(wo.plan_date for wo in work_orders)
    max_d = max(wo.plan_date for wo in work_orders)
    horizon_start = datetime.combine(min_d, time.min)
    horizon_end = datetime.combine(max_d + timedelta(days=730), time.max)

    window_cache: Dict[Tuple[str, int], List[Tuple[datetime, datetime]]] = {}

    def get_windows(key: Optional[Tuple[str, int]]) -> List[Tuple[datetime, datetime]]:
        if not key:
            return []
        if key in window_cache:
            return window_cache[key]
        kind, rid = key
        if kind == "machine":
            merged = _load_machine_available_intervals(
                machine_id=rid, horizon_start=horizon_start, horizon_end=horizon_end
            )
        elif kind == "employee":
            merged = _load_employee_available_intervals(
                employee_id=rid, horizon_start=horizon_start, horizon_end=horizon_end
            )
        else:
            merged = []
        window_cache[key] = merged
        return merged

    # 同一预计划内多工单共享机台/人员尾时间（跨 WO 排队）
    shared_resource_tail: Dict[Tuple[str, int], datetime] = {}

    for wo in work_orders:
        base_start = datetime.combine(wo.plan_date, datetime.min.time())
        ops: List[ProductionWorkOrderOperation] = (
            ProductionWorkOrderOperation.query.filter_by(work_order_id=wo.id)
            .order_by(ProductionWorkOrderOperation.step_no.asc(), ProductionWorkOrderOperation.id.asc())
            .all()
        )
        _plan_one_work_order(
            wo=wo,
            ops=list(ops),
            base_start=base_start,
            get_windows=get_windows,
            shared_resource_tail=shared_resource_tail,
        )


def _plan_one_work_order(
    *,
    wo: ProductionWorkOrder,
    ops: List[ProductionWorkOrderOperation],
    base_start: datetime,
    get_windows,
    shared_resource_tail: Dict[Tuple[str, int], datetime],
) -> None:
    if not ops:
        return

    predecessors: Dict[int, Set[int]] = {int(op.id): set() for op in ops}
    step_to_op_id: Dict[int, int] = {int(op.step_no): int(op.id) for op in ops}
    ops_by_id: Dict[int, ProductionWorkOrderOperation] = {int(op.id): op for op in ops}
    sorted_ops = sorted(ops, key=lambda x: (x.step_no, x.id))
    for i in range(1, len(sorted_ops)):
        predecessors[int(sorted_ops[i].id)].add(int(sorted_ops[i - 1].id))

    template_id = _resolve_template_id_for_work_order(wo)
    if template_id:
        node_map = {
            int(n.id): int(n.step_no)
            for n in ProductionProcessNode.query.filter_by(
                template_id=template_id, node_type="operation", is_active=True
            ).all()
            if n.step_no is not None
        }
        edges = ProductionProcessEdge.query.filter_by(template_id=template_id).all()
        dag_predecessors: Dict[int, Set[int]] = {int(op.id): set() for op in ops}
        has_effective_edge = False
        for e in edges:
            from_step = node_map.get(int(e.from_node_id))
            to_step = node_map.get(int(e.to_node_id))
            if from_step is None or to_step is None:
                continue
            from_op_id = step_to_op_id.get(int(from_step))
            to_op_id = step_to_op_id.get(int(to_step))
            if not from_op_id or not to_op_id:
                continue
            dag_predecessors[to_op_id].add(from_op_id)
            has_effective_edge = True
        if has_effective_edge:
            predecessors = dag_predecessors

    indeg: Dict[int, int] = {op_id: len(preds) for op_id, preds in predecessors.items()}
    ready = [op_id for op_id, d in indeg.items() if d == 0]
    ready.sort(key=lambda oid: (ops_by_id[oid].step_no, oid))
    topo: List[int] = []

    succs: Dict[int, List[int]] = {int(op.id): [] for op in ops}
    for to_id, preds in predecessors.items():
        for p in preds:
            succs[p].append(to_id)

    while ready:
        oid = ready.pop(0)
        topo.append(oid)
        for nxt in succs.get(oid, []):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
        ready.sort(key=lambda x: (ops_by_id[x].step_no, x))

    if len(topo) != len(ops):
        topo = [int(op.id) for op in sorted_ops]
        predecessors = {int(op.id): set() for op in ops}
        for i in range(1, len(sorted_ops)):
            predecessors[int(sorted_ops[i].id)].add(int(sorted_ops[i - 1].id))
        succs = {int(op.id): [] for op in ops}
        for to_id, preds in predecessors.items():
            for p in preds:
                succs[p].append(to_id)

    # ---------- 前向 ES/EF（逻辑无限资源） ----------
    ef_map: Dict[int, datetime] = {}
    es_map: Dict[int, datetime] = {}
    for oid in topo:
        op = ops_by_id[oid]
        preds = predecessors.get(oid, set())
        es = max((ef_map[p] for p in preds), default=base_start)
        dur = float(_d(op.estimated_total_minutes))
        ef = es + timedelta(minutes=dur)
        es_map[oid] = es
        ef_map[oid] = ef

    project_end = max(ef_map.values())

    # ---------- 后向 LS/LF（关键路径） ----------
    ls_map: Dict[int, datetime] = {}
    lf_map: Dict[int, datetime] = {}
    for oid in reversed(topo):
        op = ops_by_id[oid]
        dur = float(_d(op.estimated_total_minutes))
        succ_list = succs.get(oid, [])
        if not succ_list:
            lf = project_end
        else:
            lf = min(ls_map[s] for s in succ_list)
        ls = lf - timedelta(minutes=dur)
        lf_map[oid] = lf
        ls_map[oid] = ls

    _eps_sec = 60.0

    # ---------- 资源队列 + 排班窗（shared_resource_tail 跨工单累积） ----------
    es_final: Dict[int, datetime] = {}
    ef_final: Dict[int, datetime] = {}

    for oid in topo:
        op = ops_by_id[oid]
        preds = predecessors.get(oid, set())
        if preds:
            es_from = max(es_final[p] for p in preds)
        else:
            es_from = base_start

        rkey = _resource_key(op)
        if rkey:
            tail = shared_resource_tail.get(rkey, es_from)
            es1 = max(es_from, tail)
        else:
            es1 = es_from

        dur = float(_d(op.estimated_total_minutes))
        wins = get_windows(rkey) if rkey else []
        if rkey and wins:
            ef1 = _consume_minutes_on_calendar(es1, dur, wins)
        else:
            ef1 = es1 + timedelta(minutes=dur)

        es_final[oid] = es1
        ef_final[oid] = ef1
        if rkey:
            shared_resource_tail[rkey] = ef1

    for oid in topo:
        op = ops_by_id[oid]
        slack = (ls_map[oid] - es_map[oid]).total_seconds()
        is_critical = abs(slack) <= _eps_sec
        db.session.add(
            ProductionWorkOrderOperationPlan(
                preplan_id=wo.preplan_id,
                work_order_id=wo.id,
                operation_id=op.id,
                process_node_id=None,
                plan_date=wo.plan_date,
                es=es_final[oid],
                ef=ef_final[oid],
                ls=ls_map[oid],
                lf=lf_map[oid],
                is_critical=is_critical,
                resource_kind=op.resource_kind,
                machine_type_id=op.machine_type_id,
                hr_department_id=op.hr_department_id,
                planned_minutes=_d(op.estimated_total_minutes),
                remark=None,
            )
        )


def _resolve_template_id_for_work_order(wo: ProductionWorkOrder) -> Optional[int]:
    if (wo.parent_kind or "") != "finished":
        return None
    product_id = int(wo.parent_product_id or 0)
    if product_id <= 0:
        return None
    routing = ProductionProductRouting.query.filter_by(product_id=product_id, is_active=True).first()
    if not routing:
        return None
    return int(routing.template_id or 0) or None


def compute_preplan_schedule_dashboard(*, preplan_id: int) -> Dict[str, object]:
    """
    预计划详情页：工序作业量合计、墙钟起止与跨度、各工单跨度；另返回排程作业量合计（Σ planned_minutes）。
    """
    sum_planned = (
        db.session.query(db.func.coalesce(db.func.sum(ProductionWorkOrderOperationPlan.planned_minutes), 0))
        .filter(ProductionWorkOrderOperationPlan.preplan_id == preplan_id)
        .scalar()
    ) or 0
    bounds = (
        db.session.query(
            db.func.min(ProductionWorkOrderOperationPlan.es),
            db.func.max(ProductionWorkOrderOperationPlan.ef),
        )
        .filter(ProductionWorkOrderOperationPlan.preplan_id == preplan_id)
        .first()
    )
    min_es = bounds[0] if bounds else None
    max_ef = bounds[1] if bounds else None

    wall_minutes: Optional[float] = None
    if min_es is not None and max_ef is not None:
        wall_minutes = (max_ef - min_es).total_seconds() / 60.0

    wo_rows = (
        db.session.query(
            ProductionWorkOrderOperationPlan.work_order_id,
            db.func.min(ProductionWorkOrderOperationPlan.es),
            db.func.max(ProductionWorkOrderOperationPlan.ef),
        )
        .filter(ProductionWorkOrderOperationPlan.preplan_id == preplan_id)
        .group_by(ProductionWorkOrderOperationPlan.work_order_id)
        .all()
    )
    wo_span: Dict[int, Dict[str, object]] = {}
    for wid, w_es, w_ef in wo_rows:
        span_m = (w_ef - w_es).total_seconds() / 60.0 if w_es and w_ef else None
        wo_span[int(wid)] = {
            "planned_es": w_es,
            "planned_ef": w_ef,
            "wall_minutes": span_m,
        }

    return {
        "sum_planned_minutes": sum_planned,
        "preplan_planned_es": min_es,
        "preplan_planned_ef": max_ef,
        "preplan_wall_minutes": wall_minutes,
        "wo_planned_span": wo_span,
    }


def list_schedule_plan_rows_for_preplan(*, preplan_id: int) -> List[Dict[str, Any]]:
    """
    测算/预计划详情：按时间顺序列出每条工序的排程结果（ES/EF、资源、关键路径），供排产对照。
    """
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
            ProductionWorkOrderOperation.id.asc(),
        )
        .all()
    )
    if not rows:
        return []

    machine_ids = {int(op.budget_machine_id or 0) for _, op in rows if int(op.budget_machine_id or 0) > 0}
    emp_ids = {int(op.budget_operator_employee_id or 0) for _, op in rows if int(op.budget_operator_employee_id or 0) > 0}
    machines = {m.id: m for m in Machine.query.filter(Machine.id.in_(machine_ids)).all()} if machine_ids else {}
    emps = {e.id: e for e in HrEmployee.query.filter(HrEmployee.id.in_(emp_ids)).all()} if emp_ids else {}

    out: List[Dict[str, Any]] = []
    for plan, op in rows:
        wall_m: Optional[float] = None
        if plan.es and plan.ef:
            wall_m = (plan.ef - plan.es).total_seconds() / 60.0
        mid = int(op.budget_machine_id or 0)
        eid = int(op.budget_operator_employee_id or 0)
        if mid > 0 and mid in machines:
            m = machines[mid]
            m_label = f"{m.machine_no} {m.name}".strip()
        elif mid > 0:
            m_label = f"机台#{mid}"
        else:
            m_label = "—"
        if eid > 0 and eid in emps:
            e = emps[eid]
            e_label = f"{e.name}（{e.employee_no}）"
        elif eid > 0:
            e_label = f"员工#{eid}"
        else:
            e_label = "—"
        rk = (op.resource_kind or "").strip()
        if rk == "machine_type":
            rk_zh = "机台"
        elif rk == "hr_department":
            rk_zh = "人工"
        else:
            rk_zh = rk or "—"
        out.append(
            {
                "work_order_id": int(plan.work_order_id),
                "step_no": op.step_no,
                "step_name": op.step_name or "",
                "es": plan.es,
                "ef": plan.ef,
                "planned_minutes": plan.planned_minutes,
                "wall_minutes": wall_m,
                "resource_kind_zh": rk_zh,
                "budget_machine_label": m_label,
                "budget_employee_label": e_label,
                "is_critical": bool(plan.is_critical),
            }
        )
    return out
