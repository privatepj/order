from __future__ import annotations

from datetime import datetime, time, timedelta
from collections import defaultdict
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from app import db
from app.models import (
    HrEmployee,
    HrEmployeeScheduleBooking,
    Machine,
    MachineScheduleBooking,
    ProductionComponentNeed,
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
    elif rk in ("hr_department", "hr_work_type"):
        eid = int(op.budget_operator_employee_id or 0)
        if eid > 0:
            return ("employee", eid)
    return None


def _wo_matches_child_target(
    wo: ProductionWorkOrder, child_kind: str, child_material_id: int
) -> bool:
    """与测算工单字段一致：finished→parent_product_id；semi→parent_material_id。"""
    k = (child_kind or "").strip()
    cid = int(child_material_id or 0)
    if cid <= 0:
        return False
    if k == "finished":
        return (wo.parent_kind or "").strip() == "finished" and int(
            wo.parent_product_id or 0
        ) == cid
    if k == "semi":
        return (wo.parent_kind or "").strip() == "semi" and int(
            wo.parent_material_id or 0
        ) == cid
    return False


def _build_bom_child_to_parent_edges(
    *,
    preplan_id: int,
    work_orders: List[ProductionWorkOrder],
) -> Tuple[Dict[int, Set[int]], Dict[int, Set[int]]]:
    """
    子工单 → 父工单：父工单须等待其 BOM 缺口对应子工单全部完工（FS）。
    返回 (children_by_parent, parents_after_child)。
    子工单匹配：同 preplan、同 root_preplan_line_id、child_kind/child_material_id 与工单 parent 字段一致。
    多条 need 同一子项：将该父项下所有匹配子工单并入依赖（父取 max(子 EF)）。
    """
    children_by_parent: Dict[int, Set[int]] = defaultdict(set)
    wo_by_id = {int(w.id): w for w in work_orders}
    needs = (
        ProductionComponentNeed.query.filter_by(preplan_id=preplan_id)
        .order_by(ProductionComponentNeed.id.asc())
        .all()
    )
    for need in needs:
        if _d(need.shortage_qty) <= 0:
            continue
        ck = (need.child_kind or "").strip()
        if ck not in ("finished", "semi"):
            continue
        pid = int(need.work_order_id or 0)
        parent_wo = wo_by_id.get(pid)
        if not parent_wo:
            continue
        root = parent_wo.root_preplan_line_id
        cid = int(need.child_material_id or 0)
        for wo in work_orders:
            if int(wo.id) == pid:
                continue
            if wo.root_preplan_line_id != root:
                continue
            if not _wo_matches_child_target(wo, ck, cid):
                continue
            children_by_parent[pid].add(int(wo.id))

    parents_after_child: Dict[int, Set[int]] = defaultdict(set)
    for p_id, chs in children_by_parent.items():
        for c_id in chs:
            parents_after_child[c_id].add(p_id)

    return children_by_parent, parents_after_child


def list_bom_work_order_gate_errors(
    *,
    preplan_id: int,
    rows: List[Dict[str, Any]],
) -> List[str]:
    """
    人工/确认排程校验：父工单任意工序的 ES 不得早于其 BOM 子生产工单的最晚 EF（方案 A）。
    rows：含 work_order_id、es、ef（与 validate_preplan_schedule 的 row_dicts 一致）。
    """
    errs: List[str] = []
    by_wo: Dict[int, List[Tuple[datetime, datetime]]] = defaultdict(list)
    for r in rows:
        wid = int(r.get("work_order_id") or 0)
        es, ef = r.get("es"), r.get("ef")
        if wid <= 0 or not es or not ef:
            continue
        by_wo[wid].append((es, ef))

    work_orders = ProductionWorkOrder.query.filter_by(preplan_id=preplan_id).all()
    if not work_orders:
        return errs
    children_by_parent, _ = _build_bom_child_to_parent_edges(
        preplan_id=preplan_id, work_orders=list(work_orders)
    )

    for p_id, child_ids in children_by_parent.items():
        if not child_ids:
            continue
        p_times = by_wo.get(int(p_id), [])
        if not p_times:
            continue
        min_parent_es = min(t[0] for t in p_times)
        child_max_efs: List[datetime] = []
        for cid in child_ids:
            ct = by_wo.get(int(cid), [])
            if not ct:
                continue
            child_max_efs.append(max(t[1] for t in ct))
        if not child_max_efs:
            continue
        gate = max(child_max_efs)
        if min_parent_es < gate:
            errs.append(
                f"BOM 先后：父工单 WO#{p_id} 最早 ES 早于子工单完工（要求父最早 ES ≥ 子最晚 EF {gate.strftime('%m-%d %H:%M')}）。请把父工单整体排到子工单之后。"
            )
    return errs


def plan_operations_for_preplan(*, preplan_id: int) -> None:
    """
    排程 v3：
    - 工序依赖：模板 DAG，否则按 step_no 串行；
    - 前向计算 ES/EF，后向计算 LS/LF 与关键工序；
    - 资源：按 budget 机台/人员做 list scheduling；
    - 日历：有机台/人员 available 排班窗时，仅在窗内累计有效作业分钟（跨多日、跳过非工作 gap）。
    - 跨工单：BOM 子生产工单整单完工后，父工单工序方可开工（与 component_need 缺口一致）。
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

    children_by_parent, parents_after_child = _build_bom_child_to_parent_edges(
        preplan_id=preplan_id, work_orders=work_orders
    )
    wo_by_id = {int(w.id): w for w in work_orders}
    indegree: Dict[int, int] = {
        int(w.id): len(children_by_parent.get(int(w.id), set())) for w in work_orders
    }
    remaining: Set[int] = {int(w.id) for w in work_orders}
    wo_max_ef: Dict[int, datetime] = {}

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

    while remaining:
        ready = sorted(wid for wid in remaining if indegree.get(wid, 0) == 0)
        if not ready:
            logging.warning(
                "preplan_id=%s BOM 工单依赖存在环或未解析子工单，将按工单 id 强行续排。",
                preplan_id,
            )
            ready = sorted(remaining)
        wid = ready[0]
        remaining.remove(wid)
        wo = wo_by_id[wid]
        base_start = datetime.combine(wo.plan_date, datetime.min.time())
        child_ids = children_by_parent.get(wid, set())
        if child_ids:
            gate_floor = max(
                base_start,
                max((wo_max_ef[c] for c in child_ids), default=base_start),
            )
        else:
            gate_floor = base_start

        ops: List[ProductionWorkOrderOperation] = (
            ProductionWorkOrderOperation.query.filter_by(work_order_id=wo.id)
            .order_by(ProductionWorkOrderOperation.step_no.asc(), ProductionWorkOrderOperation.id.asc())
            .all()
        )
        last_ef = _plan_one_work_order(
            wo=wo,
            ops=list(ops),
            gate_floor=gate_floor,
            get_windows=get_windows,
            shared_resource_tail=shared_resource_tail,
        )
        if last_ef is not None:
            wo_max_ef[wid] = last_ef
        else:
            wo_max_ef[wid] = gate_floor

        for p in parents_after_child.get(wid, set()):
            if p in indegree:
                indegree[p] -= 1


def _plan_one_work_order(
    *,
    wo: ProductionWorkOrder,
    ops: List[ProductionWorkOrderOperation],
    gate_floor: datetime,
    get_windows,
    shared_resource_tail: Dict[Tuple[str, int], datetime],
) -> Optional[datetime]:
    """
    gate_floor：本工单无工序内向前置的工序最早可开工时间（含跨工单 BOM 门控）。
    返回本工单各工序 EF 的最大值；无工序时返回 None。
    """
    if not ops:
        return None

    predecessors: Dict[int, Set[int]] = {int(op.id): set() for op in ops}
    pred_lag_minutes: Dict[Tuple[int, int], int] = {}
    step_to_op_id: Dict[int, int] = {int(op.step_no): int(op.id) for op in ops}
    ops_by_id: Dict[int, ProductionWorkOrderOperation] = {int(op.id): op for op in ops}
    sorted_ops = sorted(ops, key=lambda x: (x.step_no, x.id))
    for i in range(1, len(sorted_ops)):
        cur_id = int(sorted_ops[i].id)
        prev_id = int(sorted_ops[i - 1].id)
        predecessors[cur_id].add(prev_id)
        pred_lag_minutes[(prev_id, cur_id)] = 0

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
        dag_pred_lag_minutes: Dict[Tuple[int, int], int] = {}
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
            if str((e.edge_type or "fs")).strip().lower() != "fs":
                continue
            dag_predecessors[to_op_id].add(from_op_id)
            dag_pred_lag_minutes[(from_op_id, to_op_id)] = int(e.lag_minutes or 0)
            has_effective_edge = True
        if has_effective_edge:
            predecessors = dag_predecessors
            pred_lag_minutes = dag_pred_lag_minutes

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
        pred_lag_minutes = {}
        for i in range(1, len(sorted_ops)):
            cur_id = int(sorted_ops[i].id)
            prev_id = int(sorted_ops[i - 1].id)
            predecessors[cur_id].add(prev_id)
            pred_lag_minutes[(prev_id, cur_id)] = 0
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
        es = max(
            (
                ef_map[p]
                + timedelta(minutes=float(pred_lag_minutes.get((p, oid), 0)))
                for p in preds
            ),
            default=gate_floor,
        )
        dur = float(_d(op.estimated_total_minutes))
        ef = es + timedelta(minutes=dur)
        es_map[oid] = es
        ef_map[oid] = ef

    project_end = max(ef_map.values()) if ef_map else gate_floor

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
            es_from = max(
                (
                    ef_final[p]
                    + timedelta(minutes=float(pred_lag_minutes.get((p, oid), 0)))
                    for p in preds
                )
            )
        else:
            es_from = gate_floor

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
                hr_work_type_id=op.effective_work_type_id,
                planned_minutes=_d(op.estimated_total_minutes),
                remark=None,
            )
        )

    return max(ef_final.values()) if ef_final else None


def _resolve_template_id_for_work_order(wo: ProductionWorkOrder) -> Optional[int]:
    parent_kind = (wo.parent_kind or "").strip()
    if parent_kind not in ("finished", "semi"):
        return None
    if parent_kind == "finished":
        target_id = int(wo.parent_product_id or 0)
    else:
        target_id = int(wo.parent_material_id or 0)
    if target_id <= 0:
        return None
    routing = ProductionProductRouting.query.filter_by(
        target_kind=parent_kind,
        target_id=target_id,
        is_active=True,
    ).first()
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
        elif rk in ("hr_department", "hr_work_type"):
            rk_zh = "工种"
        else:
            rk_zh = rk or "—"
        out.append(
            {
                "plan_id": int(plan.id),
                "operation_id": int(op.id),
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
                "resource_kind": rk,
                "confirmed_at": plan.confirmed_at,
                "budget_machine_id": mid,
                "budget_operator_employee_id": eid,
            }
        )
    return out
