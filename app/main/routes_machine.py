from __future__ import annotations

from datetime import date, datetime, time, timedelta

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app import db
from app.auth.capabilities import current_user_can_cap
from app.auth.decorators import capability_required, menu_required
from app.models import (
    Company,
    HrEmployee,
    HrWorkType,
    Machine,
    MachineOperatorAllowlist,
    MachineRuntimeLog,
    MachineScheduleBooking,
    MachineScheduleTemplate,
    MachineType,
    User,
)
from app.services.machine_schedule_svc import generate_bookings_for_range


MACHINE_STATUS = ("enabled", "disabled", "maintenance", "scrapped")
RUNTIME_STATUS = ("running", "idle", "fault")
SCHEDULE_STATES = ("available", "unavailable")
def _hr_departments_for_machine_form():
    cid = Company.get_default_id()
    if not cid:
        return []
    return (
        HrWorkType.query.filter_by(company_id=cid)
        .order_by(HrWorkType.sort_order, HrWorkType.id)
        .all()
    )


DAYS_OF_WEEK = (
    (0, "周日"),
    (1, "周一"),
    (2, "周二"),
    (3, "周三"),
    (4, "周四"),
    (5, "周五"),
    (6, "周六"),
)
REPEAT_KINDS = ("weekly",)


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


def register_machine_routes(bp):
    @bp.route("/machine/types")
    @login_required
    @menu_required("machine_type")
    def machine_type_list():
        keyword = (request.args.get("keyword") or "").strip()
        q = MachineType.query
        if keyword:
            q = q.filter(or_(MachineType.code.contains(keyword), MachineType.name.contains(keyword)))
        rows = q.order_by(MachineType.id.desc()).all()
        return render_template("machine/type_list.html", rows=rows, keyword=keyword)

    @bp.route("/machine/types/new", methods=["GET", "POST"])
    @login_required
    @menu_required("machine_type")
    @capability_required("machine_type.action.create")
    def machine_type_new():
        hr_departments = _hr_departments_for_machine_form()
        if request.method == "POST":
            code = (request.form.get("code") or "").strip().upper()
            name = (request.form.get("name") or "").strip()
            is_active = (request.form.get("is_active") or "1") == "1"
            remark = (request.form.get("remark") or "").strip() or None
            def_cap = (
                request.form.get("default_capability_work_type_id", type=int)
                or request.form.get("default_capability_hr_department_id", type=int)
                or 0
            )
            if def_cap < 0:
                def_cap = 0
            if not code or not name:
                flash("种类编码和名称为必填。", "danger")
                return render_template("machine/type_form.html", row=None, hr_departments=hr_departments)
            row = MachineType(
                code=code,
                name=name,
                is_active=is_active,
                remark=remark,
                default_capability_hr_department_id=0,
                default_capability_work_type_id=def_cap,
            )
            db.session.add(row)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("种类编码或名称重复。", "danger")
                return render_template("machine/type_form.html", row=None, hr_departments=hr_departments)
            flash("机台种类已新增。", "success")
            return redirect(url_for("main.machine_type_list"))
        return render_template("machine/type_form.html", row=None, hr_departments=hr_departments)

    @bp.route("/machine/types/<int:type_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("machine_type")
    @capability_required("machine_type.action.edit")
    def machine_type_edit(type_id):
        row = MachineType.query.get_or_404(type_id)
        hr_departments = _hr_departments_for_machine_form()
        if request.method == "POST":
            code = (request.form.get("code") or "").strip().upper()
            name = (request.form.get("name") or "").strip()
            is_active = (request.form.get("is_active") or "1") == "1"
            remark = (request.form.get("remark") or "").strip() or None
            def_cap = (
                request.form.get("default_capability_work_type_id", type=int)
                or request.form.get("default_capability_hr_department_id", type=int)
                or 0
            )
            if def_cap < 0:
                def_cap = 0
            if not code or not name:
                flash("种类编码和名称为必填。", "danger")
                return render_template("machine/type_form.html", row=row, hr_departments=hr_departments)
            row.code = code
            row.name = name
            row.is_active = is_active
            row.remark = remark
            row.default_capability_hr_department_id = 0
            row.default_capability_work_type_id = def_cap
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("种类编码或名称重复。", "danger")
                return render_template("machine/type_form.html", row=row, hr_departments=hr_departments)
            flash("机台种类已更新。", "success")
            return redirect(url_for("main.machine_type_list"))
        return render_template("machine/type_form.html", row=row, hr_departments=hr_departments)

    @bp.route("/machine/types/<int:type_id>/delete", methods=["POST"])
    @login_required
    @menu_required("machine_type")
    @capability_required("machine_type.action.delete")
    def machine_type_delete(type_id):
        row = MachineType.query.get_or_404(type_id)
        if Machine.query.filter_by(machine_type_id=row.id).first():
            flash("该种类下仍有机台，无法删除。", "danger")
            return redirect(url_for("main.machine_type_list"))
        db.session.delete(row)
        db.session.commit()
        flash("机台种类已删除。", "success")
        return redirect(url_for("main.machine_type_list"))

    @bp.route("/machines")
    @login_required
    @menu_required("machine_asset")
    def machine_list():
        keyword = (request.args.get("keyword") or "").strip()
        status = (request.args.get("status") or "").strip()
        type_id = request.args.get("machine_type_id", type=int)
        q = Machine.query
        if current_user_can_cap("machine_asset.filter.keyword") and keyword:
            q = q.filter(
                or_(
                    Machine.machine_no.contains(keyword),
                    Machine.name.contains(keyword),
                    Machine.location.contains(keyword),
                )
            )
        if status and status in MACHINE_STATUS:
            q = q.filter(Machine.status == status)
        if type_id:
            q = q.filter(Machine.machine_type_id == type_id)
        rows = q.order_by(Machine.id.desc()).all()
        types = MachineType.query.order_by(MachineType.name).all()
        return render_template(
            "machine/machine_list.html",
            rows=rows,
            types=types,
            keyword=keyword,
            status=status,
            machine_type_id=type_id,
            machine_statuses=MACHINE_STATUS,
        )

    @bp.route("/machines/new", methods=["GET", "POST"])
    @login_required
    @menu_required("machine_asset")
    @capability_required("machine_asset.action.create")
    def machine_new():
        types = MachineType.query.order_by(MachineType.name).all()
        users = User.query.order_by(User.id).all()
        hr_departments = _hr_departments_for_machine_form()
        if request.method == "POST":
            return _machine_save(None, types, users)
        return render_template(
            "machine/machine_form.html",
            row=None,
            types=types,
            users=users,
            machine_statuses=MACHINE_STATUS,
            hr_departments=hr_departments,
        )

    @bp.route("/machines/<int:machine_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("machine_asset")
    @capability_required("machine_asset.action.edit")
    def machine_edit(machine_id):
        row = Machine.query.get_or_404(machine_id)
        types = MachineType.query.order_by(MachineType.name).all()
        users = User.query.order_by(User.id).all()
        hr_departments = _hr_departments_for_machine_form()
        if request.method == "POST":
            return _machine_save(row, types, users)
        return render_template(
            "machine/machine_form.html",
            row=row,
            types=types,
            users=users,
            machine_statuses=MACHINE_STATUS,
            hr_departments=hr_departments,
        )

    def _machine_save(row, types, users):
        hr_departments = _hr_departments_for_machine_form()
        machine_no = (request.form.get("machine_no") or "").strip().upper()
        name = (request.form.get("name") or "").strip()
        machine_type_id = request.form.get("machine_type_id", type=int)
        status = (request.form.get("status") or "enabled").strip()
        location = (request.form.get("location") or "").strip() or None
        owner_user_id = request.form.get("owner_user_id", type=int) or None
        remark = (request.form.get("remark") or "").strip() or None
        def_cap_raw = (
            request.form.get("default_capability_work_type_id", type=int)
            or request.form.get("default_capability_hr_department_id", type=int)
        )
        def_cap_m = max(0, int(def_cap_raw or 0))
        is_admin = getattr(current_user, "role_code", None) == "admin"
        try:
            capacity_per_hour = float((request.form.get("capacity_per_hour") or "0").strip())
        except ValueError:
            flash("标准产能格式不正确。", "danger")
            return render_template(
                "machine/machine_form.html",
                row=row,
                types=types,
                users=users,
                machine_statuses=MACHINE_STATUS,
                hr_departments=hr_departments,
            )

        machine_cost_purchase_price = None
        machine_single_run_cost = None
        if is_admin:
            purchase_raw = (request.form.get("machine_cost_purchase_price") or "").strip()
            single_raw = (request.form.get("machine_single_run_cost") or "").strip()
            try:
                machine_cost_purchase_price = float(purchase_raw) if purchase_raw != "" else 0.0
                if machine_cost_purchase_price < 0:
                    raise ValueError()
            except ValueError:
                flash("购入价格格式不正确或不能为负数。", "danger")
                return render_template(
                    "machine/machine_form.html",
                    row=row,
                    types=types,
                    users=users,
                    machine_statuses=MACHINE_STATUS,
                    hr_departments=hr_departments,
                )
            try:
                if single_raw == "":
                    machine_single_run_cost = None
                else:
                    machine_single_run_cost = float(single_raw)
                    if machine_single_run_cost < 0:
                        raise ValueError()
            except ValueError:
                flash("单次运行成本格式不正确或不能为负数。", "danger")
                return render_template(
                    "machine/machine_form.html",
                    row=row,
                    types=types,
                    users=users,
                    machine_statuses=MACHINE_STATUS,
                    hr_departments=hr_departments,
                )
        if not machine_no or not name or not machine_type_id:
            flash("机台编号、名称、种类为必填。", "danger")
            return render_template(
                "machine/machine_form.html",
                row=row,
                types=types,
                users=users,
                machine_statuses=MACHINE_STATUS,
                hr_departments=hr_departments,
            )
        if status not in MACHINE_STATUS:
            status = "enabled"
        mt = MachineType.query.get(machine_type_id)
        if not mt:
            flash("机台种类不存在。", "danger")
            return render_template(
                "machine/machine_form.html",
                row=row,
                types=types,
                users=users,
                machine_statuses=MACHINE_STATUS,
                hr_departments=hr_departments,
            )
        if owner_user_id and not User.query.get(owner_user_id):
            flash("责任人不存在。", "danger")
            return render_template(
                "machine/machine_form.html",
                row=row,
                types=types,
                users=users,
                machine_statuses=MACHINE_STATUS,
                hr_departments=hr_departments,
            )
        if capacity_per_hour < 0:
            flash("标准产能不能为负数。", "danger")
            return render_template(
                "machine/machine_form.html",
                row=row,
                types=types,
                users=users,
                machine_statuses=MACHINE_STATUS,
                hr_departments=hr_departments,
            )
        if not row:
            row = Machine(machine_no=machine_no)
            db.session.add(row)
        row.machine_no = machine_no
        row.name = name
        row.machine_type_id = machine_type_id
        row.capacity_per_hour = capacity_per_hour
        if is_admin:
            row.machine_cost_purchase_price = machine_cost_purchase_price if machine_cost_purchase_price is not None else 0.0
            row.machine_single_run_cost = machine_single_run_cost
        row.status = status
        row.location = location
        row.owner_user_id = owner_user_id
        row.remark = remark
        row.default_capability_hr_department_id = 0
        row.default_capability_work_type_id = def_cap_m
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("机台编号重复。", "danger")
            return render_template(
                "machine/machine_form.html",
                row=row,
                types=types,
                users=users,
                machine_statuses=MACHINE_STATUS,
                hr_departments=hr_departments,
            )
        flash("机台信息已保存。", "success")
        return redirect(url_for("main.machine_list"))

    @bp.route("/machines/<int:machine_id>")
    @login_required
    @menu_required("machine_asset")
    def machine_detail(machine_id):
        row = Machine.query.options(selectinload(Machine.machine_type)).get_or_404(machine_id)
        open_log = (
            MachineRuntimeLog.query.filter_by(machine_id=machine_id, ended_at=None)
            .order_by(MachineRuntimeLog.started_at.desc(), MachineRuntimeLog.id.desc())
            .first()
        )
        latest_logs = (
            MachineRuntimeLog.query.filter_by(machine_id=machine_id)
            .order_by(MachineRuntimeLog.started_at.desc(), MachineRuntimeLog.id.desc())
            .limit(20)
            .all()
        )
        allowlist = (
            MachineOperatorAllowlist.query.options(selectinload(MachineOperatorAllowlist.employee))
            .filter_by(machine_id=machine_id)
            .order_by(MachineOperatorAllowlist.id.asc())
            .all()
        )
        employees = (
            HrEmployee.query.filter(HrEmployee.status == "active")
            .order_by(HrEmployee.employee_no.asc())
            .limit(800)
            .all()
        )
        return render_template(
            "machine/machine_detail.html",
            row=row,
            open_log=open_log,
            latest_logs=latest_logs,
            allowlist=allowlist,
            employees=employees,
        )

    @bp.route("/machines/<int:machine_id>/operator-allowlist/add", methods=["POST"])
    @login_required
    @menu_required("machine_asset")
    @capability_required("machine_asset.action.edit")
    def machine_operator_allowlist_add(machine_id):
        Machine.query.get_or_404(machine_id)
        employee_id = request.form.get("employee_id", type=int)
        cap_dept = (
            request.form.get("capability_work_type_id", type=int)
            or request.form.get("capability_hr_department_id", type=int)
            or 0
        )
        if not employee_id:
            flash("请选择员工。", "danger")
            return redirect(url_for("main.machine_detail", machine_id=machine_id))
        if not HrEmployee.query.get(employee_id):
            flash("员工不存在。", "danger")
            return redirect(url_for("main.machine_detail", machine_id=machine_id))
        row = MachineOperatorAllowlist(
            machine_id=machine_id,
            employee_id=employee_id,
            capability_hr_department_id=0,
            capability_work_type_id=max(0, int(cap_dept)),
            is_active=True,
        )
        db.session.add(row)
        try:
            db.session.commit()
            flash("已加入操作员白名单。", "success")
        except IntegrityError:
            db.session.rollback()
            flash("该员工已在白名单中。", "danger")
        return redirect(url_for("main.machine_detail", machine_id=machine_id))

    @bp.route("/machines/<int:machine_id>/operator-allowlist/<int:row_id>/delete", methods=["POST"])
    @login_required
    @menu_required("machine_asset")
    @capability_required("machine_asset.action.edit")
    def machine_operator_allowlist_delete(machine_id, row_id):
        row = MachineOperatorAllowlist.query.get_or_404(row_id)
        if int(row.machine_id) != int(machine_id):
            flash("数据不匹配。", "danger")
            return redirect(url_for("main.machine_list"))
        db.session.delete(row)
        db.session.commit()
        flash("已移除白名单。", "success")
        return redirect(url_for("main.machine_detail", machine_id=machine_id))

    @bp.route("/machines/<int:machine_id>/delete", methods=["POST"])
    @login_required
    @menu_required("machine_asset")
    @capability_required("machine_asset.action.delete")
    def machine_delete(machine_id):
        row = Machine.query.get_or_404(machine_id)
        if MachineRuntimeLog.query.filter_by(machine_id=machine_id).first():
            flash("该机台已有运转记录，不能删除。", "danger")
            return redirect(url_for("main.machine_list"))
        db.session.delete(row)
        db.session.commit()
        flash("机台已删除。", "success")
        return redirect(url_for("main.machine_list"))

    @bp.route("/machine-runtime")
    @login_required
    @menu_required("machine_runtime")
    def machine_runtime_list():
        machine_id = request.args.get("machine_id", type=int)
        runtime_status = (request.args.get("runtime_status") or "").strip()
        open_only = (request.args.get("open_only") or "").strip() == "1"
        q = MachineRuntimeLog.query
        if machine_id:
            q = q.filter(MachineRuntimeLog.machine_id == machine_id)
        if runtime_status in RUNTIME_STATUS:
            q = q.filter(MachineRuntimeLog.runtime_status == runtime_status)
        if open_only:
            q = q.filter(MachineRuntimeLog.ended_at.is_(None))
        rows = q.order_by(MachineRuntimeLog.started_at.desc(), MachineRuntimeLog.id.desc()).limit(200).all()
        machines = Machine.query.order_by(Machine.machine_no).all()
        return render_template(
            "machine/runtime_list.html",
            rows=rows,
            machines=machines,
            machine_id=machine_id,
            runtime_status=runtime_status,
            open_only=open_only,
            runtime_statuses=RUNTIME_STATUS,
        )

    @bp.route("/machine-runtime/new", methods=["GET", "POST"])
    @login_required
    @menu_required("machine_runtime")
    @capability_required("machine_runtime.action.create")
    def machine_runtime_new():
        machines = Machine.query.order_by(Machine.machine_no).all()
        if request.method == "POST":
            return _runtime_save(None, machines)
        return render_template("machine/runtime_form.html", row=None, machines=machines, runtime_statuses=RUNTIME_STATUS)

    @bp.route("/machine-runtime/<int:log_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("machine_runtime")
    @capability_required("machine_runtime.action.edit")
    def machine_runtime_edit(log_id):
        row = MachineRuntimeLog.query.get_or_404(log_id)
        machines = Machine.query.order_by(Machine.machine_no).all()
        if request.method == "POST":
            return _runtime_save(row, machines)
        return render_template("machine/runtime_form.html", row=row, machines=machines, runtime_statuses=RUNTIME_STATUS)

    def _runtime_save(row, machines):
        machine_id = request.form.get("machine_id", type=int)
        runtime_status = (request.form.get("runtime_status") or "").strip()
        started_at = _parse_dt(request.form.get("started_at"))
        ended_at = _parse_dt(request.form.get("ended_at"))
        remark = (request.form.get("remark") or "").strip() or None
        if not machine_id or runtime_status not in RUNTIME_STATUS or not started_at:
            flash("请完整填写机台、运转状态、开始时间。", "danger")
            return render_template("machine/runtime_form.html", row=row, machines=machines, runtime_statuses=RUNTIME_STATUS)
        machine = Machine.query.get(machine_id)
        if not machine:
            flash("机台不存在。", "danger")
            return render_template("machine/runtime_form.html", row=row, machines=machines, runtime_statuses=RUNTIME_STATUS)
        if machine.status == "scrapped" and runtime_status == "running":
            flash("报废机台不可设置为运行中。", "danger")
            return render_template("machine/runtime_form.html", row=row, machines=machines, runtime_statuses=RUNTIME_STATUS)
        if ended_at and ended_at < started_at:
            flash("结束时间不能早于开始时间。", "danger")
            return render_template("machine/runtime_form.html", row=row, machines=machines, runtime_statuses=RUNTIME_STATUS)
        open_q = MachineRuntimeLog.query.filter(
            MachineRuntimeLog.machine_id == machine_id, MachineRuntimeLog.ended_at.is_(None)
        )
        if row:
            open_q = open_q.filter(MachineRuntimeLog.id != row.id)
        if (not ended_at) and open_q.first():
            flash("同一机台同一时刻仅允许一条进行中记录。", "danger")
            return render_template("machine/runtime_form.html", row=row, machines=machines, runtime_statuses=RUNTIME_STATUS)
        if not row:
            row = MachineRuntimeLog(created_by=int(current_user.get_id()))
            db.session.add(row)
        row.machine_id = machine_id
        row.runtime_status = runtime_status
        row.started_at = started_at
        row.ended_at = ended_at
        row.remark = remark
        if row.created_by is None:
            row.created_by = int(current_user.get_id())
        db.session.commit()
        flash("运转记录已保存。", "success")
        return redirect(url_for("main.machine_runtime_list", machine_id=machine_id))

    @bp.route("/machine-runtime/<int:log_id>/close", methods=["POST"])
    @login_required
    @menu_required("machine_runtime")
    @capability_required("machine_runtime.action.close")
    def machine_runtime_close(log_id):
        row = MachineRuntimeLog.query.get_or_404(log_id)
        if row.ended_at:
            flash("该记录已结束。", "info")
            return redirect(url_for("main.machine_runtime_list", machine_id=row.machine_id))
        ended_at = _parse_dt(request.form.get("ended_at")) or datetime.now()
        if ended_at < row.started_at:
            flash("结束时间不能早于开始时间。", "danger")
            return redirect(url_for("main.machine_runtime_list", machine_id=row.machine_id))
        row.ended_at = ended_at
        db.session.commit()
        flash("运转记录已结束。", "success")
        return redirect(url_for("main.machine_runtime_list", machine_id=row.machine_id))

    # ----------------------------
    # 机台排班：模板（可重复）与时间窗（展开/手工）
    # ----------------------------

    @bp.route("/machine-schedule/templates")
    @login_required
    @menu_required("machine_schedule")
    def machine_schedule_template_list():
        machine_id = request.args.get("machine_id", type=int) or 0
        q = MachineScheduleTemplate.query
        if machine_id:
            q = q.filter(MachineScheduleTemplate.machine_id == machine_id)
        rows = q.order_by(MachineScheduleTemplate.id.desc()).limit(500).all()
        machines = Machine.query.order_by(Machine.machine_no).all()
        return render_template(
            "machine/machine_schedule_template_list.html",
            rows=rows,
            machines=machines,
            machine_id=machine_id,
            schedule_states=SCHEDULE_STATES,
        )

    @bp.route("/machine-schedule/templates/new", methods=["GET", "POST"])
    @login_required
    @menu_required("machine_schedule")
    @capability_required("machine_schedule_template.action.create")
    def machine_schedule_template_new():
        machines = Machine.query.order_by(Machine.machine_no).all()
        if request.method == "POST":
            return _machine_schedule_template_save(None, machines=machines)
        return render_template(
            "machine/machine_schedule_template_form.html",
            row=None,
            machines=machines,
            schedule_states=SCHEDULE_STATES,
            repeat_kinds=REPEAT_KINDS,
            dow_list=DAYS_OF_WEEK,
        )

    @bp.route("/machine-schedule/templates/<int:tpl_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("machine_schedule")
    @capability_required("machine_schedule_template.action.edit")
    def machine_schedule_template_edit(tpl_id: int):
        row = MachineScheduleTemplate.query.get_or_404(tpl_id)
        machines = Machine.query.order_by(Machine.machine_no).all()
        if request.method == "POST":
            return _machine_schedule_template_save(row, machines=machines)
        return render_template(
            "machine/machine_schedule_template_form.html",
            row=row,
            machines=machines,
            schedule_states=SCHEDULE_STATES,
            repeat_kinds=REPEAT_KINDS,
            dow_list=DAYS_OF_WEEK,
        )

    @bp.route("/machine-schedule/templates/<int:tpl_id>/delete", methods=["POST"])
    @login_required
    @menu_required("machine_schedule")
    @capability_required("machine_schedule_template.action.delete")
    def machine_schedule_template_delete(tpl_id: int):
        row = MachineScheduleTemplate.query.get_or_404(tpl_id)
        if MachineScheduleBooking.query.filter_by(template_id=row.id).first():
            flash("该模板已被展开生成时间窗，不能直接删除。", "danger")
            return redirect(url_for("main.machine_schedule_template_list", machine_id=row.machine_id))
        db.session.delete(row)
        db.session.commit()
        flash("排班模板已删除。", "success")
        return redirect(url_for("main.machine_schedule_template_list", machine_id=row.machine_id))

    def _machine_schedule_template_save(row: MachineScheduleTemplate | None, *, machines: list[Machine]) -> str:
        machine_id = request.form.get("machine_id", type=int) or 0
        name = (request.form.get("name") or "").strip()
        repeat_kind = (request.form.get("repeat_kind") or "").strip() or "weekly"
        days_of_week = request.form.getlist("days_of_week") or []
        valid_from = _parse_date(request.form.get("valid_from"))
        valid_to = _parse_date(request.form.get("valid_to"))
        start_time = _parse_time(request.form.get("start_time"))
        end_time = _parse_time(request.form.get("end_time"))
        state = (request.form.get("state") or "").strip()
        remark = (request.form.get("remark") or "").strip() or None

        if not machine_id or not name:
            flash("机台与模板名称为必填。", "danger")
            return redirect(url_for("main.machine_schedule_template_list"))
        if repeat_kind not in REPEAT_KINDS:
            flash("repeat_kind 非法。", "danger")
            return redirect(url_for("main.machine_schedule_template_list"))
        if state not in SCHEDULE_STATES:
            flash("排班状态非法。", "danger")
            return redirect(url_for("main.machine_schedule_template_list"))
        if not days_of_week:
            flash("至少选择一个星期。", "danger")
            return redirect(url_for("main.machine_schedule_template_list", machine_id=machine_id))
        if not valid_from or not start_time or not end_time:
            flash("有效期起始日期、开始时间、结束时间为必填。", "danger")
            return redirect(url_for("main.machine_schedule_template_list", machine_id=machine_id))

        machine = Machine.query.get(machine_id)
        if not machine:
            flash("机台不存在。", "danger")
            return redirect(url_for("main.machine_schedule_template_list", machine_id=machine_id))

        tpl_days_csv = ",".join(sorted(set(days_of_week)))

        if not row:
            row = MachineScheduleTemplate(created_by=int(current_user.get_id()))
            db.session.add(row)

        row.machine_id = machine_id
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
            return redirect(url_for("main.machine_schedule_template_list", machine_id=machine_id))

        flash("排班模板已保存。", "success")
        return redirect(url_for("main.machine_schedule_template_list", machine_id=machine_id))

    @bp.route("/machine-schedule/bookings")
    @login_required
    @menu_required("machine_schedule")
    def machine_schedule_booking_list():
        machine_id = request.args.get("machine_id", type=int) or 0
        date_from = _parse_date(request.args.get("date_from")) or date.today()
        date_to = _parse_date(request.args.get("date_to")) or (date.today() + timedelta(days=6))

        machines = Machine.query.order_by(Machine.machine_no).all()
        if not machine_id:
            rows = []
            return render_template(
                "machine/machine_schedule_booking_list.html",
                rows=rows,
                machines=machines,
                machine_id=machine_id,
                date_from=date_from,
                date_to=date_to,
                schedule_states=SCHEDULE_STATES,
            )

        try:
            generate_bookings_for_range(
                machine_id=machine_id,
                from_date=date_from,
                to_date=date_to,
                created_by=int(current_user.get_id()),
            )
        except ValueError as e:
            flash(str(e), "danger")

        start_dt = datetime.combine(date_from, time.min)
        end_dt = datetime.combine(date_to + timedelta(days=1), time.min)

        rows = (
            MachineScheduleBooking.query.filter(
                MachineScheduleBooking.machine_id == machine_id,
                MachineScheduleBooking.start_at < end_dt,
                MachineScheduleBooking.end_at > start_dt,
            )
            .order_by(MachineScheduleBooking.start_at.asc(), MachineScheduleBooking.id.asc())
            .limit(2000)
            .all()
        )

        return render_template(
            "machine/machine_schedule_booking_list.html",
            rows=rows,
            machines=machines,
            machine_id=machine_id,
            date_from=date_from,
            date_to=date_to,
            schedule_states=SCHEDULE_STATES,
        )

    @bp.route("/machine-schedule/bookings/new", methods=["GET", "POST"])
    @login_required
    @menu_required("machine_schedule")
    @capability_required("machine_schedule_booking.action.create")
    def machine_schedule_booking_new():
        machines = Machine.query.order_by(Machine.machine_no).all()
        machine_id = request.args.get("machine_id", type=int) or 0
        tpl_rows = MachineScheduleTemplate.query.filter(
            MachineScheduleTemplate.machine_id == machine_id
        ).order_by(MachineScheduleTemplate.id.asc()).all() if machine_id else []
        if request.method == "POST":
            return _machine_schedule_booking_save(None, machines=machines)
        return render_template(
            "machine/machine_schedule_booking_form.html",
            row=None,
            machines=machines,
            templates=tpl_rows,
            machine_id=machine_id,
            schedule_states=SCHEDULE_STATES,
        )

    @bp.route("/machine-schedule/bookings/<int:booking_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("machine_schedule")
    @capability_required("machine_schedule_booking.action.edit")
    def machine_schedule_booking_edit(booking_id: int):
        row = MachineScheduleBooking.query.get_or_404(booking_id)
        machines = Machine.query.order_by(Machine.machine_no).all()
        templates = (
            MachineScheduleTemplate.query.filter(
                MachineScheduleTemplate.machine_id == row.machine_id
            )
            .order_by(MachineScheduleTemplate.id.asc())
            .all()
        )
        if request.method == "POST":
            return _machine_schedule_booking_save(row, machines=machines)
        return render_template(
            "machine/machine_schedule_booking_form.html",
            row=row,
            machines=machines,
            templates=templates,
            machine_id=row.machine_id,
            schedule_states=SCHEDULE_STATES,
        )

    @bp.route("/machine-schedule/bookings/<int:booking_id>/delete", methods=["POST"])
    @login_required
    @menu_required("machine_schedule")
    @capability_required("machine_schedule_booking.action.delete")
    def machine_schedule_booking_delete(booking_id: int):
        row = MachineScheduleBooking.query.get_or_404(booking_id)
        db.session.delete(row)
        db.session.commit()
        flash("时间窗已删除。", "success")
        return redirect(url_for("main.machine_schedule_booking_list", machine_id=row.machine_id))

    def _machine_schedule_booking_save(
        row: MachineScheduleBooking | None,
        *,
        machines: list[Machine],
    ) -> str:
        machine_id = request.form.get("machine_id", type=int) or 0
        template_id = request.form.get("template_id", type=int) or 0
        start_at = _parse_dt(request.form.get("start_at"))
        end_at = _parse_dt(request.form.get("end_at"))
        state = (request.form.get("state") or "").strip()
        remark = (request.form.get("remark") or "").strip() or None

        if not machine_id or not template_id or state not in SCHEDULE_STATES or not start_at or not end_at:
            flash("机台、模板、开始/结束时间与状态为必填。", "danger")
            return redirect(url_for("main.machine_schedule_booking_list", machine_id=machine_id))
        if end_at <= start_at:
            flash("结束时间不能早于开始时间。", "danger")
            return redirect(url_for("main.machine_schedule_booking_list", machine_id=machine_id))

        template = MachineScheduleTemplate.query.get(template_id)
        if not template or template.machine_id != machine_id:
            flash("所选模板不属于当前机台。", "danger")
            return redirect(url_for("main.machine_schedule_booking_list", machine_id=machine_id))

        # 冲突校验：同机台任意 booking 不得重叠
        conflict_q = MachineScheduleBooking.query.filter(
            MachineScheduleBooking.machine_id == machine_id,
            MachineScheduleBooking.start_at < end_at,
            MachineScheduleBooking.end_at > start_at,
        )
        if row:
            conflict_q = conflict_q.filter(MachineScheduleBooking.id != row.id)
        if conflict_q.first():
            flash("保存失败：该时间窗与其它时间窗冲突。", "danger")
            return redirect(url_for("main.machine_schedule_booking_list", machine_id=machine_id))

        if not row:
            row = MachineScheduleBooking(created_by=int(current_user.get_id()))
            db.session.add(row)

        row.machine_id = machine_id
        row.template_id = template_id
        row.state = state
        row.start_at = start_at.replace(second=0, microsecond=0)
        row.end_at = end_at.replace(second=0, microsecond=0)
        row.remark = remark
        if row.created_by is None:
            row.created_by = int(current_user.get_id())

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("保存失败（可能存在重复约束）。", "danger")
            return redirect(url_for("main.machine_schedule_booking_list", machine_id=machine_id))

        flash("时间窗已保存。", "success")
        return redirect(url_for("main.machine_schedule_booking_list", machine_id=machine_id))
