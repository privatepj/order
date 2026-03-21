import calendar
import re
import zipfile
from datetime import date
from io import BytesIO

from flask import render_template, request, redirect, url_for, send_file, flash
from flask_login import login_required

from app.auth.decorators import menu_required
from sqlalchemy.orm import joinedload

from app.models import Customer, Company
from app.utils.reconciliation_excel import build_reconciliation_workbook
from app.utils.visibility import is_admin


def _dominant_month(s: date, e: date):
    y, m = s.year, s.month
    counts = {}
    while True:
        last = calendar.monthrange(y, m)[1]
        ms = date(y, m, 1)
        me = date(y, m, last)
        a = max(s, ms)
        b = min(e, me)
        if a <= b:
            counts[(y, m)] = (b - a).days + 1
        if y == e.year and m == e.month:
            break
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    end_key = (e.year, e.month)
    best_key = end_key
    best_days = -1
    for k, days in counts.items():
        if days > best_days:
            best_key = k
            best_days = days
        elif days == best_days and k == end_key:
            best_key = end_key
    return best_key


def _safe_filename_part(s: str, default: str = "X") -> str:
    t = re.sub(r'[<>:"/\\|?*\s]', "_", (s or "").strip()) or default
    return t[:32]


def _reconciliation_download_name(company: Company, customer: Customer, yy: int, mm: int) -> str:
    co = _safe_filename_part(company.code or company.name, "CO")
    cust = _safe_filename_part(
        customer.short_code or customer.customer_code, "C"
    )
    return f"{co}_{cust}_{yy:04d}{mm:02d}.xlsx"


def register_reconciliation_routes(bp):
    @bp.route("/reconciliation")
    @login_required
    @menu_required("reconciliation")
    def reconciliation_export():
        customers = Customer.query.order_by(Customer.customer_code).all()
        now = date.today()
        return render_template(
            "reconciliation/export.html",
            customers=customers,
            now=now,
        )

    @bp.route("/reconciliation/download")
    @login_required
    @menu_required("reconciliation")
    def reconciliation_download():
        customer_id = request.args.get("customer_id", type=int)
        start_s = (request.args.get("start_date") or "").strip()
        end_s = (request.args.get("end_date") or "").strip()
        if not start_s or not end_s:
            return redirect(url_for("main.reconciliation_export"))
        try:
            start = date.fromisoformat(start_s)
            end = date.fromisoformat(end_s)
        except ValueError:
            flash("日期格式不正确。", "danger")
            return redirect(url_for("main.reconciliation_export"))
        if start > end:
            flash("开始日期不能晚于结束日期。", "danger")
            return redirect(url_for("main.reconciliation_export"))

        yy, mm = _dominant_month(start, end)
        caption = f"{yy}年{mm}月份对帐单"
        admin = is_admin()

        if customer_id:
            customer = Customer.query.options(joinedload(Customer.company)).get_or_404(
                customer_id
            )
            company = customer.company or Company.query.get(customer.company_id)
            if not company:
                return redirect(url_for("main.reconciliation_export"))
            buf = build_reconciliation_workbook(
                customer=customer,
                company=company,
                start=start,
                end=end,
                period_caption=caption,
                show_amounts=admin,
            )
            filename = _reconciliation_download_name(company, customer, yy, mm)
            return send_file(
                buf,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=filename,
            )

        customers = (
            Customer.query.options(joinedload(Customer.company))
            .order_by(Customer.customer_code)
            .all()
        )
        zip_buf = BytesIO()
        used_names = set()
        count = 0
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for customer in customers:
                company = customer.company or Company.query.get(customer.company_id)
                if not company:
                    continue
                buf = build_reconciliation_workbook(
                    customer=customer,
                    company=company,
                    start=start,
                    end=end,
                    period_caption=caption,
                    show_amounts=admin,
                )
                inner = _reconciliation_download_name(company, customer, yy, mm)
                if inner in used_names:
                    base = inner.rsplit(".", 1)[0]
                    inner = f"{base}_{customer.id}.xlsx"
                used_names.add(inner)
                zf.writestr(inner, buf.getvalue())
                count += 1

        if count == 0:
            flash("没有可导出的客户（请维护客户与经营主体）。", "warning")
            return redirect(url_for("main.reconciliation_export"))

        zip_buf.seek(0)
        zip_name = f"对账批量_{yy:04d}{mm:02d}.zip"
        return send_file(
            zip_buf,
            mimetype="application/zip",
            as_attachment=True,
            download_name=zip_name,
        )
