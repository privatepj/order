from datetime import date
from decimal import Decimal

from flask import render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required

from app.auth.decorators import menu_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app import db
from app.models import (
    Customer,
    SalesOrder,
    OrderItem,
    Delivery,
    DeliveryItem,
    Company,
    ExpressCompany,
    ExpressWaybill,
    CustomerProduct,
    Product,
)
from app.utils.query import keyword_like_or
from app.utils.delivery_note_excel import (
    build_delivery_notes_workbook,
    ADDRESS_LINE,
    TEL_LINE,
    FOOT_NOTES,
    _qty_str,
)
from app.utils.delivery_records_excel import build_delivery_records_workbook
from app.utils.payment_type import PAYMENT_TYPE_LABELS, VALID_PAYMENT_TYPES
from app.services.delivery_svc import create_delivery_from_data
from app.services.order_svc import recompute_orders_status_for_delivery


def _express_companies_for_delivery():
    return (
        ExpressCompany.query.filter(ExpressCompany.is_active.is_(True))
        .filter(ExpressCompany.code != "LEGACY")
        .order_by(ExpressCompany.name)
        .all()
    )


def _peek_next_waybill_no(express_company_id: int):
    w = (
        db.session.query(ExpressWaybill.waybill_no)
        .filter(
            ExpressWaybill.express_company_id == express_company_id,
            ExpressWaybill.status == "available",
        )
        .order_by(ExpressWaybill.id)
        .limit(1)
        .scalar()
    )
    return w


def _pending_order_items(customer_id):
    """该客户下所有订单行及其已送数量，返回可选的 (order_item, order, delivered_qty, remaining_qty)。"""
    items = (
        db.session.query(OrderItem, SalesOrder)
        .join(SalesOrder, OrderItem.order_id == SalesOrder.id)
        .filter(SalesOrder.customer_id == customer_id)
        .order_by(SalesOrder.order_no, OrderItem.id)
        .all()
    )
    item_ids = [it.id for it, _ in items if it.id]
    if item_ids:
        qrows = (
            db.session.query(
                DeliveryItem.order_item_id,
                func.coalesce(func.sum(DeliveryItem.quantity), 0),
            )
            .join(Delivery, DeliveryItem.delivery_id == Delivery.id)
            .filter(
                Delivery.status == "shipped",
                DeliveryItem.order_item_id.in_(item_ids),
            )
            .group_by(DeliveryItem.order_item_id)
            .all()
        )
        delivered_map = {r[0]: float(r[1] or 0) for r in qrows}
    else:
        delivered_map = {}
    result = []
    for item, order in items:
        delivered = delivered_map.get(item.id, 0.0)
        need = float(item.quantity or 0)
        remaining = max(0, need - delivered)
        if remaining > 0:
            result.append(
                {
                    "order_item": item,
                    "order": order,
                    "delivered_qty": delivered,
                    "remaining_qty": remaining,
                }
            )
    return result


def _delivery_form_ctx(pending_items=None):
    return {
        "delivery": None,
        "express_companies": _express_companies_for_delivery(),
        "pending_items": pending_items or [],
        "today": date.today().isoformat(),
    }


def register_delivery_routes(bp):
    @bp.route("/deliveries")
    @login_required
    @menu_required("delivery")
    def delivery_list():
        page = request.args.get("page", 1, type=int)
        customer_id = request.args.get("customer_id", type=int)
        status = (request.args.get("status") or "").strip()
        keyword = (request.args.get("keyword") or "").strip()
        q = Delivery.query.options(
            joinedload(Delivery.customer).joinedload(Customer.company),
            joinedload(Delivery.express_company),
        )
        if customer_id:
            q = q.filter(Delivery.customer_id == customer_id)
        if status:
            q = q.filter(Delivery.status == status)
        if keyword:
            q = q.outerjoin(Customer, Delivery.customer_id == Customer.id)
            q = q.outerjoin(
                ExpressCompany, Delivery.express_company_id == ExpressCompany.id
            )
            cond = keyword_like_or(
                keyword,
                Delivery.delivery_no,
                Delivery.remark,
                Delivery.driver,
                Delivery.plate_no,
                Delivery.waybill_no,
                Customer.customer_code,
                Customer.name,
                ExpressCompany.name,
            )
            if cond is not None:
                q = q.filter(cond)
            q = q.distinct()
        q = q.order_by(Delivery.id.desc())
        pagination = q.paginate(page=page, per_page=20)
        customers = Customer.query.order_by(Customer.customer_code).all()
        companies = Company.query.order_by(Company.name).all()
        return render_template(
            "delivery/list.html",
            pagination=pagination,
            customers=customers,
            companies=companies,
            customer_id=customer_id,
            status=status,
            keyword=keyword,
            payment_type_labels=PAYMENT_TYPE_LABELS,
            export_today=date.today().isoformat(),
        )

    @bp.route("/report-export/delivery-notes", methods=["GET"])
    @login_required
    @menu_required("report_export")
    def report_export_delivery_notes():
        customers = Customer.query.order_by(Customer.customer_code).all()
        companies = Company.query.order_by(Company.name).all()
        return render_template(
            "report_export/delivery_notes_export.html",
            customers=customers,
            companies=companies,
            payment_type_labels=PAYMENT_TYPE_LABELS,
            export_today=date.today().isoformat(),
        )

    @bp.route("/report-export/delivery-records", methods=["GET"])
    @login_required
    @menu_required("report_export")
    def report_export_delivery_records():
        customers = Customer.query.order_by(Customer.customer_code).all()
        companies = Company.query.order_by(Company.name).all()
        return render_template(
            "report_export/delivery_records_export.html",
            customers=customers,
            companies=companies,
            payment_type_labels=PAYMENT_TYPE_LABELS,
            export_today=date.today().isoformat(),
        )

    @bp.route("/deliveries/export-delivery-notes")
    @login_required
    @menu_required("report_export")
    def delivery_export_notes():
        date_from_s = (request.args.get("delivery_date_from") or "").strip()
        date_to_s = (request.args.get("delivery_date_to") or "").strip()
        if not date_from_s or not date_to_s:
            flash("请选择送货日期起止。", "danger")
            return redirect(url_for("main.delivery_list"))
        try:
            d_from = date.fromisoformat(date_from_s)
            d_to = date.fromisoformat(date_to_s)
        except ValueError:
            flash("送货日期格式不正确。", "danger")
            return redirect(url_for("main.delivery_list"))
        if d_from > d_to:
            flash("起始日期不能晚于结束日期。", "danger")
            return redirect(url_for("main.delivery_list"))

        company_id = request.args.get("company_id", type=int)
        customer_id = request.args.get("export_customer_id", type=int)
        payment_type = (request.args.get("payment_type") or "").strip()

        q = Delivery.query.options(
            joinedload(Delivery.customer).joinedload(Customer.company)
        ).filter(
            Delivery.delivery_date >= d_from,
            Delivery.delivery_date <= d_to,
        )
        if company_id:
            q = q.join(Customer, Delivery.customer_id == Customer.id).filter(
                Customer.company_id == company_id
            )
        if customer_id:
            q = q.filter(Delivery.customer_id == customer_id)

        deliveries = q.order_by(Delivery.delivery_date, Delivery.id).all()

        if payment_type in VALID_PAYMENT_TYPES:
            wrong_ids = {
                r[0]
                for r in db.session.query(DeliveryItem.delivery_id)
                .join(SalesOrder, DeliveryItem.order_id == SalesOrder.id)
                .filter(SalesOrder.payment_type != payment_type)
                .distinct()
            }
            deliveries = [d for d in deliveries if d.id not in wrong_ids]

        bio = build_delivery_notes_workbook(deliveries)
        if bio is None:
            flash("没有符合条件的送货单可导出（或明细为空）。", "warning")
            return redirect(url_for("main.delivery_list"))

        fname = f"送货单_{d_from.strftime('%Y%m%d')}_{d_to.strftime('%Y%m%d')}.xlsx"
        return send_file(
            bio,
            as_attachment=True,
            download_name=fname,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @bp.route("/deliveries/export-delivery-records")
    @login_required
    @menu_required("report_export")
    def delivery_export_records():
        date_from_s = (request.args.get("delivery_date_from") or "").strip()
        date_to_s = (request.args.get("delivery_date_to") or "").strip()
        if not date_from_s or not date_to_s:
            flash("请选择送货日期起止。", "danger")
            return redirect(url_for("main.delivery_list"))
        try:
            d_from = date.fromisoformat(date_from_s)
            d_to = date.fromisoformat(date_to_s)
        except ValueError:
            flash("送货日期格式不正确。", "danger")
            return redirect(url_for("main.delivery_list"))
        if d_from > d_to:
            flash("起始日期不能晚于结束日期。", "danger")
            return redirect(url_for("main.delivery_list"))

        company_id = request.args.get("company_id", type=int)
        customer_id = request.args.get("export_customer_id", type=int)
        payment_type = (request.args.get("payment_type") or "").strip()
        pt_arg = payment_type if payment_type in VALID_PAYMENT_TYPES else None

        bio = build_delivery_records_workbook(
            d_from,
            d_to,
            company_id=company_id or None,
            customer_id=customer_id or None,
            payment_type=pt_arg,
        )
        if bio is None:
            flash("没有符合条件的送货记录。", "warning")
            return redirect(url_for("main.delivery_list"))

        fname = f"送货记录_{d_from.strftime('%Y%m%d')}_{d_to.strftime('%Y%m%d')}.xlsx"
        return send_file(
            bio,
            as_attachment=True,
            download_name=fname,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @bp.route("/deliveries/new", methods=["GET", "POST"])
    @login_required
    @menu_required("delivery")
    def delivery_new():
        if request.method == "POST":
            return _delivery_save()
        return render_template("delivery/form.html", **_delivery_form_ctx())

    @bp.route("/api/delivery/customers-search", methods=["GET"])
    @login_required
    @menu_required("delivery")
    def delivery_customers_search():
        qstr = (request.args.get("q") or "").strip()
        limit = request.args.get("limit", 50, type=int)
        limit = max(1, min(limit, 100))

        q = Customer.query.options(joinedload(Customer.company)).order_by(
            Customer.name
        )
        if qstr:
            like = f"%{qstr}%"
            q = (
                q.outerjoin(Company, Customer.company_id == Company.id)
                .filter(
                    db.or_(
                        Customer.name.like(like),
                        Company.code.like(like),
                    )
                )
            )

        items = []
        for c in q.limit(limit).all():
            co = c.company
            co_code = (co.code if co and co.code else "").strip()
            label = f"{co_code} - {c.name}" if co_code else c.name
            items.append({"id": c.id, "label": label})
        return jsonify({"items": items})

    @bp.route("/deliveries/<int:delivery_id>")
    @login_required
    @menu_required("delivery")
    def delivery_detail(delivery_id):
        delivery = Delivery.query.options(
            joinedload(Delivery.express_company)
        ).get_or_404(delivery_id)
        return render_template("delivery/detail.html", delivery=delivery)

    @bp.route("/deliveries/print")
    @login_required
    @menu_required("delivery")
    def delivery_print():
        delivery_id = request.args.get("delivery_id", type=int)
        if not delivery_id:
            flash("请指定送货单。", "danger")
            return redirect(url_for("main.delivery_list"))
        delivery = (
            Delivery.query.options(
                joinedload(Delivery.customer).joinedload(Customer.company),
                joinedload(Delivery.express_company),
            )
            .get_or_404(delivery_id)
        )
        items = (
            DeliveryItem.query.filter_by(delivery_id=delivery_id)
            .order_by(DeliveryItem.id)
            .options(
                joinedload(DeliveryItem.order_item).joinedload(
                    OrderItem.customer_product
                ).joinedload(CustomerProduct.product),
                joinedload(DeliveryItem.order_item).joinedload(OrderItem.order),
            )
            .all()
        )
        oi_map = {di.order_item_id: di.order_item for di in items if di.order_item}
        delivered_running = {}
        remaining_after = {}
        for di in items:
            oi = oi_map.get(di.order_item_id)
            if not oi:
                continue
            need = float(oi.quantity or 0)
            q = float(di.quantity or 0)
            delivered_running[oi.id] = delivered_running.get(oi.id, 0) + q
            remaining_after[di.id] = max(0.0, need - delivered_running[oi.id])

        rows = []
        for di in items:
            oi = oi_map.get(di.order_item_id)
            if not oi:
                continue
            so = oi.order
            product_code = None
            material_no = ""
            if oi.customer_product:
                material_no = (oi.customer_product.material_no or "").strip()
                if oi.customer_product.product:
                    product_code = oi.customer_product.product.product_code
            liao = product_code or (oi.customer_material_no or "").strip()
            name_spec = (
                " ".join(
                    x for x in (oi.product_name or "", oi.product_spec or "") if x
                ).strip()
                or (oi.product_name or "")
            )
            order_cell = (
                (so.customer_order_no or "").strip() if so else ""
            ) or ((so.order_no or "").strip() if so else "")
            rows.append(
                {
                    "liao": liao,
                    "material_no": material_no,
                    "name_spec": name_spec,
                    "order_qty_str": _qty_str(oi.quantity),
                    "ship_qty_str": _qty_str(di.quantity),
                    "remaining_str": _qty_str(remaining_after.get(di.id, 0)),
                    "unit": (di.unit or oi.unit or "").strip(),
                    "order_cell": order_cell,
                }
            )

        sign_line = "制单人：________________    仓库：________________    客户签收：________________"
        return render_template(
            "delivery/print.html",
            delivery=delivery,
            rows=rows,
            address_line=ADDRESS_LINE,
            tel_line=TEL_LINE,
            foot_notes=FOOT_NOTES,
            sign_line=sign_line,
        )

    @bp.route("/deliveries/<int:delivery_id>/delete", methods=["POST"])
    @login_required
    @menu_required("delivery")
    def delivery_delete(delivery_id):
        delivery = Delivery.query.get_or_404(delivery_id)
        flash("删除操作已禁用。", "warning")
        return redirect(url_for("main.delivery_list"))

    @bp.route("/deliveries/<int:delivery_id>/clear-waybill", methods=["POST"])
    @login_required
    @menu_required("delivery")
    def delivery_clear_waybill(delivery_id):
        delivery = Delivery.query.get_or_404(delivery_id)
        flash("清空快递单号操作已禁用；如需释放快递单号，请将该单标记为“失效”。", "warning")
        return redirect(url_for("main.delivery_detail", delivery_id=delivery.id))

    @bp.route("/deliveries/<int:delivery_id>/mark-shipped", methods=["POST"])
    @login_required
    @menu_required("delivery")
    def delivery_mark_shipped(delivery_id):
        delivery = Delivery.query.get_or_404(delivery_id)
        if delivery.status != "created":
            flash("该送货单不是待发状态。", "warning")
            return redirect(url_for("main.delivery_detail", delivery_id=delivery.id))
        delivery.status = "shipped"
        db.session.add(delivery)
        recompute_orders_status_for_delivery(delivery.id)
        db.session.commit()
        flash("已标记为已发。", "success")
        return redirect(url_for("main.delivery_detail", delivery_id=delivery.id))

    @bp.route("/deliveries/<int:delivery_id>/mark-created", methods=["POST"])
    @login_required
    @menu_required("delivery")
    def delivery_mark_created(delivery_id):
        delivery = Delivery.query.get_or_404(delivery_id)
        if delivery.status != "shipped":
            flash("仅已发状态允许回退。", "warning")
            return redirect(url_for("main.delivery_detail", delivery_id=delivery.id))
        delivery.status = "created"
        db.session.add(delivery)
        recompute_orders_status_for_delivery(delivery.id)
        db.session.commit()
        flash("已回退为待发。", "success")
        return redirect(url_for("main.delivery_detail", delivery_id=delivery.id))

    @bp.route("/deliveries/<int:delivery_id>/mark-expired", methods=["POST"])
    @login_required
    @menu_required("delivery")
    def delivery_mark_expired(delivery_id):
        delivery = Delivery.query.get_or_404(delivery_id)

        if delivery.status == "expired":
            flash("该送货单已处于失效状态。", "info")
            return redirect(url_for("main.delivery_detail", delivery_id=delivery.id))

        was_created = delivery.status == "created"
        delivery.status = "expired"

        # 仅在从“待发(created)”进入“失效(expired)”时释放占用的快递单号池。
        if was_created and delivery.express_waybill_id:
            w = ExpressWaybill.query.get(delivery.express_waybill_id)
            if w:
                w.status = "available"
                w.delivery_id = None
                w.used_at = None
                db.session.add(w)
            delivery.express_waybill_id = None
            delivery.waybill_no = None

        db.session.add(delivery)
        recompute_orders_status_for_delivery(delivery.id)
        db.session.commit()
        flash("送货单已标记为失效。", "success")
        return redirect(url_for("main.delivery_detail", delivery_id=delivery.id))

    @bp.route("/api/delivery/pending-items")
    @login_required
    @menu_required("delivery")
    def delivery_pending_items():
        customer_id = request.args.get("customer_id", type=int)
        if not customer_id:
            return jsonify({"items": []})
        items = _pending_order_items(customer_id)
        return jsonify({
            "items": [
                {
                    "order_item_id": x["order_item"].id,
                    "order_id": x["order"].id,
                    "order_no": x["order"].order_no,
                    "product_name": x["order_item"].product_name,
                    "product_spec": x["order_item"].product_spec or "",
                    "customer_material_no": x["order_item"].customer_material_no or "",
                    "quantity": float(x["order_item"].quantity),
                    "remaining_qty": x["remaining_qty"],
                    "unit": x["order_item"].unit or "",
                }
                for x in items
            ]
        })

    @bp.route("/api/delivery/next-waybill")
    @login_required
    @menu_required("delivery")
    def delivery_next_waybill():
        ec_id = request.args.get("express_company_id", type=int)
        if not ec_id:
            return jsonify({"waybill_no": None, "message": "请选择快递公司"})
        ec = ExpressCompany.query.get(ec_id)
        if not ec or ec.code == "LEGACY" or not ec.is_active:
            return jsonify({"waybill_no": None, "message": "无效的快递公司"})
        no = _peek_next_waybill_no(ec_id)
        return jsonify({"waybill_no": no, "message": None if no else "该公司暂无可用单号"})

    def _delivery_save():
        customer_id = request.form.get("customer_id", type=int)
        express_company_id = request.form.get("express_company_id", type=int)
        if not customer_id:
            flash("请选择客户。", "danger")
            return render_template("delivery/form.html", **_delivery_form_ctx())
        if not express_company_id:
            flash("请选择快递公司。", "danger")
            ctx = _delivery_form_ctx()
            ctx["pending_items"] = _pending_order_items(customer_id)
            return render_template("delivery/form.html", **ctx)
        order_item_ids = request.form.getlist("order_item_id")
        quantities = request.form.getlist("delivery_quantity")
        lines = []
        for i, oi_id in enumerate(order_item_ids):
            try:
                oi_id = int(oi_id)
            except (TypeError, ValueError):
                continue
            qty_str = quantities[i] if i < len(quantities) else "0"
            try:
                qty = float(Decimal(str(qty_str)))
            except Exception:
                qty = 0
            if oi_id and qty > 0:
                lines.append({"order_item_id": oi_id, "quantity": qty})
        data = {
            "customer_id": customer_id,
            "express_company_id": express_company_id if express_company_id else None,
            "delivery_date": request.form.get("delivery_date"),
            "driver": (request.form.get("driver") or "").strip() or None,
            "plate_no": (request.form.get("plate_no") or "").strip() or None,
            "remark": (request.form.get("remark") or "").strip() or None,
            "lines": lines,
        }
        delivery, err = create_delivery_from_data(data)
        if err:
            flash(err, "danger")
            ctx = _delivery_form_ctx()
            ctx["pending_items"] = _pending_order_items(customer_id) if customer_id else []
            return render_template("delivery/form.html", **ctx)
        flash("送货单已保存。", "success")
        return redirect(url_for("main.delivery_detail", delivery_id=delivery.id))
