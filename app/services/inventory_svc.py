"""库存台账：期初、进出明细、送货自动出库、结存查询。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, List, Optional, Tuple

from flask import current_app
from sqlalchemy import text

from app import db
from app.models import (
    CustomerProduct,
    Delivery,
    DeliveryItem,
    InventoryMovement,
    InventoryOpeningBalance,
    OrderItem,
    Product,
)

INV_FINISHED = "finished"
INV_SEMI = "semi"
SOURCE_MANUAL = "manual"
SOURCE_DELIVERY = "delivery"


def default_storage_area_for_delivery() -> str:
    return (current_app.config.get("INVENTORY_DEFAULT_STORAGE_AREA") or "").strip()


@dataclass
class DeliveryLineProduct:
    delivery_item: DeliveryItem
    product_id: int


def delivery_lines_with_products(delivery_id: int) -> Tuple[List[DeliveryLineProduct], Optional[str]]:
    """解析送货单行对应系统产品。任一行无法解析则返回 (partial, error_msg)。"""
    items: List[DeliveryItem] = (
        DeliveryItem.query.filter_by(delivery_id=delivery_id)
        .order_by(DeliveryItem.id)
        .all()
    )
    out: List[DeliveryLineProduct] = []
    for di in items:
        oi = OrderItem.query.get(di.order_item_id)
        if not oi or not oi.customer_product_id:
            return [], "存在无法关联到客户产品的订单行，无法标记已发（请先维护订单明细的客户产品）。"
        cp = CustomerProduct.query.get(oi.customer_product_id)
        if not cp or not cp.product_id:
            return [], "存在无法关联到系统产品的订单行，无法标记已发。"
        out.append(DeliveryLineProduct(delivery_item=di, product_id=int(cp.product_id)))
    return out, None


def create_delivery_outbound_movements(
    delivery: Delivery,
    created_by: int,
    storage_area: str,
    lines: List[DeliveryLineProduct],
) -> None:
    """写入送货出库明细；依赖 uk_inv_mov_delivery_item 幂等。"""
    for lp in lines:
        di = lp.delivery_item
        p = Product.query.get(lp.product_id)
        unit = (di.unit or (p.base_unit if p else None) or None) if p else di.unit
        m = InventoryMovement(
            category=INV_FINISHED,
            direction="out",
            product_id=lp.product_id,
            material_id=0,
            storage_area=storage_area,
            quantity=di.quantity,
            unit=unit,
            biz_date=delivery.delivery_date,
            source_type=SOURCE_DELIVERY,
            source_delivery_id=delivery.id,
            source_delivery_item_id=di.id,
            remark=None,
            created_by=created_by,
        )
        db.session.add(m)


def delete_delivery_sourced_movements(delivery_id: int) -> int:
    """删除某送货单自动生成的出库记录。"""
    q = InventoryMovement.query.filter_by(
        source_type=SOURCE_DELIVERY, source_delivery_id=delivery_id
    )
    n = q.count()
    q.delete(synchronize_session=False)
    return n


def create_manual_movement(
    *,
    category: str,
    direction: str,
    product_id: int,
    material_id: int,
    storage_area: str,
    quantity: Decimal,
    unit: Optional[str],
    biz_date,
    remark: Optional[str],
    created_by: int,
) -> InventoryMovement:
    m = InventoryMovement(
        category=category,
        direction=direction,
        product_id=product_id,
        material_id=material_id,
        storage_area=storage_area.strip()[:32],
        quantity=quantity,
        unit=(unit.strip()[:16] if unit else None),
        biz_date=biz_date,
        source_type=SOURCE_MANUAL,
        source_delivery_id=None,
        source_delivery_item_id=None,
        remark=(remark.strip()[:255] if remark else None),
        created_by=created_by,
    )
    db.session.add(m)
    return m


def suggest_storage_area_for_product(product_id: int) -> str:
    """按历史流水或期初推断成品默认仓储区；无则返回空串。"""
    if not product_id:
        return ""
    m = (
        InventoryMovement.query.filter_by(
            category=INV_FINISHED, product_id=product_id
        )
        .filter(InventoryMovement.storage_area != "")
        .order_by(InventoryMovement.id.desc())
        .first()
    )
    if m and (m.storage_area or "").strip():
        return (m.storage_area or "").strip()[:32]
    o = (
        InventoryOpeningBalance.query.filter_by(
            category=INV_FINISHED, product_id=product_id
        )
        .filter(InventoryOpeningBalance.storage_area != "")
        .order_by(InventoryOpeningBalance.id.asc())
        .first()
    )
    if o and (o.storage_area or "").strip():
        return (o.storage_area or "").strip()[:32]
    return ""


def _like_pat(kw: str) -> str:
    s = kw.strip()
    if not s:
        return ""
    return f"%{s.replace('%', r'\\%').replace('_', r'\\_')}%"


def query_stock_aggregate(
    *,
    category: str = "",
    storage_area_kw: str = "",
    spec_kw: str = "",
    name_spec_kw: str = "",
    page: int = 1,
    per_page: int = 30,
) -> Tuple[List[dict[str, Any]], int]:
    """按 bucket 聚合期初与收发，返回行字典列表与总条数。"""
    page = max(1, page)
    per_page = max(1, min(per_page, 100))
    offset = (page - 1) * per_page

    where_parts = ["1=1"]
    params: dict[str, Any] = {}

    if category in (INV_FINISHED, INV_SEMI):
        where_parts.append("b.category = :category")
        params["category"] = category
    if storage_area_kw.strip():
        where_parts.append("b.storage_area LIKE :sa_pat ESCAPE '\\\\'")
        params["sa_pat"] = _like_pat(storage_area_kw)
    if spec_kw.strip():
        where_parts.append(
            "(b.category != 'finished' OR b.product_id = 0 OR "
            "COALESCE(p.spec,'') LIKE :spec_pat ESCAPE '\\\\')"
        )
        params["spec_pat"] = _like_pat(spec_kw)
    if name_spec_kw.strip():
        where_parts.append(
            "(b.category != 'finished' OR b.product_id = 0 OR "
            "p.name LIKE :ns_pat ESCAPE '\\\\' OR COALESCE(p.spec,'') LIKE :ns_pat ESCAPE '\\\\' "
            "OR p.product_code LIKE :ns_pat ESCAPE '\\\\')"
        )
        params["ns_pat"] = _like_pat(name_spec_kw)

    where_sql = " AND ".join(where_parts)

    inner = f"""
FROM (
  SELECT DISTINCT category, product_id, material_id, storage_area FROM inventory_opening_balance
  UNION
  SELECT DISTINCT category, product_id, material_id, storage_area FROM inventory_movement
) b
LEFT JOIN inventory_opening_balance o
  ON o.category = b.category AND o.product_id = b.product_id
  AND o.material_id = b.material_id AND o.storage_area = b.storage_area
LEFT JOIN (
  SELECT category, product_id, material_id, storage_area,
    SUM(CASE WHEN direction = 'in' THEN quantity ELSE 0 END) AS qty_in,
    SUM(CASE WHEN direction = 'out' THEN quantity ELSE 0 END) AS qty_out
  FROM inventory_movement
  GROUP BY category, product_id, material_id, storage_area
) a ON a.category = b.category AND a.product_id = b.product_id
  AND a.material_id = b.material_id AND a.storage_area = b.storage_area
LEFT JOIN product p ON b.product_id = p.id AND b.category = 'finished' AND b.product_id > 0
WHERE {where_sql}
"""

    count_sql = text(f"SELECT COUNT(*) AS c FROM (SELECT 1 AS x {inner}) t")
    total = db.session.execute(count_sql, params).scalar() or 0

    data_sql = text(
        f"""
SELECT
  b.category,
  b.product_id,
  b.material_id,
  b.storage_area,
  COALESCE(o.opening_qty, 0) AS opening_qty,
  COALESCE(a.qty_in, 0) AS qty_in,
  COALESCE(a.qty_out, 0) AS qty_out,
  p.product_code AS product_code,
  p.name AS product_name,
  p.spec AS product_spec
{inner}
ORDER BY b.storage_area, b.category, b.product_id, b.material_id
LIMIT :limit OFFSET :offset
"""
    )
    params_with_lim = {**params, "limit": per_page, "offset": offset}
    rows = db.session.execute(data_sql, params_with_lim).mappings().all()
    out = []
    for r in rows:
        opening = Decimal(str(r["opening_qty"]))
        qi = Decimal(str(r["qty_in"]))
        qo = Decimal(str(r["qty_out"]))
        out.append(
            {
                "category": r["category"],
                "product_id": r["product_id"],
                "material_id": r["material_id"],
                "storage_area": r["storage_area"],
                "opening_qty": opening,
                "qty_in": qi,
                "qty_out": qo,
                "closing_qty": opening + qi - qo,
                "product_code": r["product_code"],
                "product_name": r["product_name"],
                "product_spec": r["product_spec"],
            }
        )
    return out, int(total)
