from datetime import date
from decimal import Decimal

from flask import render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required

from app.auth.capabilities import current_user_can_cap, order_list_read_filters
from app.auth.decorators import capability_required, menu_required
from sqlalchemy.orm import joinedload

from app import db
from app.models import (
    Customer,
    Company,
    SalesOrder,
    OrderItem,
    DeliveryItem,
    CustomerProduct,
    Product,
)
from app.utils.query import is_valid_customer_search_keyword, keyword_like_or
from app.utils.visibility import is_admin, order_item_view
from app.utils.payment_type import PAYMENT_TYPE_LABELS
from app.services.order_svc import create_order_from_data
from app.services.delivery_svc import order_item_shipped_and_in_transit_maps


def _order_item_ids_with_delivery(order_id):
    if not order_id:
        return set()
    rows = (
        db.session.query(DeliveryItem.order_item_id)
        .join(OrderItem, DeliveryItem.order_item_id == OrderItem.id)
        .filter(OrderItem.order_id == order_id)
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


def _load_cp_for_order(customer_id, cp_id):
    if not cp_id:
        return None, None
    cp = (
        CustomerProduct.query.filter_by(id=cp_id, customer_id=customer_id)
        .options(joinedload(CustomerProduct.product))
        .first()
    )
    if not cp or not cp.product:
        return None, None
    return cp, cp.product


def register_order_routes(bp):
    @bp.route("/orders")
    @login_required
    @menu_required("order")
    def order_list():
        page, customer_id, status, payment_type, keyword = order_list_read_filters()
        q = SalesOrder.query.options(
            joinedload(SalesOrder.customer).joinedload(Customer.company)
        )
        if customer_id:
            q = q.filter(SalesOrder.customer_id == customer_id)
        if status:
            q = q.filter(SalesOrder.status == status)
        if payment_type:
            q = q.filter(SalesOrder.payment_type == payment_type)
        if keyword:
            q = q.outerjoin(Customer, SalesOrder.customer_id == Customer.id)
            cond = keyword_like_or(
                keyword,
                SalesOrder.order_no,
                SalesOrder.customer_order_no,
                SalesOrder.remark,
                Customer.customer_code,
                Customer.name,
            )
            if cond is not None:
                q = q.filter(cond)
            q = q.distinct()
        q = q.order_by(SalesOrder.id.desc())
        pagination = q.paginate(page=page, per_page=20)
        customers = Customer.query.order_by(Customer.customer_code).all()
        return render_template(
            "order/list.html",
            pagination=pagination,
            customers=customers,
            customer_id=customer_id,
            status=status,
            payment_type=payment_type,
            payment_type_labels=PAYMENT_TYPE_LABELS,
            keyword=keyword,
        )

    @bp.route("/orders/new", methods=["GET", "POST"])
    @login_required
    @menu_required("order")
    @capability_required("order.action.create")
    def order_new():
        if request.method == "POST":
            return _order_save(None)
        customers = Customer.query.order_by(Customer.customer_code).all()
        from datetime import date as date_mod

        return render_template(
            "order/form.html",
            order=None,
            customers=customers,
            is_admin=is_admin(),
            today_order_date=date_mod.today().isoformat(),
            locked_item_ids=set(),
            payment_type_labels=PAYMENT_TYPE_LABELS,
        )

    @bp.route("/orders/<int:order_id>")
    @login_required
    @menu_required("order")
    def order_detail(order_id):
        order = (
            SalesOrder.query.options(
                joinedload(SalesOrder.items)
                .joinedload(OrderItem.customer_product)
                .joinedload(CustomerProduct.product)
            )
            .get_or_404(order_id)
        )
        item_ids = [it.id for it in order.items if it.id]
        shipped_map, in_transit_map = order_item_shipped_and_in_transit_maps(item_ids)
        rows = []
        for item in order.items:
            shipped = shipped_map.get(item.id, 0.0)
            in_transit = in_transit_map.get(item.id, 0.0)
            need = float(item.quantity or 0)
            allocated = shipped + in_transit
            remaining = max(0, need - allocated)
            rows.append(
                {
                    "item": order_item_view(item),
                    "delivered_qty": shipped,
                    "in_transit_qty": in_transit,
                    "remaining_qty": remaining,
                }
            )
        return render_template(
            "order/detail.html",
            order=order,
            rows=rows,
            is_admin=is_admin(),
            payment_type_labels=PAYMENT_TYPE_LABELS,
        )

    @bp.route("/orders/<int:order_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("order")
    @capability_required("order.action.edit")
    def order_edit(order_id):
        order = (
            SalesOrder.query.options(
                joinedload(SalesOrder.items)
                .joinedload(OrderItem.customer_product)
                .joinedload(CustomerProduct.product)
            )
            .get_or_404(order_id)
        )
        if request.method == "POST":
            return _order_save(order)
        customers = Customer.query.order_by(Customer.customer_code).all()
        locked = _order_item_ids_with_delivery(order.id)
        return render_template(
            "order/form.html",
            order=order,
            customers=customers,
            is_admin=is_admin(),
            today_order_date=None,
            locked_item_ids=locked,
            payment_type_labels=PAYMENT_TYPE_LABELS,
        )

    @bp.route("/orders/<int:order_id>/delete", methods=["POST"])
    @login_required
    @menu_required("order")
    @capability_required("order.action.delete")
    def order_delete(order_id):
        order = SalesOrder.query.get_or_404(order_id)
        # 订单一旦存在送货明细（delivery_item），删除会触发 SQLAlchemy 把关联的 order_item_id 置空，
        # 但 delivery_item.order_item_id 在库是 NOT NULL，因此会产生 IntegrityError。
        # 业务口径：有送货单明细则禁止删除。
        delivery_item_oi_ids = _order_item_ids_with_delivery(order.id)
        if delivery_item_oi_ids:
            flash("该订单已创建送货单，禁止删除。", "danger")
            return redirect(url_for("main.order_list"))
        db.session.delete(order)
        db.session.commit()
        flash("订单已删除。", "success")
        return redirect(url_for("main.order_list"))

    def _order_save(order):
        customer_id = request.form.get("customer_id", type=int)
        order_item_ids = request.form.getlist("order_item_id")
        customer_product_ids = request.form.getlist("customer_product_id")
        quantities = request.form.getlist("quantity")
        is_samples = request.form.getlist("is_sample")
        is_spares = request.form.getlist("is_spare")
        n_rows = max(
            len(customer_product_ids),
            len(quantities),
            len(order_item_ids),
            len(is_samples),
            len(is_spares),
        )

        def _row_cp_qty_sample(i):
            cp_s = customer_product_ids[i] if i < len(customer_product_ids) else ""
            q_s = quantities[i] if i < len(quantities) else "0"
            s_s = is_samples[i] if i < len(is_samples) else "0"
            sp_s = is_spares[i] if i < len(is_spares) else "0"
            try:
                cp_id = int(cp_s) if str(cp_s).strip() else None
            except (TypeError, ValueError):
                cp_id = None
            try:
                qty = Decimal(str(q_s))
            except Exception:
                qty = Decimal(0)
            try:
                is_sample = int(str(s_s).strip() or "0") == 1
            except Exception:
                is_sample = False
            try:
                is_spare = int(str(sp_s).strip() or "0") == 1
            except Exception:
                is_spare = False
            oi_id = None
            if i < len(order_item_ids) and order_item_ids[i] and str(order_item_ids[i]).strip():
                try:
                    oi_id = int(order_item_ids[i])
                except (TypeError, ValueError):
                    pass
            return cp_id, qty, is_sample, is_spare, oi_id

        items = []
        for i in range(n_rows):
            cp_id, qty, is_sample, is_spare, oi_id = _row_cp_qty_sample(i)
            items.append({
                "customer_product_id": cp_id,
                "quantity": float(qty),
                "is_sample": is_sample,
                "is_spare": is_spare,
                "order_item_id": oi_id,
            })

        data = {
            "customer_id": customer_id,
            "customer_order_no": (request.form.get("customer_order_no") or "").strip() or None,
            "salesperson": (request.form.get("salesperson") or "GaoMeiHua").strip(),
            "order_date": request.form.get("order_date"),
            "required_date": request.form.get("required_date"),
            "remark": (request.form.get("remark") or "").strip() or None,
            "payment_type": request.form.get("payment_type"),
            "items": items,
        }
        saved_order, err = create_order_from_data(data, order)
        if err:
            flash(err, "danger")
            admin = is_admin()
            today_def = date.today().isoformat()
            customers = Customer.query.order_by(Customer.customer_code).all()
            lid = _order_item_ids_with_delivery(order.id) if order and order.id else set()
            return render_template(
                "order/form.html",
                order=order,
                customers=customers,
                is_admin=admin,
                today_order_date=today_def if not (order and order.id) else None,
                locked_item_ids=lid,
                payment_type_labels=PAYMENT_TYPE_LABELS,
            )
        flash("订单已保存。", "success")
        return redirect(url_for("main.order_detail", order_id=saved_order.id))

    @bp.route("/api/customer-products-for-order")
    @login_required
    @menu_required("order", "customer_product")
    def customer_products_for_order():
        if not (
            current_user_can_cap("order.action.create")
            or current_user_can_cap("order.action.edit")
        ):
            abort(403)
        customer_id = request.args.get("customer_id", type=int)
        qstr = (request.args.get("q") or "").strip()
        limit = request.args.get("limit", 20, type=int)
        limit = max(1, min(limit, 20))
        if not customer_id:
            return jsonify({"items": []})
        q = (
            db.session.query(CustomerProduct, Product)
            .join(Product, CustomerProduct.product_id == Product.id)
            .filter(CustomerProduct.customer_id == customer_id)
        )
        if qstr:
            like = f"%{qstr}%"
            q = q.filter(
                db.or_(
                    Product.name.like(like),
                    Product.spec.like(like),
                    Product.product_code.like(like),
                    CustomerProduct.customer_material_no.like(like),
                )
            )
        q = q.order_by(Product.product_code).limit(limit)
        items = []
        for cp, p in q.all():
            row = {
                "id": cp.id,
                "product_code": p.product_code,
                "product_name": p.name,
                "product_spec": p.spec or "",
                "customer_material_no": cp.customer_material_no or "",
                "material_no": p.product_code or "",
                "unit": cp.unit or (p.base_unit or ""),
                "price": float(cp.price) if cp.price is not None else None,
            }
            items.append(row)
        return jsonify({"items": items})

    @bp.route("/api/orders/customers-search", methods=["GET"])
    @login_required
    @menu_required("order")
    def orders_customers_search():
        if not (
            current_user_can_cap("order.action.create")
            or current_user_can_cap("order.action.edit")
        ):
            abort(403)
        qstr = (request.args.get("q") or "").strip()
        limit = request.args.get("limit", 20, type=int)
        limit = max(1, min(limit, 20))

        if not is_valid_customer_search_keyword(qstr):
            return jsonify({"items": []})

        like = f"%{qstr}%"
        q = (
            Customer.query.options(joinedload(Customer.company))
            .outerjoin(Company, Customer.company_id == Company.id)
            .filter(db.or_(Customer.name.like(like), Company.code.like(like)))
            .order_by(Customer.name)
        )

        items = []
        for c in q.limit(limit).all():
            co_code = (c.company.code if c.company and c.company.code else "").strip()
            label = f"{co_code} - {c.name}" if co_code else c.name
            items.append({"id": c.id, "label": label})
        return jsonify({"items": items})

    @bp.route("/api/customer-product-for-order/<int:cp_id>")
    @login_required
    @menu_required("order", "customer_product")
    def customer_product_one_for_order(cp_id):
        if not (
            current_user_can_cap("order.action.create")
            or current_user_can_cap("order.action.edit")
        ):
            abort(403)
        customer_id = request.args.get("customer_id", type=int)
        if not customer_id:
            return jsonify({})
        cp, p = _load_cp_for_order(customer_id, cp_id)
        if not cp or not p:
            return jsonify({})
        return jsonify(
            {
                "id": cp.id,
                "product_code": p.product_code,
                "product_name": p.name,
                "product_spec": p.spec or "",
                "customer_material_no": cp.customer_material_no or "",
                "material_no": p.product_code or "",
                "unit": cp.unit or (p.base_unit or ""),
                "price": float(cp.price) if cp.price is not None else None,
            }
        )
