from __future__ import annotations

from decimal import Decimal
from typing import Dict

from flask import render_template, request
from flask_login import login_required

from app.auth.decorators import capability_required, menu_required
from app.models import Company, HrDepartment, HrEmployee, HrEmployeeCapability


def _companies():
    return Company.query.order_by(Company.id).all()


def _resolve_company_id():
    # HR 能力表不允许选择主体：一律使用默认主体（无则兜底取最小 id）
    companies = _companies()
    return Company.get_default_id(), companies


def register_employee_capability_routes(bp):
    @bp.route("/hr-employee-capability")
    @login_required
    @menu_required("hr_employee_capability")
    @capability_required("hr_employee_capability.view")
    def hr_employee_capability_list():
        company_id, _ = _resolve_company_id()
        employee_id = request.args.get("employee_id", type=int) or 0
        hr_department_id = request.args.get("hr_department_id", type=int) or 0

        q = HrEmployeeCapability.query.filter_by(company_id=company_id)
        if employee_id:
            q = q.filter(HrEmployeeCapability.employee_id == employee_id)
        if hr_department_id:
            q = q.filter(HrEmployeeCapability.hr_department_id == hr_department_id)

        rows = (
            q.order_by(HrEmployeeCapability.produced_qty_total.desc(), HrEmployeeCapability.id.asc())
            .limit(2000)
            .all()
        )

        emp_ids = {int(r.employee_id) for r in rows}
        dept_ids = {int(r.hr_department_id) for r in rows}
        emp_map: Dict[int, HrEmployee] = {
            int(e.id): e for e in HrEmployee.query.filter(HrEmployee.id.in_(emp_ids)).all()
        }
        dept_map: Dict[int, HrDepartment] = {
            int(d.id): d for d in HrDepartment.query.filter(HrDepartment.id.in_(dept_ids)).all()
        }

        for r in rows:
            produced = Decimal(r.produced_qty_total or 0)
            worked_minutes = Decimal(r.worked_minutes_total or 0)
            worked_hours = worked_minutes / Decimal(60)
            bad = Decimal(r.bad_qty_total or 0)
            labor_cost = Decimal(r.labor_cost_total or 0)

            r.employee_no = emp_map.get(int(r.employee_id)).employee_no if emp_map.get(int(r.employee_id)) else "-"
            r.employee_name = emp_map.get(int(r.employee_id)).name if emp_map.get(int(r.employee_id)) else "-"
            r.department_name = (
                dept_map.get(int(r.hr_department_id)).name if dept_map.get(int(r.hr_department_id)) else "-"
            )

            r.worked_hours_total = worked_hours
            r.bad_rate_pct = (
                (bad / produced * Decimal(100)).quantize(Decimal("0.01")) if produced > 0 else None
            )
            r.hourly_capacity = (
                (produced / worked_hours).quantize(Decimal("0.0001"))
                if worked_hours > 0
                else None
            )
            r.unit_cost = (
                (labor_cost / produced).quantize(Decimal("0.0001")) if produced > 0 else None
            )

        employees = HrEmployee.query.filter_by(company_id=company_id).order_by(HrEmployee.employee_no.asc()).all()
        departments = (
            HrDepartment.query.filter_by(company_id=company_id)
            .order_by(HrDepartment.sort_order.asc(), HrDepartment.id.asc())
            .all()
        )

        return render_template(
            "hr/employee_capability_list.html",
            rows=rows,
            employees=employees,
            departments=departments,
            employee_id=employee_id,
            hr_department_id=hr_department_id,
        )

