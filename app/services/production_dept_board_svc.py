"""部门生产看板：按行政部门聚合相关工序（机台归属 / 工序部门与部门-工种映射）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import and_, exists, or_, select

from app import db
from app.models import (
    Customer,
    HrDepartmentWorkTypeMap,
    Machine,
    ProductionPreplan,
    ProductionWorkOrder,
    ProductionWorkOrderOperation,
    ProductionWorkOrderOperationPlan,
)


def list_board_rows(*, dept_id: int, company_id: int) -> List[Dict[str, Any]]:
    """
    返回当前部门相关的工序行（含预计划、工单、可选排程 ES/EF）。
    company_id：默认经营主体，用于过滤预计划客户归属及部门-工种映射；0 表示不按公司过滤。
    """
    dept_id = int(dept_id)
    company_id = int(company_id or 0)

    op = ProductionWorkOrderOperation
    wo = ProductionWorkOrder
    pp = ProductionPreplan
    pl = ProductionWorkOrderOperationPlan

    cust_filter = True
    if company_id:
        cust_ids = [r for r, in db.session.query(Customer.id).filter(Customer.company_id == company_id).all()]
        if not cust_ids:
            return []
        cust_filter = pp.customer_id.in_(cust_ids)

    map_subq_conditions = [
        HrDepartmentWorkTypeMap.department_id == dept_id,
        HrDepartmentWorkTypeMap.work_type_id == op.hr_work_type_id,
        HrDepartmentWorkTypeMap.is_active.is_(True),
    ]
    if company_id:
        map_subq_conditions.append(HrDepartmentWorkTypeMap.company_id == company_id)

    work_type_map_exists = exists(
        select(1).select_from(HrDepartmentWorkTypeMap).where(and_(*map_subq_conditions))
    )

    machine_budget_match = exists(
        select(1)
        .select_from(Machine)
        .where(
            Machine.id == op.budget_machine_id,
            Machine.owning_hr_department_id == dept_id,
        )
    )
    machine_type_pool_match = exists(
        select(1)
        .select_from(Machine)
        .where(
            Machine.machine_type_id == op.machine_type_id,
            Machine.status == "enabled",
            Machine.owning_hr_department_id == dept_id,
        )
    )

    machine_clause = and_(
        op.resource_kind == "machine_type",
        op.machine_type_id > 0,
        or_(
            and_(op.budget_machine_id > 0, machine_budget_match),
            and_(op.budget_machine_id == 0, machine_type_pool_match),
        ),
    )

    hr_clause = and_(
        op.resource_kind.in_(("hr_department", "hr_work_type")),
        or_(
            op.hr_department_id == dept_id,
            and_(op.hr_work_type_id > 0, work_type_map_exists),
        ),
    )

    rows = (
        db.session.query(op, wo, pp, pl)
        .join(wo, op.work_order_id == wo.id)
        .join(pp, op.preplan_id == pp.id)
        .outerjoin(pl, pl.operation_id == op.id)
        .filter(cust_filter)
        .filter(wo.status != "cancelled")
        .filter(or_(machine_clause, hr_clause))
        .order_by(pp.plan_date.asc(), pp.id.asc(), wo.id.asc(), op.step_no.asc())
        .all()
    )

    out: List[Dict[str, Any]] = []
    for operation, work_order, preplan, oplan in rows:
        parent_label = ""
        if work_order.parent_kind == "finished" and work_order.parent_product:
            p = work_order.parent_product
            parent_label = f"{p.product_code or ''} {p.name or ''}".strip() or f"成品#{p.id}"
        elif work_order.parent_kind in ("semi", "material") and work_order.parent_material:
            m = work_order.parent_material
            parent_label = f"{m.material_code or ''} {m.name or ''}".strip() or f"物料#{m.id}"

        machine_label = ""
        mid = int(operation.budget_machine_id or 0)
        if mid:
            m = db.session.get(Machine, mid)
            if m:
                machine_label = f"{m.machine_no} {m.name or ''}".strip()

        emp_label = ""
        eid = int(operation.budget_operator_employee_id or 0)
        if eid:
            from app.models import HrEmployee

            emp = db.session.get(HrEmployee, eid)
            if emp:
                emp_label = f"{emp.employee_no} {emp.name or ''}".strip()

        out.append(
            {
                "preplan_id": int(preplan.id),
                "preplan_plan_date": preplan.plan_date,
                "preplan_status": preplan.status,
                "work_order_id": int(work_order.id),
                "operation_id": int(operation.id),
                "step_no": int(operation.step_no or 0),
                "step_name": (operation.step_name or "").strip(),
                "resource_kind": (operation.resource_kind or "").strip(),
                "parent_label": parent_label,
                "machine_label": machine_label,
                "employee_label": emp_label,
                "es": oplan.es if oplan else None,
                "ef": oplan.ef if oplan else None,
            }
        )
    return out
