from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import case, func

from app import db
from app.models import (
    InventoryMovement,
    InventoryOpeningBalance,
    ProductionComponentNeed,
    ProductionPreplan,
    ProductionPreplanLine,
    ProductionWorkOrder,
)
from app.services import bom_svc


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


def _stock_total_qty(category: str, item_id: int) -> Decimal:
    """
    取某维度的库存总量（忽略仓储区）：opening + qty_in - qty_out。
    说明：v1 默认把所有 storage_area 视作同一池进行分配。
    """
    item_id = int(item_id)
    if category == _INV_FINISHED:
        pid, mid = item_id, 0
    else:
        pid, mid = 0, item_id

    opening_qty = (
        db.session.query(func.coalesce(func.sum(InventoryOpeningBalance.opening_qty), 0))
        .filter(
            InventoryOpeningBalance.category == category,
            InventoryOpeningBalance.product_id == pid,
            InventoryOpeningBalance.material_id == mid,
        )
        .scalar()
    )

    qty_in_out = (
        db.session.query(
            func.coalesce(
                func.sum(case((InventoryMovement.direction == "in", InventoryMovement.quantity), else_=0)),
                0,
            ).label("qty_in"),
            func.coalesce(
                func.sum(case((InventoryMovement.direction == "out", InventoryMovement.quantity), else_=0)),
                0,
            ).label("qty_out"),
        )
        .filter(
            InventoryMovement.category == category,
            InventoryMovement.product_id == pid,
            InventoryMovement.material_id == mid,
        )
        .one()
    )
    qty_in = qty_in_out.qty_in
    qty_out = qty_in_out.qty_out
    return _d(opening_qty) + _d(qty_in) - _d(qty_out)


class _StockAllocator:
    """
    全局库存分配器：当多个需求共享同一子项库存时，通过递减可用量避免重复使用。
    """

    def __init__(self):
        self.available: Dict[Tuple[str, int], Decimal] = {}

    def _key(self, category: str, item_id: int) -> Tuple[str, int]:
        return (category, int(item_id))

    def available_for(self, category: str, item_id: int) -> Decimal:
        k = self._key(category, item_id)
        if k not in self.available:
            self.available[k] = _stock_total_qty(category, item_id)
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
    基于 BOM 与库存，计算某个预生产计划的净需求：
    - 先用库存覆盖父项需求
    - 不足部分按 active BOM 展开；继续“库存覆盖 + 递归生产/缺料”

    返回：本次测算生成的 production_work_order.id 列表。
    """
    preplan = db.session.get(ProductionPreplan, preplan_id)
    if not preplan:
        raise ValueError("预生产计划不存在。")

    # 删除旧测算结果（允许重复运行）
    db.session.query(ProductionComponentNeed).filter_by(preplan_id=preplan_id).delete(
        synchronize_session=False
    )
    db.session.query(ProductionWorkOrder).filter_by(preplan_id=preplan_id).delete(
        synchronize_session=False
    )
    db.session.flush()

    root_lines = (
        ProductionPreplanLine.query.filter_by(preplan_id=preplan_id)
        .order_by(ProductionPreplanLine.line_no.asc(), ProductionPreplanLine.id.asc())
        .all()
    )
    if not root_lines:
        raise ValueError("预生产计划明细为空，无法测算。")

    allocator = _StockAllocator()
    header_cache: Dict[Tuple[str, int], Optional[object]] = {}

    produced_work_order_ids: List[int] = []

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
        parent_material_id = parent_id if parent_kind in (_INV_SEMI, _INV_MATERIAL) else 0

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
                child_header = _active_bom_header_cached(header_cache, child_kind, child_id)
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

    preplan.status = "planned"
    db.session.add(preplan)
    db.session.commit()

    return produced_work_order_ids

