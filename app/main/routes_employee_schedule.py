from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app import db
from app.auth.decorators import capability_required, menu_required
from app.models import (
    HrEmployee,
    HrEmployeeScheduleBooking,
    HrEmployeeScheduleTemplate,
    HrWorkType,
    Product,
    ProductionWorkOrder,
)
from app.services.hr_employee_schedule_svc import generate_bookings_for_range
from app.services.hr_work_type_svc import list_work_types


SCHEDULE_STATES = ("available", "unavailable")
REPEAT_KINDS = ("weekly",)
DAYS_OF_WEEK = (
    (0, "周日"),
    (1, "周一"),
    (2, "周二"),
    (3, "周三"),
    (4, "周四"),
    (5, "周五"),
    (6, "周六"),
)


def _parse_dt(raw: str | None) -> datetime | None:
    s = (raw or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _parse_date(raw: str | None) -> date | None:
    s = (raw or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_time(raw: str | None) -> time | None:
    s = (raw or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%H:%M").time()
    except ValueError:
        return None


def _parse_decimal_non_negative(raw: Any, *, default: Decimal = Decimal(0)) -> Decimal:
    if raw is None:
        return default
    s = str(raw).strip()
    if not s:
        return default
    try:
        v = Decimal(s)
    except (InvalidOperation, ValueError):
        return default
    if v < 0:
        raise ValueError("数量不能为负数。")
    return v


def _parse_int(raw: Any, *, default: Optional[int] = None) -> Optional[int]:
    if raw is None:
        return default
    s = str(raw).strip()
    if not s:
        return default
    try:
        return int(s)
    except (TypeError, ValueError):
        return default


def _text_or_none(raw: Any) -> Optional[str]:
    s = (raw or "").strip()
    return s if s else None


def register_employee_schedule_routes(bp):
    # ----------------------------
    # 人员排班：模板（可重复）
    # ----------------------------
    @bp.route("/hr-employee-schedule/templates")
    @login_required
    @menu_required("hr_employee_schedule")
    def hr_employee_schedule_template_list():
        employee_id = request.args.get("employee_id", type=int) or 0
        q = HrEmployeeScheduleTemplate.query
        if employee_id:
            q = q.filter(HrEmployeeScheduleTemplate.employee_id == employee_id)
        rows = q.order_by(HrEmployeeScheduleTemplate.id.desc()).limit(500).all()
        employees = HrEmployee.query.order_by(HrEmployee.employee_no.asc()).all()
        return render_template(
            "hr/employee_schedule_template_list.html",
            rows=rows,
            employees=employees,
            employee_id=employee_id,
            schedule_states=SCHEDULE_STATES,
        )

    @bp.route("/hr-employee-schedule/templates/new", methods=["GET", "POST"])
    @login_required
    @menu_required("hr_employee_schedule")
    @capability_required("hr_employee_schedule_template.action.create")
    def hr_employee_schedule_template_new():
        employees = HrEmployee.query.order_by(HrEmployee.employee_no.asc()).all()
        if request.method == "POST":
            return _hr_employee_schedule_template_save(None, employees=employees)
        return render_template(
            "hr/employee_schedule_template_form.html",
            row=None,
            employees=employees,
            schedule_states=SCHEDULE_STATES,
            repeat_kinds=REPEAT_KINDS,
            dow_list=DAYS_OF_WEEK,
        )

    @bp.route("/hr-employee-schedule/templates/<int:tpl_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("hr_employee_schedule")
    @capability_required("hr_employee_schedule_template.action.edit")
    def hr_employee_schedule_template_edit(tpl_id: int):
        row = HrEmployeeScheduleTemplate.query.get_or_404(tpl_id)
        employees = HrEmployee.query.order_by(HrEmployee.employee_no.asc()).all()
        if request.method == "POST":
            return _hr_employee_schedule_template_save(row, employees=employees)
        return render_template(
            "hr/employee_schedule_template_form.html",
            row=row,
            employees=employees,
            schedule_states=SCHEDULE_STATES,
            repeat_kinds=REPEAT_KINDS,
            dow_list=DAYS_OF_WEEK,
        )

    @bp.route("/hr-employee-schedule/templates/<int:tpl_id>/delete", methods=["POST"])
    @login_required
    @menu_required("hr_employee_schedule")
    @capability_required("hr_employee_schedule_template.action.delete")
    def hr_employee_schedule_template_delete(tpl_id: int):
        row = HrEmployeeScheduleTemplate.query.get_or_404(tpl_id)
        if HrEmployeeScheduleBooking.query.filter_by(template_id=row.id).first():
            flash("该模板已被展开生成时间窗，不能直接删除。", "danger")
            return redirect(
                url_for(
                    "main.hr_employee_schedule_template_list",
                    employee_id=row.employee_id,
                )
            )
        db.session.delete(row)
        db.session.commit()
        flash("排班模板已删除。", "success")
        return redirect(
            url_for(
                "main.hr_employee_schedule_template_list",
                employee_id=row.employee_id,
            )
        )

    def _hr_employee_schedule_template_save(
        row: HrEmployeeScheduleTemplate | None,
        *,
        employees: list[HrEmployee],
    ) -> str:
        employee_id = request.form.get("employee_id", type=int) or 0
        name = (request.form.get("name") or "").strip()
        repeat_kind = (request.form.get("repeat_kind") or "").strip() or "weekly"
        days_of_week = request.form.getlist("days_of_week") or []
        valid_from = _parse_date(request.form.get("valid_from"))
        valid_to = _parse_date(request.form.get("valid_to"))
        start_time = _parse_time(request.form.get("start_time"))
        end_time = _parse_time(request.form.get("end_time"))
        state = (request.form.get("state") or "").strip()
        remark = (request.form.get("remark") or "").strip() or None

        if not employee_id or not name:
            flash("人员与模板名称为必填。", "danger")
            return redirect(url_for("main.hr_employee_schedule_template_list"))
        if repeat_kind not in REPEAT_KINDS:
            flash("repeat_kind 非法。", "danger")
            return redirect(url_for("main.hr_employee_schedule_template_list"))
        if state not in SCHEDULE_STATES:
            flash("排班状态非法。", "danger")
            return redirect(url_for("main.hr_employee_schedule_template_list"))
        if not days_of_week:
            flash("至少选择一个星期。", "danger")
            return redirect(
                url_for(
                    "main.hr_employee_schedule_template_list",
                    employee_id=employee_id,
                )
            )
        if not valid_from or not start_time or not end_time:
            flash("有效期起始日期、开始时间、结束时间为必填。", "danger")
            return redirect(
                url_for(
                    "main.hr_employee_schedule_template_list",
                    employee_id=employee_id,
                )
            )

        employee = HrEmployee.query.get(employee_id)
        if not employee:
            flash("人员不存在。", "danger")
            return redirect(
                url_for(
                    "main.hr_employee_schedule_template_list",
                    employee_id=employee_id,
                )
            )

        tpl_days_csv = ",".join(sorted(set(days_of_week)))
        if not row:
            row = HrEmployeeScheduleTemplate(created_by=int(current_user.get_id()))
            db.session.add(row)

        row.employee_id = employee_id
        row.name = name
        row.repeat_kind = repeat_kind
        row.days_of_week = tpl_days_csv
        row.valid_from = valid_from
        row.valid_to = valid_to
        row.start_time = start_time
        row.end_time = end_time
        row.state = state
        row.remark = remark
        if row.created_by is None:
            row.created_by = int(current_user.get_id())

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("保存失败（可能存在重复约束）。", "danger")
            return redirect(
                url_for(
                    "main.hr_employee_schedule_template_list",
                    employee_id=employee_id,
                )
            )

        flash("排班模板已保存。", "success")
        return redirect(
            url_for(
                "main.hr_employee_schedule_template_list",
                employee_id=employee_id,
            )
        )

    # ----------------------------
    # 人员排产：时间窗（展开/手工）
    # ----------------------------
    @bp.route("/hr-employee-schedule/bookings")
    @login_required
    @menu_required("hr_employee_schedule")
    def hr_employee_schedule_booking_list():
        employee_id = request.args.get("employee_id", type=int) or 0
        date_from = _parse_date(request.args.get("date_from")) or date.today()
        date_to = _parse_date(request.args.get("date_to")) or (date.today() + timedelta(days=6))

        employees = HrEmployee.query.order_by(HrEmployee.employee_no.asc()).all()
        if not employee_id:
            return render_template(
                "hr/employee_schedule_booking_list.html",
                rows=[],
                employees=employees,
                employee_id=employee_id,
                date_from=date_from,
                date_to=date_to,
                schedule_states=SCHEDULE_STATES,
            )

        try:
            generate_bookings_for_range(
                employee_id=employee_id,
                from_date=date_from,
                to_date=date_to,
                created_by=int(current_user.get_id()),
            )
        except ValueError as e:
            flash(str(e), "danger")

        start_dt = datetime.combine(date_from, time.min)
        end_dt = datetime.combine(date_to + timedelta(days=1), time.min)

        rows = (
            HrEmployeeScheduleBooking.query.filter(
                HrEmployeeScheduleBooking.employee_id == employee_id,
                HrEmployeeScheduleBooking.start_at < end_dt,
                HrEmployeeScheduleBooking.end_at > start_dt,
            )
            .order_by(HrEmployeeScheduleBooking.start_at.asc(), HrEmployeeScheduleBooking.id.asc())
            .limit(2000)
            .all()
        )

        return render_template(
            "hr/employee_schedule_booking_list.html",
            rows=rows,
            employees=employees,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
            schedule_states=SCHEDULE_STATES,
        )

    @bp.route("/hr-employee-schedule/bookings/new", methods=["GET", "POST"])
    @login_required
    @menu_required("hr_employee_schedule")
    @capability_required("hr_employee_schedule_booking.action.create")
    def hr_employee_schedule_booking_new():
        employees = HrEmployee.query.order_by(HrEmployee.employee_no.asc()).all()
        employee_id = request.args.get("employee_id", type=int) or 0
        employee = HrEmployee.query.get(employee_id) if employee_id else None

        templates = (
            HrEmployeeScheduleTemplate.query.filter(HrEmployeeScheduleTemplate.employee_id == employee_id)
            .order_by(HrEmployeeScheduleTemplate.id.asc())
            .all()
            if employee_id
            else []
        )

        work_types = list_work_types(company_id=employee.company_id, active_only=False) if employee else []

        # 仅展示最近的成品工单，用户可手工填写 work_order_id
        recent_work_orders = (
            ProductionWorkOrder.query.filter(ProductionWorkOrder.parent_kind == "finished")
            .order_by(ProductionWorkOrder.plan_date.desc(), ProductionWorkOrder.id.desc())
            .limit(50)
            .all()
        )

        if request.method == "POST":
            return _hr_employee_schedule_booking_save(None, employees=employees)

        return render_template(
            "hr/employee_schedule_booking_form.html",
            row=None,
            employees=employees,
            templates=templates,
            work_types=work_types,
            recent_work_orders=recent_work_orders,
            employee_id=employee_id,
            schedule_states=SCHEDULE_STATES,
        )

    @bp.route("/hr-employee-schedule/bookings/<int:booking_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("hr_employee_schedule")
    @capability_required("hr_employee_schedule_booking.action.edit")
    def hr_employee_schedule_booking_edit(booking_id: int):
        row = HrEmployeeScheduleBooking.query.get_or_404(booking_id)
        employees = HrEmployee.query.order_by(HrEmployee.employee_no.asc()).all()
        employee_id = row.employee_id
        employee = HrEmployee.query.get(employee_id)

        templates = (
            HrEmployeeScheduleTemplate.query.filter(HrEmployeeScheduleTemplate.employee_id == employee_id)
            .order_by(HrEmployeeScheduleTemplate.id.asc())
            .all()
        )
        work_types = list_work_types(company_id=employee.company_id, active_only=False) if employee else []
        recent_work_orders = (
            ProductionWorkOrder.query.filter(ProductionWorkOrder.parent_kind == "finished")
            .order_by(ProductionWorkOrder.plan_date.desc(), ProductionWorkOrder.id.desc())
            .limit(50)
            .all()
        )

        if request.method == "POST":
            return _hr_employee_schedule_booking_save(row, employees=employees)

        return render_template(
            "hr/employee_schedule_booking_form.html",
            row=row,
            employees=employees,
            templates=templates,
            work_types=work_types,
            recent_work_orders=recent_work_orders,
            employee_id=employee_id,
            schedule_states=SCHEDULE_STATES,
        )

    @bp.route("/hr-employee-schedule/bookings/<int:booking_id>/delete", methods=["POST"])
    @login_required
    @menu_required("hr_employee_schedule")
    @capability_required("hr_employee_schedule_booking.action.delete")
    def hr_employee_schedule_booking_delete(booking_id: int):
        row = HrEmployeeScheduleBooking.query.get_or_404(booking_id)
        employee_id = row.employee_id
        db.session.delete(row)
        db.session.commit()
        flash("时间窗已删除。", "success")
        return redirect(
            url_for(
                "main.hr_employee_schedule_booking_list",
                employee_id=employee_id,
            )
        )

    def _hr_employee_schedule_booking_save(
        row: HrEmployeeScheduleBooking | None,
        *,
        employees: list[HrEmployee],
    ) -> str:
        employee_id = request.form.get("employee_id", type=int) or 0
        template_id = request.form.get("template_id", type=int) or 0
        state = (request.form.get("state") or "").strip()
        start_at = _parse_dt(request.form.get("start_at"))
        end_at = _parse_dt(request.form.get("end_at"))
        remark = _text_or_none(request.form.get("remark"))

        work_type_id = _parse_int(request.form.get("work_type_id"), default=None)
        work_order_id = _parse_int(request.form.get("work_order_id"), default=None)

        try:
            good_qty = _parse_decimal_non_negative(request.form.get("good_qty"))
            bad_qty = _parse_decimal_non_negative(request.form.get("bad_qty"))
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(
                url_for(
                    "main.hr_employee_schedule_booking_list",
                    employee_id=employee_id,
                )
            )

        if not employee_id or not template_id or state not in SCHEDULE_STATES or not start_at or not end_at:
            flash("人员、模板、开始/结束时间与状态为必填。", "danger")
            return redirect(
                url_for(
                    "main.hr_employee_schedule_booking_list",
                    employee_id=employee_id,
                )
            )
        if end_at <= start_at:
            flash("结束时间不能早于开始时间。", "danger")
            return redirect(
                url_for(
                    "main.hr_employee_schedule_booking_list",
                    employee_id=employee_id,
                )
            )

        template = HrEmployeeScheduleTemplate.query.get(template_id)
        if not template or template.employee_id != employee_id:
            flash("所选模板不属于当前人员。", "danger")
            return redirect(
                url_for(
                    "main.hr_employee_schedule_booking_list",
                    employee_id=employee_id,
                )
            )

        # 冲突校验：同一人员任意 booking 不得重叠
        conflict_q = HrEmployeeScheduleBooking.query.filter(
            HrEmployeeScheduleBooking.employee_id == employee_id,
            HrEmployeeScheduleBooking.start_at < end_at,
            HrEmployeeScheduleBooking.end_at > start_at,
        )
        if row:
            conflict_q = conflict_q.filter(HrEmployeeScheduleBooking.id != row.id)
        if conflict_q.first():
            flash("保存失败：该时间窗与其它时间窗冲突。", "danger")
            return redirect(
                url_for(
                    "main.hr_employee_schedule_booking_list",
                    employee_id=employee_id,
                )
            )

        # 若填写工单：回填实际工种/产品/单位，并计算 produced_qty
        product_id: int | None = None
        unit: str | None = None
        if work_order_id:
            wo = db.session.get(ProductionWorkOrder, work_order_id)
            if not wo:
                flash("所选工单不存在。", "danger")
                return redirect(
                    url_for(
                        "main.hr_employee_schedule_booking_list",
                        employee_id=employee_id,
                    )
                )
            if (wo.parent_kind or "") != "finished":
                flash("当前仅支持为“成品工单”填写工作log。", "danger")
                return redirect(
                    url_for(
                        "main.hr_employee_schedule_booking_list",
                        employee_id=employee_id,
                    )
                )
            if wo.parent_product_id is None or int(wo.parent_product_id) <= 0:
                flash("工单未能解析出成品产品。", "danger")
                return redirect(
                    url_for(
                        "main.hr_employee_schedule_booking_list",
                        employee_id=employee_id,
                    )
                )
            if not work_type_id or int(work_type_id) <= 0:
                flash("工单填写后，实际工种为必填。", "danger")
                return redirect(
                    url_for(
                        "main.hr_employee_schedule_booking_list",
                        employee_id=employee_id,
                    )
                )

            emp = db.session.get(HrEmployee, employee_id)
            work_type = db.session.get(HrWorkType, work_type_id)
            if not emp or not work_type:
                flash("人员或工种不存在。", "danger")
                return redirect(
                    url_for(
                        "main.hr_employee_schedule_booking_list",
                        employee_id=employee_id,
                    )
                )
            if int(work_type.company_id or 0) != int(emp.company_id or 0):
                flash("所选工种不属于当前人员的主体。", "danger")
                return redirect(
                    url_for(
                        "main.hr_employee_schedule_booking_list",
                        employee_id=employee_id,
                    )
                )

            product_id = int(wo.parent_product_id)
            prod = db.session.get(Product, product_id)
            unit = (prod.base_unit if prod else None) or None
        produced_qty = good_qty + bad_qty

        if not row:
            row = HrEmployeeScheduleBooking(created_by=int(current_user.get_id()))
            db.session.add(row)

        row.employee_id = employee_id
        row.template_id = template_id
        row.state = state
        row.start_at = start_at.replace(second=0, microsecond=0)
        row.end_at = end_at.replace(second=0, microsecond=0)
        row.remark = remark

        row.hr_department_id = None
        row.work_type_id = work_type_id
        row.work_order_id = work_order_id
        row.product_id = product_id
        row.unit = unit
        row.good_qty = good_qty
        row.bad_qty = bad_qty
        row.produced_qty = produced_qty

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("保存失败（可能存在重复约束）。", "danger")
            return redirect(
                url_for(
                    "main.hr_employee_schedule_booking_list",
                    employee_id=employee_id,
                )
            )

        flash("时间窗已保存。", "success")
        return redirect(
            url_for(
                "main.hr_employee_schedule_booking_list",
                employee_id=employee_id,
            )
        )

