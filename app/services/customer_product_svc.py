"""客户产品创建，供 OpenClaw 与扩展接口使用。"""
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Tuple

from app import db
from app.models import Customer, CustomerProduct, Product


def create_customer_product_from_data(
    data: Dict[str, Any],
    *,
    allow_price_fields: bool,
) -> Tuple[Optional[CustomerProduct], Optional[str]]:
    """
    data: customer_id, product_id 必填；
    customer_material_no?, unit?, price?, currency?, remark?
    （物料编号始终与产品 product_code 一致；请求中的 material_no 已忽略。）
    allow_price_fields 为 False 时忽略 price、currency（与非管理员 Web 行为一致）。
    """
    try:
        customer_id = int(data.get("customer_id"))
    except (TypeError, ValueError):
        return None, "请选择客户 customer_id。"

    try:
        product_id = int(data.get("product_id"))
    except (TypeError, ValueError):
        return None, "请选择产品 product_id。"

    if not db.session.get(Customer, customer_id):
        return None, "客户不存在。"

    prod = db.session.get(Product, product_id)
    if not prod:
        return None, "产品不存在。"

    existing = CustomerProduct.query.filter_by(
        customer_id=customer_id, product_id=product_id
    ).first()
    if existing:
        return None, "该客户已绑定此产品，请勿重复创建。"

    cp = CustomerProduct()
    cp.customer_id = customer_id
    cp.product_id = product_id
    cp.customer_material_no = (data.get("customer_material_no") or "").strip() or None
    cp.material_no = prod.product_code or None
    cp.unit = (data.get("unit") or "").strip() or None
    cp.remark = (data.get("remark") or "").strip() or None

    if allow_price_fields:
        price_raw = data.get("price")
        if price_raw is not None and str(price_raw).strip() != "":
            try:
                cp.price = Decimal(str(price_raw))
            except (InvalidOperation, ValueError):
                cp.price = None
        else:
            cp.price = None
        cur = data.get("currency")
        cp.currency = (str(cur).strip() if cur is not None else "") or None
    else:
        cp.price = None
        cp.currency = None

    db.session.add(cp)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return None, "保存客户产品失败，请重试。"

    return cp, None
