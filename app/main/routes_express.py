from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy import func

from app import db
from app.auth.decorators import menu_required
from app.models import ExpressCompany, ExpressWaybill
from app.utils.waybill_range import expand_waybill_range


def register_express_routes(bp):
    @bp.route("/express-companies")
    @login_required
    @menu_required("express")
    def express_company_list():
        companies = ExpressCompany.query.order_by(ExpressCompany.id).all()
        stats = {}
        for c in companies:
            av = (
                db.session.query(func.count(ExpressWaybill.id))
                .filter(
                    ExpressWaybill.express_company_id == c.id,
                    ExpressWaybill.status == "available",
                )
                .scalar()
                or 0
            )
            us = (
                db.session.query(func.count(ExpressWaybill.id))
                .filter(
                    ExpressWaybill.express_company_id == c.id,
                    ExpressWaybill.status == "used",
                )
                .scalar()
                or 0
            )
            stats[c.id] = {"available": av, "used": us}
        return render_template(
            "express/company_list.html", companies=companies, stats=stats
        )

    @bp.route("/express-companies/new", methods=["GET", "POST"])
    @login_required
    @menu_required("express")
    def express_company_new():
        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            code = (request.form.get("code") or "").strip().upper()
            if not name or not code:
                flash("请填写名称与短码。", "danger")
                return render_template("express/company_form.html", company=None)
            if ExpressCompany.query.filter_by(code=code).first():
                flash("短码已存在。", "danger")
                return render_template("express/company_form.html", company=None)
            c = ExpressCompany(name=name, code=code, is_active=True)
            db.session.add(c)
            db.session.commit()
            flash("已添加快递公司。", "success")
            return redirect(url_for("main.express_company_list"))
        return render_template("express/company_form.html", company=None)

    @bp.route("/express-companies/<int:cid>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("express")
    def express_company_edit(cid):
        c = ExpressCompany.query.get_or_404(cid)
        if request.method == "POST":
            c.name = (request.form.get("name") or "").strip() or c.name
            code = (request.form.get("code") or "").strip().upper()
            if code:
                other = ExpressCompany.query.filter(
                    ExpressCompany.code == code, ExpressCompany.id != c.id
                ).first()
                if other:
                    flash("短码已存在。", "danger")
                    return render_template("express/company_form.html", company=c)
                c.code = code
            c.is_active = request.form.get("is_active") == "1"
            db.session.commit()
            flash("已保存。", "success")
            return redirect(url_for("main.express_company_list"))
        return render_template("express/company_form.html", company=c)

    @bp.route("/express-waybills/import", methods=["GET", "POST"])
    @login_required
    @menu_required("express")
    def express_waybill_import():
        companies = (
            ExpressCompany.query.filter(ExpressCompany.is_active.is_(True))
            .filter(ExpressCompany.code != "LEGACY")
            .order_by(ExpressCompany.name)
            .all()
        )
        if not companies:
            flash("请先添加快递公司。", "warning")
            return redirect(url_for("main.express_company_new"))

        if request.method == "POST":
            ec_id = request.form.get("express_company_id", type=int)
            start = (request.form.get("waybill_start") or "").strip()
            end = (request.form.get("waybill_end") or "").strip()
            if not ec_id:
                flash("请选择快递公司。", "danger")
                return render_template(
                    "express/waybill_import.html", companies=companies
                )
            ec = ExpressCompany.query.get(ec_id)
            if not ec or ec.code == "LEGACY":
                flash("无效的快递公司。", "danger")
                return render_template(
                    "express/waybill_import.html", companies=companies
                )
            try:
                numbers = expand_waybill_range(start, end)
            except ValueError as e:
                flash(str(e), "danger")
                return render_template(
                    "express/waybill_import.html", companies=companies
                )
            inserted = 0
            skipped = 0
            for no in numbers:
                exists = (
                    db.session.query(ExpressWaybill.id)
                    .filter_by(express_company_id=ec_id, waybill_no=no)
                    .first()
                )
                if exists:
                    skipped += 1
                    continue
                db.session.add(
                    ExpressWaybill(
                        express_company_id=ec_id,
                        waybill_no=no,
                        status="available",
                    )
                )
                inserted += 1
            db.session.commit()
            flash(
                f"录入完成：新增 {inserted} 条，跳过（已存在）{skipped} 条。",
                "success",
            )
            return redirect(url_for("main.express_waybill_import"))

        return render_template("express/waybill_import.html", companies=companies)
