"""OpenClaw 专用 API 路由：JSON 入参/出参，全局 Key 或用户 Token + 能力码，客户信息仅返回简称。"""
from flask import g, jsonify, request

from app import db
from app.models import Company, Customer, CustomerProduct, Product
from app.auth.openclaw_auth import require_openclaw
from app.auth.capabilities import user_can_cap
from app.services.customer_svc import create_customer_from_data
from app.services.customer_product_svc import create_customer_product_from_data
from app.services.order_svc import create_order_from_data, preview_order_create
from app.services.delivery_svc import (
    create_delivery_from_data,
    get_pending_order_items,
    preview_delivery_create,
    effective_customer_material_no,
)

from app.openclaw import bp
from app.utils.query import is_valid_customer_search_keyword


def _openclaw_allow_price_fields() -> bool:
    """全局 Key、admin，或具备 openclaw.customer_product.create 的用户令牌可写单价/币种。"""
    if getattr(g, "audit_auth", None) == "api_key":
        return True
    u = getattr(g, "openclaw_user", None)
    if not u:
        return False
    if getattr(u, "role_code", None) == "admin":
        return True
    return user_can_cap(u, "openclaw.customer_product.create")


def _customer_display_label(c: Customer) -> str:
    """对外仅展示简称，不暴露完整客户名。"""
    return (c.short_code or c.customer_code or "").strip() or str(c.id)


def _audit_openclaw_write(payload: dict) -> None:
    """写入 audit_log.extra（结构化 OpenClaw 写操作）。"""
    base = {"openclaw": True}
    base.update(payload)
    g.audit_openclaw_extra = base


@bp.route("/companies", methods=["GET"])
@require_openclaw("openclaw.companies.read")
def companies():
    """经营主体列表：供新建客户时选择 company_id。"""
    rows = Company.query.order_by(Company.id).all()
    return jsonify({
        "items": [
            {"id": c.id, "code": c.code or "", "name": c.name or ""}
            for c in rows
        ]
    })


@bp.route("/products", methods=["GET"])
@require_openclaw("openclaw.products.read")
def products():
    """系统产品搜索：供绑定客户产品前确认 product_id。q= 编码/名称/规格。"""
    q_str = (request.args.get("q") or "").strip()
    limit = min(max(request.args.get("limit", 50, type=int), 1), 100)
    q = Product.query.order_by(Product.product_code)
    if q_str:
        like = f"%{q_str}%"
        q = q.filter(
            db.or_(
                Product.name.like(like),
                Product.spec.like(like),
                Product.product_code.like(like),
                Product.remark.like(like),
            )
        )
    rows = q.limit(limit).all()
    return jsonify({
        "items": [
            {
                "id": p.id,
                "product_code": p.product_code or "",
                "name": p.name or "",
                "spec": (p.spec or "")[:128],
                "remark": (p.remark or "")[:255],
                "base_unit": p.base_unit or "",
            }
            for p in rows
        ]
    })


@bp.route("/customers", methods=["GET"])
@require_openclaw("openclaw.customers.read")
def customers():
    """客户列表：仅返回 id 与简称（short_code/customer_code），供解析与选择。q= 搜索简称/编码。"""
    q_str = (request.args.get("q") or "").strip()
    if not is_valid_customer_search_keyword(q_str):
        return (
            jsonify(
                ok=False,
                error="请提供客户搜索关键字 q（至少 2 个字符）。",
            ),
            400,
        )
    limit = min(max(request.args.get("limit", 20, type=int), 1), 100)
    like = f"%{q_str}%"
    rows = (
        Customer.query.filter(
            db.or_(
                Customer.short_code.like(like),
                Customer.customer_code.like(like),
            )
        )
        .order_by(Customer.customer_code)
        .limit(limit)
        .all()
    )
    return jsonify({
        "items": [
            {"id": c.id, "label": _customer_display_label(c)}
            for c in rows
        ]
    })


@bp.route("/customers", methods=["POST"])
@require_openclaw("openclaw.customer.create")
def create_customer():
    """新建客户（单主体）。Body: name, company_id 必填；short_code, contact, phone, fax, address, payment_terms, remark, tax_point 可选。"""
    data = request.get_json(force=True, silent=True) or {}
    cust, err = create_customer_from_data(data)
    _audit_openclaw_write({
        "action": "create_customer",
        "ok": err is None,
        "customer_id": cust.id if cust else None,
        "company_id": data.get("company_id"),
        "error": err,
    })
    if err:
        return jsonify(ok=False, error=err), 400
    return jsonify(
        ok=True,
        customer_id=cust.id,
        customer_code=cust.customer_code,
        label=_customer_display_label(cust),
    )


@bp.route("/customer-products", methods=["GET"])
@require_openclaw("openclaw.customer_products.read")
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


@bp.route("/customer-products", methods=["POST"])
@require_openclaw("openclaw.customer_product.create")
def create_customer_product():
    """绑定客户与系统产品。Body: customer_id, product_id 必填；其余可选。单价/币种：全局 Key、admin 或具备本接口能力的用户令牌可写。"""
    data = request.get_json(force=True, silent=True) or {}
    cp, err = create_customer_product_from_data(
        data, allow_price_fields=_openclaw_allow_price_fields()
    )
    _audit_openclaw_write({
        "action": "create_customer_product",
        "ok": err is None,
        "customer_product_id": cp.id if cp else None,
        "customer_id": data.get("customer_id"),
        "product_id": data.get("product_id"),
        "error": err,
    })
    if err:
        return jsonify(ok=False, error=err), 400
    return jsonify(ok=True, customer_product_id=cp.id)


@bp.route("/deliveries/pending-items", methods=["GET"])
@require_openclaw("openclaw.pending_items.read")
def pending_items():
    """待发货订单行：customer_id 必填，order_id 可选。含已发/待发占用/可再开单数量。"""
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
                "customer_material_no": effective_customer_material_no(x["order_item"])[
                    :64
                ],
                "quantity": float(x["order_item"].quantity),
                "delivered_qty": x["delivered_qty"],
                "in_transit_qty": x["in_transit_qty"],
                "remaining_qty": x["remaining_qty"],
                "unit": (x["order_item"].unit or "")[:16],
            }
            for x in items
        ]
    })


@bp.route("/orders/preview", methods=["POST"])
@require_openclaw("openclaw.order.preview")
def preview_order():
    """不写库：校验订单创建参数并返回摘要，用户确认后再 POST /orders。"""
    data = request.get_json(force=True, silent=True) or {}
    err, summary = preview_order_create(data)
    return jsonify(ok=(err is None), error=err, summary=summary)


@bp.route("/orders", methods=["POST"])
@require_openclaw("openclaw.order.create")
def create_order():
    """创建订单。Body: customer_id, customer_order_no（必填）, items, payment_type 等。订单号仅由服务端生成，请求体勿自拟。"""
    data = request.get_json(force=True, silent=True) or {}
    if not (data.get("customer_order_no") or "").strip():
        return jsonify(ok=False, error="请提供客户订单编号 customer_order_no。"), 400
    order, err = create_order_from_data(data, existing_order=None)
    _audit_openclaw_write({
        "action": "create_order",
        "customer_id": data.get("customer_id"),
        "ok": err is None,
        "order_id": order.id if order else None,
        "order_no": order.order_no if order else None,
        "error": err,
    })
    if err:
        return jsonify(ok=False, error=err), 400
    return jsonify(ok=True, order_id=order.id, order_no=order.order_no)


@bp.route("/deliveries/preview", methods=["POST"])
@require_openclaw("openclaw.delivery.preview")
def preview_delivery():
    """不写库：校验送货单创建参数并返回摘要，用户确认后再 POST /deliveries。"""
    data = request.get_json(force=True, silent=True) or {}
    err, summary = preview_delivery_create(data)
    return jsonify(ok=(err is None), error=err, summary=summary)


@bp.route("/deliveries", methods=["POST"])
@require_openclaw("openclaw.delivery.create")
def create_delivery():
    """创建送货单。Body: customer_id, lines: [{ order_item_id, quantity }]；可选 order_id（所有行须属于该订单且订单须属于该客户）；可选 self_delivery、express_company_id、waybill_no、delivery_date 等。送货单号与运单占号由服务端处理，勿自拟。"""
    data = request.get_json(force=True, silent=True) or {}
    delivery, err = create_delivery_from_data(data)
    _audit_openclaw_write({
        "action": "create_delivery",
        "customer_id": data.get("customer_id"),
        "order_id": data.get("order_id"),
        "ok": err is None,
        "delivery_id": delivery.id if delivery else None,
        "delivery_no": delivery.delivery_no if delivery else None,
        "error": err,
    })
    if err:
        return jsonify(ok=False, error=err), 400
    return jsonify(
        ok=True,
        delivery_id=delivery.id,
        delivery_no=delivery.delivery_no,
        waybill_no=delivery.waybill_no,
    )
