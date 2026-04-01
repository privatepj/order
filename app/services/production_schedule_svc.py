from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Set

from app import db
from app.models import (
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


def plan_operations_for_preplan(*, preplan_id: int) -> None:
    """
    简单排程实现（v2.1）：
    - 以工单 plan_date 为基准，只做日级顺排；
    - 同一工单内按 step_no 串行，计算 ES/EF；
    - 暂不考虑跨工单/资源抢占，先满足“可解释的工序工期”。
    """
    # 清理旧排程结果
    db.session.query(ProductionWorkOrderOperationPlan).filter_by(preplan_id=preplan_id).delete(
        synchronize_session=False
    )
    db.session.flush()

    work_orders: Iterable[ProductionWorkOrder] = (
        ProductionWorkOrder.query.filter_by(preplan_id=preplan_id)
        .order_by(ProductionWorkOrder.id.asc())
        .all()
    )

    for wo in work_orders:
        base_start = datetime.combine(wo.plan_date, datetime.min.time())
        ops: Iterable[ProductionWorkOrderOperation] = (
            ProductionWorkOrderOperation.query.filter_by(work_order_id=wo.id)
            .order_by(ProductionWorkOrderOperation.step_no.asc(), ProductionWorkOrderOperation.id.asc())
            .all()
        )
        _plan_one_work_order(wo=wo, ops=list(ops), base_start=base_start)


def _plan_one_work_order(
    *,
    wo: ProductionWorkOrder,
    ops: List[ProductionWorkOrderOperation],
    base_start: datetime,
) -> None:
    if not ops:
        return

    # 默认依赖：按 step_no 串行
    predecessors: Dict[int, Set[int]] = {int(op.id): set() for op in ops}
    step_to_op_id: Dict[int, int] = {int(op.step_no): int(op.id) for op in ops}
    ops_by_id: Dict[int, ProductionWorkOrderOperation] = {int(op.id): op for op in ops}
    sorted_ops = sorted(ops, key=lambda x: (x.step_no, x.id))
    for i in range(1, len(sorted_ops)):
        cur_id = int(sorted_ops[i].id)
        prev_id = int(sorted_ops[i - 1].id)
        predecessors[cur_id].add(prev_id)

    # 若能解析到模板DAG，则使用 DAG 覆盖默认串行依赖
    template_id = _resolve_template_id_for_work_order(wo)
    if template_id:
        node_map = {
            int(n.id): int(n.step_no)
            for n in ProductionProcessNode.query.filter_by(template_id=template_id, node_type="operation", is_active=True).all()
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

    # 拓扑顺排：ES = max(所有前置EF)，无前置则取 base_start
    es_map: Dict[int, datetime] = {}
    ef_map: Dict[int, datetime] = {}
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

    # 环或异常时回退串行
    if len(topo) != len(ops):
        topo = [int(op.id) for op in sorted_ops]
        predecessors = {int(op.id): set() for op in ops}
        for i in range(1, len(sorted_ops)):
            predecessors[int(sorted_ops[i].id)].add(int(sorted_ops[i - 1].id))

    for oid in topo:
        op = ops_by_id[oid]
        preds = predecessors.get(oid, set())
        es = max((ef_map[p] for p in preds), default=base_start)
        dur = _d(op.estimated_total_minutes)
        ef = es + timedelta(minutes=float(dur))
        es_map[oid] = es
        ef_map[oid] = ef
        db.session.add(
            ProductionWorkOrderOperationPlan(
                preplan_id=wo.preplan_id,
                work_order_id=wo.id,
                operation_id=op.id,
                process_node_id=None,
                plan_date=wo.plan_date,
                es=es,
                ef=ef,
                ls=None,
                lf=None,
                is_critical=True,
                resource_kind=op.resource_kind,
                machine_type_id=op.machine_type_id,
                hr_department_id=op.hr_department_id,
                planned_minutes=dur,
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

