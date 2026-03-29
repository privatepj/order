"""库存台账：期初、进出明细、送货自动出库、结存查询。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app
from sqlalchemy import func, text

from app import db
from app.models import (
    CustomerProduct,
    Delivery,
    DeliveryItem,
    InventoryMovement,
    InventoryMovementBatch,
    InventoryOpeningBalance,
    OrderItem,
    Product,
)

INV_FINISHED = "finished"
INV_SEMI = "semi"
SOURCE_MANUAL = "manual"
SOURCE_DELIVERY = "delivery"

BATCH_SOURCE_FORM = "form"
BATCH_SOURCE_EXCEL = "excel"
BATCH_SOURCE_DELIVERY = "delivery"


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


def create_movement_batch(
    *,
    category: str,
    biz_date,
    direction: str,
    source: str,
    line_count: int,
    created_by: int,
    original_filename: Optional[str] = None,
    source_delivery_id: Optional[int] = None,
    remark: Optional[str] = None,
) -> InventoryMovementBatch:
    fn = None
    if original_filename and str(original_filename).strip():
        fn = str(original_filename).strip()[:255]
    b = InventoryMovementBatch(
        category=category,
        biz_date=biz_date,
        direction=direction,
        source=source,
        line_count=line_count,
        original_filename=fn,
        source_delivery_id=source_delivery_id,
        remark=(remark.strip()[:255] if remark else None),
        created_by=created_by,
    )
    db.session.add(b)
    db.session.flush()
    return b


def create_delivery_outbound_movements(
    delivery: Delivery,
    created_by: int,
    storage_area: str,
    lines: List[DeliveryLineProduct],
) -> None:
    """写入送货出库明细；先建批次再写明细；依赖 uk_inv_mov_delivery_item 幂等。"""
    if not lines:
        return
    batch = create_movement_batch(
        category=INV_FINISHED,
        biz_date=delivery.delivery_date,
        direction="out",
        source=BATCH_SOURCE_DELIVERY,
        line_count=len(lines),
        created_by=created_by,
        source_delivery_id=delivery.id,
    )
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
            movement_batch_id=batch.id,
        )
        db.session.add(m)


def delete_delivery_sourced_movements(delivery_id: int) -> int:
    """删除某送货单自动生成的出库记录及对应批次。"""
    n = InventoryMovement.query.filter_by(
        source_type=SOURCE_DELIVERY, source_delivery_id=delivery_id
    ).delete(synchronize_session=False)
    batch = InventoryMovementBatch.query.filter_by(
        source=BATCH_SOURCE_DELIVERY, source_delivery_id=delivery_id
    ).first()
    if batch:
        db.session.delete(batch)
    return n


def void_movement_batch(batch_id: int) -> None:
    """撤销手工或 Excel 批次（删除明细与批次头）。送货批次禁止调用。"""
    batch = InventoryMovementBatch.query.get(batch_id)
    if not batch:
        raise ValueError("批次不存在。")
    if batch.source == BATCH_SOURCE_DELIVERY:
        raise ValueError("送货出库批次请在送货单中回退待发或标记失效，勿在库存页撤销。")
    InventoryMovement.query.filter_by(movement_batch_id=batch_id).delete(synchronize_session=False)
    db.session.delete(batch)


def normalize_spec_for_match(spec: Optional[str]) -> str:
    """与 Excel 导入一致：NULL/空白规格与空字符串等同。"""
    if spec is None:
        return ""
    return spec.strip() if isinstance(spec, str) else str(spec).strip()


def movement_import_label(name_st: str, spec_raw: Optional[str]) -> str:
    """导入失败信息前缀：品名「…」规格「…」（不写 Excel 行号）。"""
    nd = (name_st or "").strip() or "（空）"
    sp = normalize_spec_for_match(spec_raw)
    spec_disp = sp if sp else "（空）"
    return f"品名「{nd}」规格「{spec_disp}」"


def movement_import_failed_row(
    *,
    name: str,
    spec: str,
    area: str,
    quantity: str,
    unit: Optional[str],
    remark: Optional[str],
    reason: str,
) -> Dict[str, Any]:
    return {
        "name": name or "",
        "spec": spec or "",
        "area": area or "",
        "quantity": quantity,
        "unit": unit or "",
        "remark": remark or "",
        "reason": reason,
    }


def find_product_id_by_name_spec(name: str, spec: str) -> Tuple[Optional[int], Optional[str]]:
    """
    按品名 + 规格精确匹配产品。
    返回 (product_id, None) 或 (None, 简短错误说明)。
    """
    n = (name or "").strip()
    spec_n = normalize_spec_for_match(spec)
    if not n:
        return None, "品名为空"
    matches = (
        Product.query.filter(
            Product.name == n,
            func.coalesce(Product.spec, "") == spec_n,
        )
        .order_by(Product.id)
        .all()
    )
    if not matches:
        return None, "未找到匹配的产品（品名+规格）"
    if len(matches) > 1:
        return None, "匹配到多条产品，请核对主数据"
    return int(matches[0].id), None


def import_finished_movements_from_parsed_lines(
    parsed_lines: List[
        Tuple[int, str, str, str, Decimal, Optional[str], Optional[str]]
    ],
    *,
    direction: str,
    biz_date,
    created_by: int,
    original_filename: Optional[str] = None,
) -> Tuple[int, List[str], List[Dict[str, Any]]]:
    """
    成品手工流水批量导入。parsed_lines 每项：
    (excel_row, name, spec_raw, storage_area, quantity, unit, remark)。
    excel_row 仅保留作扩展用，错误文案不写行号。
    仅当至少一行成功时 commit；否则 rollback。
    返回 (成功条数, 错误信息列表, 失败行明细供导出)。
    """
    errors: List[str] = []
    failed_rows: List[Dict[str, Any]] = []
    to_write: List[
        Tuple[int, str, Decimal, Optional[str], Optional[str], str, str]
    ] = []

    def _qty_str(q: Decimal) -> str:
        s = format(q, "f").rstrip("0").rstrip(".")
        return s if s else "0"

    for _excel_row, name, spec_raw, storage_area, qty, unit, remark in parsed_lines:
        spec_cell = (spec_raw or "").strip() if isinstance(spec_raw, str) else str(spec_raw or "").strip()
        name_st = (name or "").strip()
        area = (storage_area or "").strip()
        u_raw = unit
        r_raw = remark

        def _append_fail(reason: str) -> None:
            u_disp = (
                u_raw.strip()
                if isinstance(u_raw, str)
                else (str(u_raw).strip() if u_raw is not None else "")
            )
            r_disp = (
                r_raw.strip()
                if isinstance(r_raw, str)
                else (str(r_raw).strip() if r_raw is not None else "")
            )
            errors.append(f"{movement_import_label(name_st, spec_raw)}：{reason}")
            failed_rows.append(
                movement_import_failed_row(
                    name=name_st,
                    spec=spec_cell,
                    area=area,
                    quantity=_qty_str(qty) if qty is not None else "",
                    unit=u_disp or None,
                    remark=r_disp or None,
                    reason=reason,
                )
            )

        if not name_st:
            has_other = bool(
                normalize_spec_for_match(spec_raw)
                or area
                or qty > 0
                or (unit and str(unit).strip())
                or (remark and str(remark).strip())
            )
            if has_other:
                _append_fail("品名为空")
            continue

        pid, err = find_product_id_by_name_spec(name_st, spec_raw)
        if err:
            _append_fail(err)
            continue

        if not area:
            _append_fail("仓储区不能为空")
            continue

        if qty <= 0:
            _append_fail("数量须大于 0")
            continue

        u = None
        if unit is not None:
            u = unit.strip()[:16] if isinstance(unit, str) else str(unit).strip()[:16]
            u = u or None
        rmk = None
        if remark is not None:
            rmk = remark.strip()[:255] if isinstance(remark, str) else str(remark).strip()[:255]
            rmk = rmk or None

        to_write.append((pid, area, qty, u, rmk, name_st, spec_cell))

    if not to_write:
        db.session.rollback()
        return 0, errors, failed_rows

    try:
        batch = create_movement_batch(
            category=INV_FINISHED,
            biz_date=biz_date,
            direction=direction,
            source=BATCH_SOURCE_EXCEL,
            line_count=len(to_write),
            created_by=created_by,
            original_filename=original_filename,
        )
        for product_id, area, qty, unit, remark, name_st, spec_cell in to_write:
            p = Product.query.get(product_id)
            if not p:
                db.session.rollback()
                reason = "内部错误：产品不存在"
                errors.append(f"{movement_import_label(name_st, spec_cell)}：{reason}")
                failed_rows.append(
                    movement_import_failed_row(
                        name=name_st,
                        spec=spec_cell,
                        area=area,
                        quantity=_qty_str(qty),
                        unit=unit or "",
                        remark=remark or "",
                        reason=reason,
                    )
                )
                return 0, errors, failed_rows
            create_manual_movement(
                category=INV_FINISHED,
                direction=direction,
                product_id=product_id,
                material_id=0,
                storage_area=area,
                quantity=qty,
                unit=unit or (p.base_unit or None),
                biz_date=biz_date,
                remark=remark,
                created_by=created_by,
                movement_batch_id=batch.id,
            )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return len(to_write), errors, failed_rows


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
    movement_batch_id: Optional[int] = None,
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
        movement_batch_id=movement_batch_id,
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
