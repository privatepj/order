"""OpenClaw 专用 API 路由：JSON 入参/出参，API Key 鉴权，客户信息仅返回简称。"""
from flask import request, jsonify

from app import db
from app.models import Customer, CustomerProduct, Product
from app.auth.api_key_auth import require_api_key
from app.services.order_svc import create_order_from_data
from app.services.delivery_svc import (
    create_delivery_from_data,
    get_pending_order_items,
)

from app.openclaw import bp


def _customer_display_label(c: Customer) -> str:
    """对外仅展示简称，不暴露完整客户名。"""
    return (c.short_code or c.customer_code or "").strip() or str(c.id)


@bp.route("/customers", methods=["GET"])
@require_api_key
def customers():
    """客户列表：仅返回 id 与简称（short_code/customer_code），供解析与选择。q= 搜索简称/编码。"""
    q_str = (request.args.get("q") or "").strip()
    limit = min(max(request.args.get("limit", 20, type=int), 1), 100)
    q = Customer.query.order_by(Customer.customer_code)
    if q_str:
        like = f"%{q_str}%"
        q = q.filter(
            db.or_(
                Customer.short_code.like(like),
                Customer.customer_code.like(like),
            )
        )
    rows = q.limit(limit).all()
    return jsonify({
        "items": [
            {"id": c.id, "label": _customer_display_label(c)}
            for c in rows
        ]
    })


@bp.route("/customer-products", methods=["GET"])
@require_api_key
def customer_products():
    """客户产品列表：供解析产品用，仅返回编码/简称级别信息。"""
    customer_id = request.args.get("customer_id", type=int)
    q_str = (request.args.get("q") or "").strip()
    limit = min(max(request.args.get("limit", 50, type=int), 1), 100)
    if not customer_id:
        return jsonify({"items": []})
    q = (
        db.session.query(CustomerProduct, Product)
        .join(Product, CustomerProduct.product_id == Product.id)
        .filter(CustomerProduct.customer_id == customer_id)
    )
    if q_str:
        like = f"%{q_str}%"
        q = q.filter(
            db.or_(
                Product.name.like(like),
                Product.spec.like(like),
                Product.product_code.like(like),
                CustomerProduct.customer_material_no.like(like),
                CustomerProduct.material_no.like(like),
            )
        )
    q = q.order_by(Product.product_code).limit(limit)
    items = []
    for cp, p in q.all():
        items.append({
            "id": cp.id,
            "product_code": p.product_code or "",
            "product_name": p.name or "",
            "product_spec": (p.spec or "")[:64],
            "customer_material_no": (cp.customer_material_no or "")[:64],
            "unit": cp.unit or (p.base_unit or ""),
        })
    return jsonify({"items": items})


@bp.route("/deliveries/pending-items", methods=["GET"])
@require_api_key
def pending_items():
    """待发货订单行：customer_id 必填，order_id 可选（指定则只返回该订单行，配合 FIFO/指定订单）。"""
    customer_id = request.args.get("customer_id", type=int)
    order_id = request.args.get("order_id", type=int) or None
    if not customer_id:
        return jsonify({"items": []})
    items = get_pending_order_items(customer_id, order_id)
    return jsonify({
        "items": [
            {
                "order_item_id": x["order_item"].id,
                "order_id": x["order"].id,
                "order_no": x["order"].order_no,
                "product_name": x["order_item"].product_name or "",
                "product_spec": (x["order_item"].product_spec or "")[:64],
                "customer_material_no": (x["order_item"].customer_material_no or "")[:64],
                "quantity": float(x["order_item"].quantity),
                "remaining_qty": x["remaining_qty"],
                "unit": (x["order_item"].unit or "")[:16],
            }
            for x in items
        ]
    })


@bp.route("/orders", methods=["POST"])
@require_api_key
def create_order():
    """创建订单。Body: customer_id, items: [{ customer_product_id, quantity, is_sample? }], 可选 customer_order_no, salesperson, order_date, required_date, payment_type, remark。"""
    data = request.get_json(force=True, silent=True) or {}
    order, err = create_order_from_data(data, existing_order=None)
    if err:
        return jsonify(ok=False, error=err), 400
    return jsonify(ok=True, order_id=order.id, order_no=order.order_no)


@bp.route("/deliveries", methods=["POST"])
@require_api_key
def create_delivery():
    """创建送货单。Body: customer_id, lines: [{ order_item_id, quantity }]；可选 express_company_id（缺省顺丰）, delivery_date（缺省今天）, driver, plate_no, remark；可选 order_id 指定从某单送。"""
    data = request.get_json(force=True, silent=True) or {}
    delivery, err = create_delivery_from_data(data)
    if err:
        return jsonify(ok=False, error=err), 400
    return jsonify(
        ok=True,
        delivery_id=delivery.id,
        delivery_no=delivery.delivery_no,
        waybill_no=delivery.waybill_no,
    )
