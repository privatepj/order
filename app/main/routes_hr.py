from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from flask import render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app import db
from app.auth.capabilities import current_user_can_cap
from app.auth.decorators import capability_required, menu_required
from app.auth.menus import first_landing_url
from app.models import (
    AuditLog,
    Company,
    HrDepartment,
    HrEmployee,
    HrPayrollLine,
    HrPerformanceReview,
    User,
)
from app.utils.hr_privacy import display_id_card, display_phone


def _trunc(s, n):
    if s is None:
        return None
    s = str(s)
    if len(s) <= n:
        return s
    return s[: n - 3] + "..."


def _hr_audit(action: str, payload: dict):
    """关键 HR 操作写入 audit_log（event_type=hr）。"""
    from flask import has_request_context, request

    if not has_request_context():
        return
    uid = int(current_user.get_id()) if current_user.is_authenticated else None
    extra = {"action": action, **payload}
    row = AuditLog(
        event_type="hr",
        method=_trunc(request.method, 8),
        path=_trunc(request.path, 512),
        query_string=_trunc(
            request.query_string.decode("utf-8", errors="replace") if request.query_string else None,
            2048,
        ),
        status_code=None,
        duration_ms=None,
        user_id=uid,
        auth_type="session" if uid else "anonymous",
        ip=_trunc(request.remote_addr or "", 45) or "-",
        user_agent=_trunc(request.headers.get("User-Agent"), 512),
        endpoint=_trunc(request.endpoint or "", 128) if request.endpoint else None,
        extra=extra,
    )
    try:
        db.session.add(row)
        db.session.commit()
    except Exception:
        db.session.rollback()


def _companies():
    return Company.query.order_by(Company.id).all()


def _resolve_company_id():
    # HR/采购前端不再允许选择主体：一律使用默认主体（无则兜底取最小 id）
    companies = _companies()
    return Company.get_default_id(), companies


def _period_first_day(period: str) -> date | None:
    try:
        parts = (period or "").strip().split("-")
        if len(parts) != 2:
            return None
        return date(int(parts[0]), int(parts[1]), 1)
    except (ValueError, TypeError):
        return None


def register_hr_routes(bp):
    @bp.route("/hr-departments")
    @login_required
    @menu_required("hr_department")
    def hr_department_list():
        company_id, companies = _resolve_company_id()
        keyword = (request.args.get("keyword") or "").strip()
        if not current_user_can_cap("hr_department.filter.keyword"):
            keyword = ""
        q = HrDepartment.query
        if company_id:
            q = q.filter(HrDepartment.company_id == company_id)
        if keyword:
            q = q.filter(HrDepartment.name.contains(keyword))
        rows = q.order_by(HrDepartment.sort_order, HrDepartment.id).all()
        return render_template(
            "hr/department_list.html",
            rows=rows,
            companies=companies,
            company_id=company_id,
            keyword=keyword,
        )

    @bp.route("/hr-departments/new", methods=["GET", "POST"])
    @login_required
    @menu_required("hr_department")
    @capability_required("hr_department.action.create")
    def hr_department_new():
        companies = _companies()
        if not companies:
            flash("请先建立经营主体。", "danger")
            return redirect(url_for("main.hr_department_list"))
        if request.method == "POST":
            company_id = Company.get_default_id()
            name = (request.form.get("name") or "").strip()
            sort_order = request.form.get("sort_order", type=int) or 0
            if not company_id:
                flash("请先设置默认经营主体。", "danger")
                return render_template("hr/department_form.html", dept=None, companies=companies, company_id=None)
            if not name:
                flash("部门名称为必填。", "danger")
                return render_template("hr/department_form.html", dept=None, companies=companies, company_id=company_id)
            d = HrDepartment(company_id=company_id, name=name, sort_order=sort_order)
            db.session.add(d)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("同一主体下部门名称已存在。", "danger")
                return render_template("hr/department_form.html", dept=None, companies=companies, company_id=company_id)
            flash("部门已新增。", "success")
            return redirect(url_for("main.hr_department_list", company_id=company_id))
        return render_template("hr/department_form.html", dept=None, companies=companies, company_id=Company.get_default_id())

    @bp.route("/hr-departments/<int:dept_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("hr_department")
    @capability_required("hr_department.action.edit")
    def hr_department_edit(dept_id):
        d = HrDepartment.query.get_or_404(dept_id)
        companies = _companies()
        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            sort_order = request.form.get("sort_order", type=int) or 0
            company_id = d.company_id
            if not name:
                flash("部门名称为必填。", "danger")
                return render_template("hr/department_form.html", dept=d, companies=companies, company_id=company_id)
            d.name = name
            d.sort_order = sort_order
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("同一主体下部门名称已存在。", "danger")
                return render_template("hr/department_form.html", dept=d, companies=companies, company_id=company_id)
            flash("已保存。", "success")
            return redirect(url_for("main.hr_department_list", company_id=company_id))
        return render_template("hr/department_form.html", dept=d, companies=companies, company_id=d.company_id)

    @bp.route("/hr-departments/<int:dept_id>/delete", methods=["POST"])
    @login_required
    @menu_required("hr_department")
    @capability_required("hr_department.action.delete")
    def hr_department_delete(dept_id):
        d = HrDepartment.query.get_or_404(dept_id)
        cid = d.company_id
        used = HrEmployee.query.filter(HrEmployee.department_id == dept_id).first()
        if used:
            flash("该部门下仍有人员，无法删除。", "danger")
            return redirect(url_for("main.hr_department_list", company_id=cid))
        db.session.delete(d)
        db.session.commit()
        flash("部门已删除。", "success")
        return redirect(url_for("main.hr_department_list", company_id=cid))

    @bp.route("/hr-employees")
    @login_required
    @menu_required("hr_employee")
    def hr_employee_list():
        company_id, companies = _resolve_company_id()
        keyword = (request.args.get("keyword") or "").strip()
        if not current_user_can_cap("hr_employee.filter.keyword"):
            keyword = ""
        q = HrEmployee.query
        if company_id:
            q = q.filter(HrEmployee.company_id == company_id)
        if keyword:
            cond = or_(
                HrEmployee.name.contains(keyword),
                HrEmployee.employee_no.contains(keyword),
                HrEmployee.phone.contains(keyword),
            )
            q = q.filter(cond)
        rows = q.order_by(HrEmployee.company_id, HrEmployee.employee_no).all()
        sens = current_user_can_cap("hr_employee.view_sensitive")
        return render_template(
            "hr/employee_list.html",
            rows=rows,
            companies=companies,
            company_id=company_id,
            keyword=keyword,
            show_sensitive=sens,
            display_phone=display_phone,
            display_id_card=display_id_card,
        )

    @bp.route("/hr-employees/new", methods=["GET", "POST"])
    @login_required
    @menu_required("hr_employee")
    @capability_required("hr_employee.action.create")
    def hr_employee_new():
        companies = _companies()
        if not companies:
            flash("请先建立经营主体。", "danger")
            return redirect(url_for("main.hr_employee_list"))
        users = User.query.order_by(User.id).all()
        if request.method == "POST":
            return _hr_employee_save(None, companies, users)
        return _hr_employee_form(None, companies, users)

    @bp.route("/hr-employees/<int:emp_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("hr_employee")
    @capability_required("hr_employee.action.edit")
    def hr_employee_edit(emp_id):
        emp = HrEmployee.query.get_or_404(emp_id)
        companies = _companies()
        users = User.query.order_by(User.id).all()
        if request.method == "POST":
            return _hr_employee_save(emp, companies, users)
        return _hr_employee_form(emp, companies, users)

    @bp.route("/hr-employees/<int:emp_id>/delete", methods=["POST"])
    @login_required
    @menu_required("hr_employee")
    @capability_required("hr_employee.action.delete")
    def hr_employee_delete(emp_id):
        emp = HrEmployee.query.get_or_404(emp_id)
        cid = emp.company_id
        if HrPayrollLine.query.filter_by(employee_id=emp.id).first():
            flash("该人员已有工资记录，请先删除相关工资行后再删档案。", "danger")
            return redirect(url_for("main.hr_employee_list", company_id=cid))
        if HrPerformanceReview.query.filter_by(employee_id=emp.id).first():
            flash("该人员已有绩效记录，请先删除相关绩效后再删档案。", "danger")
            return redirect(url_for("main.hr_employee_list", company_id=cid))
        db.session.delete(emp)
        db.session.commit()
        flash("人员档案已删除。", "success")
        return redirect(url_for("main.hr_employee_list", company_id=cid))

    @bp.route("/hr-employees/export-import-template", methods=["GET"])
    @login_required
    @menu_required("hr_employee")
    @capability_required("hr_employee.action.export_template")
    def hr_employee_export_import_template():
        from openpyxl import Workbook

        headers = ["经营主体短码", "工号", "姓名", "部门名称", "手机", "身份证", "岗位", "入职日期", "状态"]
        wb = Workbook()
        ws = wb.active
        ws.title = "人员导入"
        for col, h in enumerate(headers, start=1):
            ws.cell(1, col, h)
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return send_file(
            buf,
            as_attachment=True,
            download_name="人员导入模板.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @bp.route("/hr-employees/import", methods=["GET", "POST"])
    @login_required
    @menu_required("hr_employee")
    @capability_required("hr_employee.action.import")
    def hr_employee_import():
        if request.method == "POST":
            file = request.files.get("file")
            if not file:
                flash("请先选择 Excel 文件。", "danger")
                return render_template("hr/employee_import.html", result=None)
            try:
                from openpyxl import load_workbook
            except ImportError:
                flash("服务器缺少 openpyxl 依赖，无法导入。", "danger")
                return render_template("hr/employee_import.html", result=None)
            try:
                wb = load_workbook(file, data_only=True)
                ws = wb.active
            except Exception:
                flash("Excel 无法读取。", "danger")
                return render_template("hr/employee_import.html", result=None)
            errors = []
            success = 0
            for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                (
                    code,
                    emp_no,
                    name,
                    dept_name,
                    phone,
                    id_card,
                    job_title,
                    hire_raw,
                    status,
                ) = (row + (None,) * 9)[:9]
                if not any(row):
                    continue
                code = (str(code).strip() if code is not None else "") or ""
                emp_no = (str(emp_no).strip() if emp_no is not None else "") or ""
                name = (str(name).strip() if name is not None else "") or ""
                if not code or not emp_no or not name:
                    errors.append(f"第 {idx} 行：经营主体短码、工号、姓名为必填")
                    continue
                comp = Company.query.filter_by(code=code).first()
                if not comp:
                    errors.append(f"第 {idx} 行：经营主体短码 {code} 不存在")
                    continue
                dept_id = None
                if dept_name:
                    dn = str(dept_name).strip()
                    dep = HrDepartment.query.filter_by(company_id=comp.id, name=dn).first()
                    if not dep:
                        errors.append(f"第 {idx} 行：部门「{dn}」不存在，请先在部门管理中维护")
                        continue
                    dept_id = dep.id
                st = (str(status).strip().lower() if status else "active") or "active"
                if st not in ("active", "left"):
                    st = "active"
                hire_date = None
                if hire_raw:
                    if isinstance(hire_raw, datetime):
                        hire_date = hire_raw.date()
                    else:
                        try:
                            hire_date = datetime.strptime(str(hire_raw).strip()[:10], "%Y-%m-%d").date()
                        except ValueError:
                            errors.append(f"第 {idx} 行：入职日期格式应为 YYYY-MM-DD")
                            continue
                emp = HrEmployee.query.filter_by(company_id=comp.id, employee_no=emp_no).first()
                if not emp:
                    emp = HrEmployee(company_id=comp.id, employee_no=emp_no)
                    db.session.add(emp)
                emp.name = name
                emp.department_id = dept_id
                emp.phone = (str(phone).strip() if phone else None) or None
                emp.id_card = (str(id_card).strip() if id_card else None) or None
                emp.job_title = (str(job_title).strip() if job_title else None) or None
                emp.hire_date = hire_date
                emp.status = st
                if st == "left" and not emp.leave_date:
                    emp.leave_date = date.today()
                success += 1
                db.session.flush()
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("导入失败：数据冲突（工号重复等）。", "danger")
                return render_template("hr/employee_import.html", result=None)
            _hr_audit("employee_import", {"success": success, "errors": len(errors)})
            return render_template(
                "hr/employee_import.html",
                result={"success": success, "errors": errors},
            )
        return render_template("hr/employee_import.html", result=None)

    def _hr_employee_form(emp, companies, users):
        sens = current_user_can_cap("hr_employee.view_sensitive")
        depts = []
        cid = emp.company_id if emp else Company.get_default_id()
        if cid:
            depts = HrDepartment.query.filter_by(company_id=cid).order_by(HrDepartment.sort_order).all()
        return render_template(
            "hr/employee_form.html",
            emp=emp,
            companies=companies,
            users=users,
            departments=depts,
            show_sensitive=sens,
            company_id=cid,
            default_company_id=cid,
        )

    def _hr_employee_save(emp, companies, users):
        company_id = emp.company_id if emp else Company.get_default_id()
        employee_no = (request.form.get("employee_no") or "").strip()
        name = (request.form.get("name") or "").strip()
        department_id = request.form.get("department_id", type=int) or None
        user_id = request.form.get("user_id", type=int) or None
        user_id = user_id if user_id else None
        phone = (request.form.get("phone") or "").strip() or None
        id_card = (request.form.get("id_card") or "").strip() or None
        job_title = (request.form.get("job_title") or "").strip() or None
        status = (request.form.get("status") or "active").strip()
        if status not in ("active", "left"):
            status = "active"
        hire_raw = (request.form.get("hire_date") or "").strip()
        leave_raw = (request.form.get("leave_date") or "").strip()
        remark = (request.form.get("remark") or "").strip() or None
        if not company_id:
            flash("请先设置默认经营主体。", "danger")
            return _hr_employee_form(emp, companies, users)
        if not employee_no or not name:
            flash("工号与姓名为必填。", "danger")
            return _hr_employee_form(emp, companies, users)
        if department_id:
            dep = HrDepartment.query.get(department_id)
            if not dep or dep.company_id != company_id:
                flash("部门与经营主体不匹配。", "danger")
                return _hr_employee_form(emp, companies, users)
        if user_id and not User.query.get(user_id):
            flash("所选用户不存在。", "danger")
            return _hr_employee_form(emp, companies, users)
        hire_date = None
        if hire_raw:
            try:
                hire_date = datetime.strptime(hire_raw[:10], "%Y-%m-%d").date()
            except ValueError:
                flash("入职日期格式错误。", "danger")
                return _hr_employee_form(emp, companies, users)
        leave_date = None
        if leave_raw:
            try:
                leave_date = datetime.strptime(leave_raw[:10], "%Y-%m-%d").date()
            except ValueError:
                flash("离职日期格式错误。", "danger")
                return _hr_employee_form(emp, companies, users)
        if not emp:
            emp = HrEmployee(company_id=company_id, employee_no=employee_no)
            db.session.add(emp)
        else:
            emp.company_id = company_id
            emp.employee_no = employee_no
        emp.name = name
        emp.department_id = department_id
        emp.user_id = user_id
        if current_user_can_cap("hr_employee.view_sensitive"):
            emp.phone = phone
            emp.id_card = id_card
        else:
            if phone or id_card:
                flash("无权限修改敏感字段，已保留原值。", "warning")
        emp.job_title = job_title
        emp.status = status
        emp.hire_date = hire_date
        emp.leave_date = leave_date
        emp.remark = remark
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("同一主体下工号已存在。", "danger")
            return _hr_employee_form(emp, companies, users)
        flash("已保存。", "success")
        return redirect(url_for("main.hr_employee_list", company_id=company_id))

    @bp.route("/hr-payroll")
    @login_required
    @menu_required("hr_payroll")
    def hr_payroll_list():
        if not current_user_can_cap("hr_payroll.view"):
            flash("无权限查看工资。", "danger")
            return redirect(first_landing_url())
        company_id, companies = _resolve_company_id()
        period = (request.args.get("period") or "").strip()
        if not period:
            period = date.today().strftime("%Y-%m")
        q = HrPayrollLine.query
        if company_id:
            q = q.filter(HrPayrollLine.company_id == company_id)
        q = q.filter(HrPayrollLine.period == period)
        rows = q.order_by(HrPayrollLine.id).all()
        return render_template(
            "hr/payroll_list.html",
            rows=rows,
            companies=companies,
            company_id=company_id,
            period=period,
        )

    @bp.route("/hr-payroll/new", methods=["GET", "POST"])
    @login_required
    @menu_required("hr_payroll")
    @capability_required("hr_payroll.edit")
    def hr_payroll_new():
        companies = _companies()
        company_id, _ = _resolve_company_id()
        if request.method == "POST":
            employee_id = request.form.get("employee_id", type=int)
            period = (request.form.get("period") or "").strip()
            base = Decimal(request.form.get("base_salary") or "0")
            allowance = Decimal(request.form.get("allowance") or "0")
            deduction = Decimal(request.form.get("deduction") or "0")
            remark = (request.form.get("remark") or "").strip() or None
            if not company_id or not employee_id or len(period) != 7:
                flash("请填写经营主体、员工与账期（YYYY-MM）。", "danger")
                return _payroll_form(None, companies, default_company_id=company_id)
            emp = HrEmployee.query.get(employee_id)
            if not emp or emp.company_id != company_id:
                flash("员工与主体不匹配。", "danger")
                return _payroll_form(None, companies, default_company_id=company_id)
            if emp.status == "left" and emp.leave_date:
                pf = _period_first_day(period)
                if pf and pf > emp.leave_date:
                    flash("该员工已离职，账期晚于离职日不可录入工资。", "danger")
                    return _payroll_form(None, companies, default_company_id=company_id)
            net = base + allowance - deduction
            row = HrPayrollLine(
                company_id=company_id,
                employee_id=employee_id,
                period=period,
                base_salary=base,
                allowance=allowance,
                deduction=deduction,
                net_pay=net,
                remark=remark,
                created_by=int(current_user.get_id()),
            )
            db.session.add(row)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("该员工该账期已有记录，请编辑原记录。", "danger")
                return _payroll_form(None, companies, default_company_id=company_id)
            _hr_audit(
                "payroll_create",
                {"company_id": company_id, "employee_id": employee_id, "period": period},
            )
            flash("工资已保存。", "success")
            return redirect(url_for("main.hr_payroll_list", company_id=company_id, period=period))
        return _payroll_form(
            None,
            companies,
            default_company_id=company_id,
            default_period=date.today().strftime("%Y-%m"),
        )

    @bp.route("/hr-payroll/<int:line_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("hr_payroll")
    @capability_required("hr_payroll.edit")
    def hr_payroll_edit(line_id):
        line = HrPayrollLine.query.get_or_404(line_id)
        companies = _companies()
        if request.method == "POST":
            base = Decimal(request.form.get("base_salary") or "0")
            allowance = Decimal(request.form.get("allowance") or "0")
            deduction = Decimal(request.form.get("deduction") or "0")
            remark = (request.form.get("remark") or "").strip() or None
            line.base_salary = base
            line.allowance = allowance
            line.deduction = deduction
            line.net_pay = base + allowance - deduction
            line.remark = remark
            db.session.commit()
            _hr_audit("payroll_edit", {"line_id": line_id, "period": line.period})
            flash("已保存。", "success")
            return redirect(
                url_for("main.hr_payroll_list", company_id=line.company_id, period=line.period)
            )
        return _payroll_form(line, companies)

    def _payroll_form(line, companies, default_company_id=None, default_period=None):
        cid = line.company_id if line else (default_company_id or (companies[0].id if companies else None))
        emps = []
        if cid:
            emps = HrEmployee.query.filter_by(company_id=cid).order_by(HrEmployee.employee_no).all()
        return render_template(
            "hr/payroll_form.html",
            line=line,
            companies=companies,
            employees=emps,
            default_company_id=cid,
            default_period=default_period or date.today().strftime("%Y-%m"),
        )

    @bp.route("/hr-payroll/export", methods=["GET"])
    @login_required
    @menu_required("hr_payroll")
    @capability_required("hr_payroll.export")
    def hr_payroll_export():
        company_id, _ = _resolve_company_id()
        period = (request.args.get("period") or "").strip() or date.today().strftime("%Y-%m")
        from openpyxl import Workbook

        q = HrPayrollLine.query.filter(HrPayrollLine.period == period)
        if company_id:
            q = q.filter(HrPayrollLine.company_id == company_id)
        rows = q.order_by(HrPayrollLine.id).all()
        wb = Workbook()
        ws = wb.active
        ws.title = "工资"
        ws.append(["账期", "主体ID", "工号", "姓名", "基本工资", "津贴", "扣款", "实发", "备注"])
        for r in rows:
            emp = r.employee
            ws.append(
                [
                    r.period,
                    r.company_id,
                    emp.employee_no if emp else "",
                    emp.name if emp else "",
                    float(r.base_salary),
                    float(r.allowance),
                    float(r.deduction),
                    float(r.net_pay),
                    r.remark or "",
                ]
            )
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return send_file(
            buf,
            as_attachment=True,
            download_name=f"工资导出_{period}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @bp.route("/hr-performance")
    @login_required
    @menu_required("hr_performance")
    def hr_performance_list():
        company_id, companies = _resolve_company_id()
        cycle = (request.args.get("cycle") or "").strip()
        q = HrPerformanceReview.query
        if company_id:
            q = q.filter(HrPerformanceReview.company_id == company_id)
        if cycle:
            q = q.filter(HrPerformanceReview.cycle == cycle)
        rows = q.order_by(HrPerformanceReview.cycle.desc(), HrPerformanceReview.id).all()
        return render_template(
            "hr/performance_list.html",
            rows=rows,
            companies=companies,
            company_id=company_id,
            cycle=cycle,
        )

    @bp.route("/hr-performance/new", methods=["GET", "POST"])
    @login_required
    @menu_required("hr_performance")
    @capability_required("hr_performance.action.create")
    def hr_performance_new():
        companies = _companies()
        company_id, _ = _resolve_company_id()
        if request.method == "POST":
            employee_id = request.form.get("employee_id", type=int)
            cycle = (request.form.get("cycle") or "").strip()
            score_raw = request.form.get("score")
            comment = (request.form.get("comment") or "").strip() or None
            if not company_id or not employee_id or not cycle:
                flash("请填写经营主体、员工与考核周期。", "danger")
                return _perf_form(None, companies)
            emp = HrEmployee.query.get(employee_id)
            if not emp or emp.company_id != company_id:
                flash("员工与主体不匹配。", "danger")
                return _perf_form(None, companies)
            score = None
            if score_raw not in (None, ""):
                try:
                    score = Decimal(str(score_raw))
                except Exception:
                    flash("评分格式错误。", "danger")
                    return _perf_form(None, companies)
            pr = HrPerformanceReview(
                company_id=company_id,
                employee_id=employee_id,
                cycle=cycle,
                score=score,
                comment=comment,
                reviewer_user_id=int(current_user.get_id()),
                status="draft",
            )
            db.session.add(pr)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("该员工该周期已有记录。", "danger")
                return _perf_form(None, companies)
            flash("已保存。", "success")
            return redirect(url_for("main.hr_performance_list", company_id=company_id, cycle=cycle))
        return _perf_form(None, companies, default_company_id=company_id)

    @bp.route("/hr-performance/<int:pr_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("hr_performance")
    def hr_performance_edit(pr_id):
        pr = HrPerformanceReview.query.get_or_404(pr_id)
        rc = getattr(current_user, "role_code", None)
        if pr.status == "finalized" and not current_user_can_cap("hr_performance.action.override") and rc != "admin":
            flash("已定稿，无权限修改。", "danger")
            return redirect(url_for("main.hr_performance_list", company_id=pr.company_id))
        if pr.status != "finalized" and not current_user_can_cap("hr_performance.action.edit") and rc != "admin":
            flash("无权限编辑。", "danger")
            return redirect(url_for("main.hr_performance_list", company_id=pr.company_id))
        companies = _companies()
        if request.method == "POST":
            score_raw = request.form.get("score")
            comment = (request.form.get("comment") or "").strip() or None
            score = None
            if score_raw not in (None, ""):
                try:
                    score = Decimal(str(score_raw))
                except Exception:
                    flash("评分格式错误。", "danger")
                    return _perf_form(pr, companies)
            pr.score = score
            pr.comment = comment
            pr.reviewer_user_id = int(current_user.get_id())
            db.session.commit()
            _hr_audit("performance_edit", {"id": pr_id, "cycle": pr.cycle})
            flash("已保存。", "success")
            return redirect(url_for("main.hr_performance_list", company_id=pr.company_id, cycle=pr.cycle))
        return _perf_form(pr, companies)

    @bp.route("/hr-performance/<int:pr_id>/delete", methods=["POST"])
    @login_required
    @menu_required("hr_performance")
    @capability_required("hr_performance.action.delete")
    def hr_performance_delete(pr_id):
        pr = HrPerformanceReview.query.get_or_404(pr_id)
        cid = pr.company_id
        cy = pr.cycle
        db.session.delete(pr)
        db.session.commit()
        flash("已删除。", "success")
        return redirect(url_for("main.hr_performance_list", company_id=cid, cycle=cy))

    @bp.route("/hr-performance/<int:pr_id>/finalize", methods=["POST"])
    @login_required
    @menu_required("hr_performance")
    @capability_required("hr_performance.action.finalize")
    def hr_performance_finalize(pr_id):
        pr = HrPerformanceReview.query.get_or_404(pr_id)
        if pr.status == "finalized":
            flash("已是定稿状态。", "info")
            return redirect(url_for("main.hr_performance_list", company_id=pr.company_id))
        pr.status = "finalized"
        pr.reviewer_user_id = int(current_user.get_id())
        db.session.commit()
        _hr_audit("performance_finalize", {"id": pr_id, "cycle": pr.cycle})
        flash("已定稿。", "success")
        return redirect(url_for("main.hr_performance_list", company_id=pr.company_id, cycle=pr.cycle))

    def _perf_form(pr, companies, default_company_id=None):
        cid = pr.company_id if pr else (default_company_id or (companies[0].id if companies else None))
        emps = []
        if cid:
            emps = HrEmployee.query.filter_by(company_id=cid).order_by(HrEmployee.employee_no).all()
        return render_template(
            "hr/performance_form.html",
            pr=pr,
            companies=companies,
            employees=emps,
            default_company_id=cid,
        )

    @bp.route("/hr/api/departments-by-company", methods=["GET"])
    @login_required
    @menu_required("hr_employee", "hr_payroll", "hr_performance")
    def hr_api_departments_by_company():
        """人员/工资/绩效表单联动：切换主体时加载部门与员工（简化：仅 JSON 部门供前端扩展）。"""
        cid = request.args.get("company_id", type=int)
        if not cid:
            return jsonify({"departments": []})
        depts = (
            HrDepartment.query.filter_by(company_id=cid)
            .order_by(HrDepartment.sort_order, HrDepartment.id)
            .all()
        )
        return jsonify({"departments": [{"id": d.id, "name": d.name} for d in depts]})
