from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required

from app import db
from app.auth.decorators import menu_required
from app.models import Company, Customer


def register_company_routes(bp):
    @bp.route("/companies")
    @login_required
    @menu_required("company")
    def company_list():
        companies = Company.query.order_by(Company.id).all()
        return render_template("company/list.html", companies=companies)

    @bp.route("/companies/new", methods=["GET", "POST"])
    @login_required
    @menu_required("company")
    def company_new():
        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            code = (request.form.get("code") or "").strip()
            if not name:
                flash("主体名称为必填。", "danger")
                return render_template("company/form.html", company=None)
            if not code:
                flash("短码为必填。", "danger")
                return render_template("company/form.html", company=None)
            other = Company.query.filter(Company.code == code).first()
            if other:
                flash("短码已存在。", "danger")
                return render_template("company/form.html", company=None)
            c = Company(name=name, code=code)
            prefix = (request.form.get("order_no_prefix") or "").strip()
            c.order_no_prefix = prefix or None
            dp = (request.form.get("delivery_no_prefix") or "").strip()
            c.delivery_no_prefix = dp or None
            day = request.form.get("billing_cycle_day", type=int)
            if day is None:
                day = 1
            c.billing_cycle_day = max(1, min(31, int(day)))
            c.phone = (request.form.get("phone") or "").strip() or None
            c.fax = (request.form.get("fax") or "").strip() or None
            c.address = (request.form.get("address") or "").strip() or None
            c.contact_person = (request.form.get("contact_person") or "").strip() or None
            c.private_account = (request.form.get("private_account") or "").strip() or None
            c.public_account = (request.form.get("public_account") or "").strip() or None
            c.account_name = (request.form.get("account_name") or "").strip() or None
            c.bank_name = (request.form.get("bank_name") or "").strip() or None
            c.preparer_name = (request.form.get("preparer_name") or "").strip() or None
            db.session.add(c)
            db.session.commit()
            flash("主体已新增。", "success")
            return redirect(url_for("main.company_list"))
        return render_template("company/form.html", company=None)

    @bp.route("/companies/<int:company_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("company")
    def company_edit(company_id):
        c = Company.query.get_or_404(company_id)
        if request.method == "POST":
            c.name = (request.form.get("name") or "").strip() or c.name
            code = (request.form.get("code") or "").strip()
            if code:
                other = Company.query.filter(Company.code == code, Company.id != c.id).first()
                if other:
                    flash("短码已存在。", "danger")
                    return render_template("company/form.html", company=c)
                c.code = code
            prefix = (request.form.get("order_no_prefix") or "").strip()
            c.order_no_prefix = prefix or None
            dp = (request.form.get("delivery_no_prefix") or "").strip()
            c.delivery_no_prefix = dp or None
            day = request.form.get("billing_cycle_day", type=int)
            if day is None:
                day = 1
            c.billing_cycle_day = max(1, min(31, int(day)))
            c.phone = (request.form.get("phone") or "").strip() or None
            c.fax = (request.form.get("fax") or "").strip() or None
            c.address = (request.form.get("address") or "").strip() or None
            c.contact_person = (request.form.get("contact_person") or "").strip() or None
            c.private_account = (request.form.get("private_account") or "").strip() or None
            c.public_account = (request.form.get("public_account") or "").strip() or None
            c.account_name = (request.form.get("account_name") or "").strip() or None
            c.bank_name = (request.form.get("bank_name") or "").strip() or None
            c.preparer_name = (request.form.get("preparer_name") or "").strip() or None
            db.session.commit()
            flash("已保存。", "success")
            return redirect(url_for("main.company_list"))
        return render_template("company/form.html", company=c)

    @bp.route("/companies/<int:company_id>/delete", methods=["POST"])
    @login_required
    @menu_required("company")
    def company_delete(company_id):
        c = Company.query.get_or_404(company_id)
        used = (
            db.session.query(db.func.count(Customer.id))
            .filter(Customer.company_id == c.id)
            .scalar()
        )
        if used and int(used) > 0:
            flash("该主体下已有客户，无法删除。", "danger")
            return redirect(url_for("main.company_list"))
        db.session.delete(c)
        db.session.commit()
        flash("主体已删除。", "success")
        return redirect(url_for("main.company_list"))
