from __future__ import annotations

from datetime import datetime

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app import db
from app.auth.capabilities import current_user_can_cap
from app.auth.decorators import capability_required, menu_required
from app.models import Machine, MachineRuntimeLog, MachineType, User


MACHINE_STATUS = ("enabled", "disabled", "maintenance", "scrapped")
RUNTIME_STATUS = ("running", "idle", "fault")


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
        if request.method == "POST":
            code = (request.form.get("code") or "").strip().upper()
            name = (request.form.get("name") or "").strip()
            is_active = (request.form.get("is_active") or "1") == "1"
            remark = (request.form.get("remark") or "").strip() or None
            if not code or not name:
                flash("种类编码和名称为必填。", "danger")
                return render_template("machine/type_form.html", row=None)
            row = MachineType(code=code, name=name, is_active=is_active, remark=remark)
            db.session.add(row)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("种类编码或名称重复。", "danger")
                return render_template("machine/type_form.html", row=None)
            flash("机台种类已新增。", "success")
            return redirect(url_for("main.machine_type_list"))
        return render_template("machine/type_form.html", row=None)

    @bp.route("/machine/types/<int:type_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("machine_type")
    @capability_required("machine_type.action.edit")
    def machine_type_edit(type_id):
        row = MachineType.query.get_or_404(type_id)
        if request.method == "POST":
            code = (request.form.get("code") or "").strip().upper()
            name = (request.form.get("name") or "").strip()
            is_active = (request.form.get("is_active") or "1") == "1"
            remark = (request.form.get("remark") or "").strip() or None
            if not code or not name:
                flash("种类编码和名称为必填。", "danger")
                return render_template("machine/type_form.html", row=row)
            row.code = code
            row.name = name
            row.is_active = is_active
            row.remark = remark
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("种类编码或名称重复。", "danger")
                return render_template("machine/type_form.html", row=row)
            flash("机台种类已更新。", "success")
            return redirect(url_for("main.machine_type_list"))
        return render_template("machine/type_form.html", row=row)

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
        if request.method == "POST":
            return _machine_save(None, types, users)
        return render_template("machine/machine_form.html", row=None, types=types, users=users, machine_statuses=MACHINE_STATUS)

    @bp.route("/machines/<int:machine_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("machine_asset")
    @capability_required("machine_asset.action.edit")
    def machine_edit(machine_id):
        row = Machine.query.get_or_404(machine_id)
        types = MachineType.query.order_by(MachineType.name).all()
        users = User.query.order_by(User.id).all()
        if request.method == "POST":
            return _machine_save(row, types, users)
        return render_template("machine/machine_form.html", row=row, types=types, users=users, machine_statuses=MACHINE_STATUS)

    def _machine_save(row, types, users):
        machine_no = (request.form.get("machine_no") or "").strip().upper()
        name = (request.form.get("name") or "").strip()
        machine_type_id = request.form.get("machine_type_id", type=int)
        status = (request.form.get("status") or "enabled").strip()
        location = (request.form.get("location") or "").strip() or None
        owner_user_id = request.form.get("owner_user_id", type=int) or None
        remark = (request.form.get("remark") or "").strip() or None
        try:
            capacity_per_hour = float((request.form.get("capacity_per_hour") or "0").strip())
        except ValueError:
            flash("标准产能格式不正确。", "danger")
            return render_template("machine/machine_form.html", row=row, types=types, users=users, machine_statuses=MACHINE_STATUS)
        if not machine_no or not name or not machine_type_id:
            flash("机台编号、名称、种类为必填。", "danger")
            return render_template("machine/machine_form.html", row=row, types=types, users=users, machine_statuses=MACHINE_STATUS)
        if status not in MACHINE_STATUS:
            status = "enabled"
        mt = MachineType.query.get(machine_type_id)
        if not mt:
            flash("机台种类不存在。", "danger")
            return render_template("machine/machine_form.html", row=row, types=types, users=users, machine_statuses=MACHINE_STATUS)
        if owner_user_id and not User.query.get(owner_user_id):
            flash("责任人不存在。", "danger")
            return render_template("machine/machine_form.html", row=row, types=types, users=users, machine_statuses=MACHINE_STATUS)
        if capacity_per_hour < 0:
            flash("标准产能不能为负数。", "danger")
            return render_template("machine/machine_form.html", row=row, types=types, users=users, machine_statuses=MACHINE_STATUS)
        if not row:
            row = Machine(machine_no=machine_no)
            db.session.add(row)
        row.machine_no = machine_no
        row.name = name
        row.machine_type_id = machine_type_id
        row.capacity_per_hour = capacity_per_hour
        row.status = status
        row.location = location
        row.owner_user_id = owner_user_id
        row.remark = remark
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("机台编号重复。", "danger")
            return render_template("machine/machine_form.html", row=row, types=types, users=users, machine_statuses=MACHINE_STATUS)
        flash("机台信息已保存。", "success")
        return redirect(url_for("main.machine_list"))

    @bp.route("/machines/<int:machine_id>")
    @login_required
    @menu_required("machine_asset")
    def machine_detail(machine_id):
        row = Machine.query.get_or_404(machine_id)
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
        return render_template("machine/machine_detail.html", row=row, open_log=open_log, latest_logs=latest_logs)

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
