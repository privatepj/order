from __future__ import annotations

from decimal import Decimal
from typing import Callable, Dict, List, Optional, Set, Tuple

from app import db
from app.models import (
    ProductionComponentNeed,
    ProductionPreplan,
    ProductionPreplanLine,
    ProductionWorkOrder,
    ProductionWorkOrderOperation,
    ProductionMaterialPlanDetail,
    ProductionWorkOrderOperationPlan,
    ProductionCostPlanDetail,
    ProductionProcessTemplate,
    ProductionProcessTemplateStep,
    ProductionProductRouting,
    ProductionProductRoutingStep,
)
from app.services import bom_svc, production_schedule_svc, production_cost_svc


_INV_FINISHED = bom_svc.PARENT_FINISHED  # finished=成品
_INV_SEMI = bom_svc.PARENT_SEMI  # semi=半成品
_INV_MATERIAL = bom_svc.PARENT_MATERIAL  # material=物料


def _d(val) -> Decimal:
    if val is None:
        return Decimal(0)
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def _active_bom_header_cached(
    header_cache: Dict[Tuple[str, int], Optional[object]],
    parent_kind: str,
    parent_id: int,
):
    key = (parent_kind, int(parent_id))
    if key in header_cache:
        return header_cache[key]
    h = bom_svc.get_active_bom_header(parent_kind=parent_kind, parent_id=parent_id)
    header_cache[key] = h
    return h


class _StockAllocator:
    """
    全局库存分配器：当多个需求共享同一子项库存时，通过递减可用量避免重复使用。
    """

    def __init__(self, atp_fn: Callable[[str, int], Decimal]):
        self._atp_fn = atp_fn
        self.available: Dict[Tuple[str, int], Decimal] = {}

    def _key(self, category: str, item_id: int) -> Tuple[str, int]:
        return (category, int(item_id))

    def available_for(self, category: str, item_id: int) -> Decimal:
        k = self._key(category, item_id)
        if k not in self.available:
            # ATP：台账结存 − 其他预计划等已生效预留（本单预留已在测算开头删除）
            self.available[k] = self._atp_fn(category, int(item_id))
        # 不允许负数传入后续计算
        if self.available[k] < 0:
            self.available[k] = Decimal(0)
        return self.available[k]

    def consume(self, category: str, item_id: int, qty: Decimal) -> Decimal:
        if qty <= 0:
            return Decimal(0)
        k = self._key(category, item_id)
        av = self.available_for(category, item_id)
        use = min(av, _d(qty))
        self.available[k] = av - use
        return use


def measure_production_for_preplan(
    *,
    preplan_id: int,
    created_by: int,
    max_depth: int = 20,
) -> List[int]:
    """
    二期测算管道（calc_only）：
    - Stage A/B：沿用一期逻辑，基于 BOM 与库存计算净需求 + 生成工作单与缺料；
    - Stage C：基于工序快照进行简单排程，生成 operation_plan；
    - Stage D：按工序工时估算人工/机台/制造费用，生成成本分项。

    返回：本次测算生成的 production_work_order.id 列表。
    """
    preplan = db.session.get(ProductionPreplan, preplan_id)
    if not preplan:
        raise ValueError("预生产计划不存在。")

    from app.services.production_preplan_schedule_manual_svc import (
        measure_blocked_by_reported_dispatch,
        revoke_preplan_commits_for_measure,
    )

    if measure_blocked_by_reported_dispatch(preplan_id=preplan_id):
        raise ValueError(
            "本预计划关联工单存在已报工的机台派工记录，无法重新测算。请先完成业务处理或联系管理员。"
        )
    revoke_preplan_commits_for_measure(preplan_id=preplan_id)
    db.session.flush()

    from app.services import inventory_svc as _inventory_svc

    # 删除旧测算结果（允许重复运行）
    db.session.query(ProductionComponentNeed).filter_by(preplan_id=preplan_id).delete(
        synchronize_session=False
    )
    db.session.query(ProductionWorkOrder).filter_by(preplan_id=preplan_id).delete(
        synchronize_session=False
    )
    db.session.query(ProductionWorkOrderOperation).filter_by(
        preplan_id=preplan_id
    ).delete(synchronize_session=False)
    db.session.query(ProductionWorkOrderOperationPlan).filter_by(
        preplan_id=preplan_id
    ).delete(synchronize_session=False)
    db.session.query(ProductionMaterialPlanDetail).filter_by(
        preplan_id=preplan_id
    ).delete(synchronize_session=False)
    db.session.query(ProductionCostPlanDetail).filter_by(preplan_id=preplan_id).delete(
        synchronize_session=False
    )
    _inventory_svc.delete_reservations_for_preplan(preplan_id=preplan_id)
    db.session.flush()

    root_lines = (
        ProductionPreplanLine.query.filter_by(preplan_id=preplan_id)
        .order_by(ProductionPreplanLine.line_no.asc(), ProductionPreplanLine.id.asc())
        .all()
    )
    if not root_lines:
        raise ValueError("预生产计划明细为空，无法测算。")

    allocator = _StockAllocator(
        lambda c, i: _inventory_svc.atp_for_item_aggregate(c, i),
    )
    header_cache: Dict[Tuple[str, int], Optional[object]] = {}
    process_cache: Dict[Tuple[str, int], List[Dict[str, object]]] = {}
    company_id_ctx = production_cost_svc.company_id_for_preplan(preplan)
    period_ctx = preplan.plan_date.strftime("%Y-%m") if preplan.plan_date else ""

    produced_work_order_ids: List[int] = []

    def _resolve_process_steps_for_target(
        *, target_kind: str, target_id: int
    ) -> List[Dict[str, object]]:
        """
        生产对象 -> 工序模板步骤（含路由覆写），用于测算时固化到工作单工序快照。
        """
        normalized_kind = (target_kind or "").strip()
        if normalized_kind not in (_INV_FINISHED, _INV_SEMI):
            return []
        normalized_id = int(target_id or 0)
        if normalized_id <= 0:
            return []
        cache_key = (normalized_kind, normalized_id)
        if cache_key in process_cache:
            return process_cache[cache_key]

        routing = ProductionProductRouting.query.filter_by(
            target_kind=normalized_kind,
            target_id=normalized_id,
            is_active=True,
        ).first()
        if not routing:
            process_cache[cache_key] = []
            return process_cache[cache_key]

        tpl = ProductionProcessTemplate.query.filter_by(
            id=routing.template_id, is_active=True
        ).first()
        if not tpl:
            process_cache[cache_key] = []
            return process_cache[cache_key]

        tpl_steps = (
            ProductionProcessTemplateStep.query.filter_by(
                template_id=tpl.id, is_active=True
            )
            .order_by(
                ProductionProcessTemplateStep.step_no.asc(),
                ProductionProcessTemplateStep.id.asc(),
            )
            .all()
        )
        if not tpl_steps:
            process_cache[cache_key] = []
            return process_cache[cache_key]

        overrides = ProductionProductRoutingStep.query.filter_by(
            routing_id=routing.id
        ).all()
        override_map = {x.template_step_no: x for x in overrides}

        out: List[Dict[str, object]] = []
        for st in tpl_steps:
            ov = override_map.get(st.step_no)

            final_step_name = (
                ov.step_name_override
                if ov and ov.step_name_override is not None
                else st.step_name
            )

            final_resource_kind = (
                ov.resource_kind_override
                if ov and ov.resource_kind_override is not None
                else st.resource_kind
            )
            if final_resource_kind and final_resource_kind != "machine_type":
                final_resource_kind = "hr_work_type"

            setup_minutes = (
                ov.setup_minutes_override
                if ov and ov.setup_minutes_override is not None
                else st.setup_minutes
            )
            run_minutes_per_unit = (
                ov.run_minutes_per_unit_override
                if ov and ov.run_minutes_per_unit_override is not None
                else st.run_minutes_per_unit
            )

            if ov and ov.resource_kind_override is not None:
                if final_resource_kind == "machine_type":
                    machine_type_id = ov.machine_type_id_override or st.machine_type_id
                    work_type_id = 0
                else:
                    work_type_id = (
                        ov.effective_work_type_id_override or st.effective_work_type_id
                    )
                    machine_type_id = 0
            else:
                machine_type_id = st.machine_type_id
                work_type_id = st.effective_work_type_id

            out.append(
                {
                    "step_no": st.step_no,
                    "step_code": st.step_code,
                    "step_name": final_step_name,
                    "resource_kind": final_resource_kind,
                    "machine_type_id": int(machine_type_id or 0),
                    "hr_department_id": int(work_type_id or 0),
                    "hr_work_type_id": int(work_type_id or 0),
                    "setup_minutes": _d(setup_minutes),
                    "run_minutes_per_unit": _d(run_minutes_per_unit),
                }
            )

        process_cache[cache_key] = out
        return out

    def alloc_node(
        *,
        parent_kind: str,
        parent_id: int,
        demand_qty: Decimal,
        plan_date,
        preplan_id: int,
        root_preplan_line_id: Optional[int],
        created_by: int,
        depth: int,
        path: Set[Tuple[str, int]],
    ) -> None:
        nonlocal produced_work_order_ids

        if demand_qty <= 0:
            return
        if depth > max_depth:
            raise ValueError("BOM 展开层级超过上限，请检查是否存在异常层级或循环引用。")

        key = (parent_kind, int(parent_id))
        if key in path:
            raise ValueError(f"检测到 BOM 循环引用：{parent_kind}:{parent_id}")
        path.add(key)

        # 库存覆盖当前父项
        covered = allocator.consume(parent_kind, parent_id, demand_qty)
        to_produce = _d(demand_qty) - _d(covered)
        if to_produce < 0:
            to_produce = Decimal(0)

        parent_product_id = parent_id if parent_kind == _INV_FINISHED else 0
        parent_material_id = (
            parent_id if parent_kind in (_INV_SEMI, _INV_MATERIAL) else 0
        )

        wo = ProductionWorkOrder(
            preplan_id=preplan_id,
            root_preplan_line_id=root_preplan_line_id,
            parent_kind=parent_kind,
            parent_product_id=parent_product_id,
            parent_material_id=parent_material_id,
            plan_date=plan_date,
            status="planned",
            demand_qty=_d(demand_qty),
            stock_covered_qty=_d(covered),
            to_produce_qty=_d(to_produce),
            created_by=created_by,
        )
        if to_produce > 0:
            h = _active_bom_header_cached(header_cache, parent_kind, parent_id)
            wo.remark = None
            if not h or not getattr(h, "lines", None):
                wo.remark = "未找到生效 BOM：缺口未展开。"
        else:
            wo.remark = "库存已覆盖：无需生产。"
            db.session.add(wo)
            db.session.flush()
            produced_work_order_ids.append(wo.id)
            path.remove(key)
            return

        db.session.add(wo)
        db.session.flush()
        produced_work_order_ids.append(wo.id)

        # 工序快照：对已配置路由的成品/半成品工单生成工序与预计工时
        if parent_kind in (_INV_FINISHED, _INV_SEMI) and to_produce > 0:
            process_steps = _resolve_process_steps_for_target(
                target_kind=parent_kind,
                target_id=parent_id,
            )
            if process_steps:
                plan_qty = _d(to_produce)
                for st in process_steps:
                    setup_minutes = _d(st["setup_minutes"])
                    run_minutes_per_unit = _d(st["run_minutes_per_unit"])
                    estimated_setup_minutes = setup_minutes
                    estimated_run_minutes = run_minutes_per_unit * plan_qty
                    estimated_total_minutes = (
                        estimated_setup_minutes + estimated_run_minutes
                    )

                    op = ProductionWorkOrderOperation(
                        preplan_id=preplan_id,
                        work_order_id=wo.id,
                        step_no=int(st["step_no"]),
                        step_code=st["step_code"],
                        step_name=str(st["step_name"]),
                        resource_kind=st["resource_kind"],
                        machine_type_id=int(st["machine_type_id"]),
                        hr_department_id=int(st["hr_department_id"]),
                        hr_work_type_id=int(
                            st.get("hr_work_type_id") or st["hr_department_id"]
                        ),
                        plan_qty=plan_qty,
                        setup_minutes=setup_minutes,
                        run_minutes_per_unit=run_minutes_per_unit,
                        estimated_setup_minutes=estimated_setup_minutes,
                        estimated_run_minutes=estimated_run_minutes,
                        estimated_total_minutes=estimated_total_minutes,
                        created_by=created_by,
                        remark=None,
                    )
                    rec_mid, rec_eid, _ = (
                        production_cost_svc.recommend_budget_assignment_for_operation(
                            op=op,
                            company_id=company_id_ctx,
                            period=period_ctx,
                        )
                    )
                    op.budget_machine_id = int(rec_mid or 0)
                    op.budget_operator_employee_id = int(rec_eid or 0)
                    db.session.add(op)

        if to_produce <= 0:
            path.remove(key)
            return

        header = _active_bom_header_cached(header_cache, parent_kind, parent_id)
        if not header or not header.lines:
            path.remove(key)
            return

        # 逐 BOM 子项：为生产父项生成对应需求/缺料
        sorted_lines = sorted(list(header.lines or []), key=lambda x: x.line_no)
        for ln in sorted_lines:
            child_kind = ln.child_kind
            child_id = int(ln.child_material_id)

            required_qty = _d(to_produce) * _d(ln.quantity)
            covered_child = allocator.consume(child_kind, child_id, required_qty)
            shortage_child = _d(required_qty) - _d(covered_child)
            if shortage_child < 0:
                shortage_child = Decimal(0)

            need = ProductionComponentNeed(
                preplan_id=preplan_id,
                work_order_id=wo.id,
                root_preplan_line_id=root_preplan_line_id,
                bom_header_id=header.id,
                bom_line_id=ln.id,
                child_kind=child_kind,
                child_material_id=child_id,
                required_qty=_d(required_qty),
                stock_covered_qty=_d(covered_child),
                shortage_qty=_d(shortage_child),
                coverage_mode="stock",
                unit=getattr(ln, "unit", None),
                remark=None,
            )
            db.session.add(need)
            db.session.flush()

            if shortage_child > 0:
                child_header = _active_bom_header_cached(
                    header_cache, child_kind, child_id
                )
                if child_header and child_header.lines:
                    alloc_node(
                        parent_kind=child_kind,
                        parent_id=child_id,
                        demand_qty=shortage_child,
                        plan_date=plan_date,
                        preplan_id=preplan_id,
                        root_preplan_line_id=root_preplan_line_id,
                        created_by=created_by,
                        depth=depth + 1,
                        path=path,
                    )

        path.remove(key)

    for line in root_lines:
        qty = _d(line.quantity)
        if qty <= 0:
            continue
        # 根节点：finished -> BOM 展开；允许中间 semi/material 用库存覆盖（由 allocator 控制）
        alloc_node(
            parent_kind=_INV_FINISHED,
            parent_id=int(line.product_id),
            demand_qty=qty,
            plan_date=preplan.plan_date,
            preplan_id=preplan_id,
            root_preplan_line_id=line.id,
            created_by=created_by,
            depth=0,
            path=set(),
        )

    # Stage C：排程（基于工序快照）
    production_schedule_svc.plan_operations_for_preplan(preplan_id=preplan_id)

    # Stage B→C 之间：材料分摊（当前版本直接以 component_need 为基础做 1:1 映射，scrap 为 0）
    _rebuild_material_plan_from_component_needs(preplan_id=preplan_id)

    # Stage D：成本测算
    production_cost_svc.build_cost_plan_for_preplan(preplan_id=preplan_id)

    _inventory_svc.rebuild_preplan_reservations_from_measure(
        preplan_id=preplan_id, created_by=created_by
    )

    preplan.status = "planned"
    db.session.add(preplan)
    db.session.commit()

    return produced_work_order_ids


def _rebuild_material_plan_from_component_needs(*, preplan_id: int) -> None:
    """
    材料测算 v2.1：
    - 以 component_need 为基础，将 required_qty 视为理论用量；
    - scrap_qty 暂为 0，net_required_qty=required_qty；
    - 未来可以按工序/损耗率拆分。
    """
    db.session.query(ProductionMaterialPlanDetail).filter_by(
        preplan_id=preplan_id
    ).delete(synchronize_session=False)
    db.session.flush()

    needs = (
        ProductionComponentNeed.query.filter_by(preplan_id=preplan_id)
        .order_by(ProductionComponentNeed.id.asc())
        .all()
    )
    for n in needs:
        required = _d(n.required_qty)
        scrap = Decimal(0)
        net_required = required - scrap
        row = ProductionMaterialPlanDetail(
            preplan_id=n.preplan_id,
            work_order_id=n.work_order_id,
            operation_id=None,
            component_need_id=n.id,
            child_kind=n.child_kind,
            child_material_id=n.child_material_id,
            required_qty=required,
            scrap_qty=scrap,
            net_required_qty=net_required,
            stock_covered_qty=_d(n.stock_covered_qty),
            shortage_qty=_d(n.shortage_qty),
            unit=n.unit,
            remark=n.remark,
        )
        db.session.add(row)
