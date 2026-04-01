from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from app import db
from app.models import (
    HrDepartment,
    MachineType,
    ProductionCostPlanDetail,
    ProductionMaterialPlanDetail,
    ProductionWorkOrder,
    ProductionWorkOrderOperation,
)


def _d(val) -> Decimal:
    if val is None:
        return Decimal(0)
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def _hourly_rate_for_machine(machine_type_id: int) -> Decimal:
    mt = db.session.get(MachineType, int(machine_type_id)) if machine_type_id else None
    # 预留：未来可扩展到独立费率表；当前简单用 remark 或默认常量
    return Decimal(100)  # 每机时 100 元，示例口径


def _hourly_rate_for_department(dept_id: int) -> Decimal:
    dept = db.session.get(HrDepartment, int(dept_id)) if dept_id else None
    return Decimal(80)  # 每工时 80 元，示例口径


def build_cost_plan_for_preplan(*, preplan_id: int) -> None:
    """
    成本测算 v2.1（示例口径）：
    - 材料成本：暂不在此计算，后续可以结合采购价或标准价补充；
    - 人工/机台成本：按工序预计工时 * 费率 计算；
    - 制造费用：按人工+机台成本的一定比例分摊。
    """
    db.session.query(ProductionCostPlanDetail).filter_by(preplan_id=preplan_id).delete(
        synchronize_session=False
    )
    db.session.flush()

    work_orders: Iterable[ProductionWorkOrder] = (
        ProductionWorkOrder.query.filter_by(preplan_id=preplan_id)
        .order_by(ProductionWorkOrder.id.asc())
        .all()
    )
    for wo in work_orders:
        ops: Iterable[ProductionWorkOrderOperation] = (
            ProductionWorkOrderOperation.query.filter_by(work_order_id=wo.id)
            .order_by(ProductionWorkOrderOperation.step_no.asc(), ProductionWorkOrderOperation.id.asc())
            .all()
        )

        labor_total = Decimal(0)
        machine_total = Decimal(0)

        for op in ops:
            minutes = _d(op.estimated_total_minutes)
            hours = minutes / Decimal(60)
            if op.resource_kind == "hr_department" and op.hr_department_id:
                rate = _hourly_rate_for_department(op.hr_department_id)
                amount = hours * rate
                labor_total += amount
                db.session.add(
                    ProductionCostPlanDetail(
                        preplan_id=wo.preplan_id,
                        work_order_id=wo.id,
                        operation_id=op.id,
                        cost_category="labor",
                        amount=amount,
                        currency="CNY",
                        unit_cost=rate,
                        qty_basis=hours,
                        remark=None,
                    )
                )
            elif op.resource_kind == "machine_type" and op.machine_type_id:
                rate = _hourly_rate_for_machine(op.machine_type_id)
                amount = hours * rate
                machine_total += amount
                db.session.add(
                    ProductionCostPlanDetail(
                        preplan_id=wo.preplan_id,
                        work_order_id=wo.id,
                        operation_id=op.id,
                        cost_category="machine",
                        amount=amount,
                        currency="CNY",
                        unit_cost=rate,
                        qty_basis=hours,
                        remark=None,
                    )
                )

        # 制造费用：简单按人工+机台成本的 20% 分摊到工单级别
        base = labor_total + machine_total
        if base > 0:
            overhead_amount = base * Decimal("0.20")
            db.session.add(
                ProductionCostPlanDetail(
                    preplan_id=wo.preplan_id,
                    work_order_id=wo.id,
                    operation_id=None,
                    cost_category="overhead",
                    amount=overhead_amount,
                    currency="CNY",
                    unit_cost=None,
                    qty_basis=None,
                    remark="按人工+机台成本 20% 计提制造费用（示例口径）",
                )
            )

