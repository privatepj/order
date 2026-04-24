"""库存台账：期初、进出明细、送货自动出库、结存查询。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app
from sqlalchemy import and_, case, func, or_, text

from app import db
from app.models import (
    CustomerProduct,
    Delivery,
    DeliveryItem,
    InventoryMovement,
    InventoryMovementBatch,
    InventoryOpeningBalance,
    InventoryReservation,
    OrderItem,
    Product,
    SemiMaterial,
)
from app.services import orchestrator_engine
from app.services.orchestrator_contracts import EVENT_INVENTORY_CHANGED

INV_FINISHED = "finished"
INV_SEMI = "semi"
INV_MATERIAL = "material"
SOURCE_MANUAL = "manual"

# 库存预留（计划占用，非出库流水）
RES_REF_PREPLAN = "preplan"
RES_STATUS_ACTIVE = "active"
RES_STATUS_RELEASED = "released"
RES_STATUS_CONSUMED = "consumed"
SOURCE_DELIVERY = "delivery"
SOURCE_PROCUREMENT = "procurement"

BATCH_SOURCE_FORM = "form"
BATCH_SOURCE_EXCEL = "excel"
BATCH_SOURCE_DELIVERY = "delivery"
BATCH_SOURCE_MAX_LEN = 64


def normalize_manual_batch_source(raw: Optional[str]) -> str:
    """手工录入批次来源：空为 form；禁止与系统保留 excel/delivery 混淆。"""
    s = (raw or "").strip()
    if not s:
        return BATCH_SOURCE_FORM
    if s in (BATCH_SOURCE_EXCEL, BATCH_SOURCE_DELIVERY):
        raise ValueError("批次来源不能使用保留字：excel、delivery。")
    if len(s) > BATCH_SOURCE_MAX_LEN:
        raise ValueError(f"批次来源最多 {BATCH_SOURCE_MAX_LEN} 个字符。")
    return s


def default_storage_area_for_delivery() -> str:
    return (current_app.config.get("INVENTORY_DEFAULT_STORAGE_AREA") or "").strip()


@dataclass
class DeliveryLineProduct:
    delivery_item: DeliveryItem
    product_id: int


def delivery_lines_with_products(
    delivery_id: int,
) -> Tuple[List[DeliveryLineProduct], Optional[str]]:
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
            return (
                [],
                "存在无法关联到客户产品的订单行，无法标记已发（请先维护订单明细的客户产品）。",
            )
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
    src = (source or "").strip()
    b = InventoryMovementBatch(
        category=category,
        biz_date=biz_date,
        direction=direction,
        source=src,
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
    related_order_ids = sorted(
        {
            int(lp.delivery_item.order_id)
            for lp in lines
            if getattr(lp.delivery_item, "order_id", None)
        }
    )
    for oid in related_order_ids:
        orchestrator_engine.emit_event(
            event_type=EVENT_INVENTORY_CHANGED,
            biz_key=f"order:{oid}",
            payload={
                "order_id": oid,
                "source_id": int(delivery.id),
                "version": int(delivery.updated_at.timestamp())
                if getattr(delivery, "updated_at", None)
                else int(delivery.id),
                "source": "inventory_svc.create_delivery_outbound_movements",
            },
        )


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
    InventoryMovement.query.filter_by(movement_batch_id=batch_id).delete(
        synchronize_session=False
    )
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


def find_product_id_by_name_spec(
    name: str, spec: str
) -> Tuple[Optional[int], Optional[str]]:
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


def find_semi_material_id_by_name_spec(
    category: str, name: str, spec: str
) -> Tuple[Optional[int], Optional[str]]:
    """
    按品名 + 规格精确匹配半成品/物料主数据。
    - category 取值：'semi' / 'material'
    返回 (semi_material_id, None) 或 (None, 简短错误说明)。
    """
    n = (name or "").strip()
    spec_n = normalize_spec_for_match(spec)
    if not n:
        return None, "品名为空"

    matches = (
        SemiMaterial.query.filter(
            SemiMaterial.kind == category,
            SemiMaterial.name == n,
            func.coalesce(SemiMaterial.spec, "") == spec_n,
        )
        .order_by(SemiMaterial.id)
        .all()
    )
    if not matches:
        return None, "未找到匹配的半成品/物料（品名+规格）"
    if len(matches) > 1:
        return None, "匹配到多条半成品/物料，请核对主数据"
    return int(matches[0].id), None


def find_item_id_by_name_spec(
    category: str, name: str, spec: str
) -> Tuple[Optional[int], Optional[str]]:
    """统一入口：finished -> Product；semi/material -> SemiMaterial。"""
    if category == INV_FINISHED:
        return find_product_id_by_name_spec(name, spec)
    if category in (INV_SEMI, INV_MATERIAL):
        return find_semi_material_id_by_name_spec(category, name, spec)
    return None, "请选择类别。"


def import_semi_material_movements_from_parsed_lines(
    parsed_lines: List[
        Tuple[int, str, str, str, Decimal, Optional[str], Optional[str]]
    ],
    *,
    category: str,
    direction: str,
    biz_date,
    created_by: int,
    original_filename: Optional[str] = None,
) -> Tuple[int, List[str], List[Dict[str, Any]]]:
    """
    半成品/物料手工流水批量导入。parsed_lines 每项：
    (excel_row, name, spec_raw, storage_area, quantity, unit, remark)。
    仅当至少一行成功时 commit；否则 rollback。
    返回 (成功条数, 错误信息列表, 失败行明细供导出)。
    """
    if category not in (INV_SEMI, INV_MATERIAL):
        raise ValueError("category 只能是 semi 或 material。")

    errors: List[str] = []
    failed_rows: List[Dict[str, Any]] = []
    to_write: List[
        Tuple[int, str, Decimal, Optional[str], Optional[str], str, str]
    ] = []

    def _qty_str(q: Decimal) -> str:
        s = format(q, "f").rstrip("0").rstrip(".")
        return s if s else "0"

    for _excel_row, name, spec_raw, storage_area, qty, unit, remark in parsed_lines:
        spec_cell = (
            (spec_raw or "").strip()
            if isinstance(spec_raw, str)
            else str(spec_raw or "").strip()
        )
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
                or qty != 0
                or (unit and str(unit).strip())
                or (remark and str(remark).strip())
            )
            if has_other:
                _append_fail("品名为空")
            continue

        mid, err = find_semi_material_id_by_name_spec(category, name_st, spec_raw)
        if err:
            _append_fail(err)
            continue

        if not area:
            _append_fail("仓储区不能为空")
            continue

        if qty < 0:
            _append_fail("数量不能为负数")
            continue
        if direction == "out" and qty <= 0:
            _append_fail("出库数量须大于 0")
            continue

        item = SemiMaterial.query.get(mid)
        if not item:
            db.session.rollback()
            reason = "内部错误：半成品/物料不存在"
            errors.append(f"{movement_import_label(name_st, spec_cell)}：{reason}")
            failed_rows.append(
                movement_import_failed_row(
                    name=name_st,
                    spec=spec_cell,
                    area=area,
                    quantity=_qty_str(qty),
                    unit=(unit or "") or "",
                    remark=(remark or "") or "",
                    reason=reason,
                )
            )
            return 0, errors, failed_rows

        u = None
        if unit is not None:
            u = unit.strip()[:16] if isinstance(unit, str) else str(unit).strip()[:16]
            u = u or None
        u_final = u or (item.base_unit or None)

        rmk = None
        if remark is not None:
            rmk = (
                remark.strip()[:255]
                if isinstance(remark, str)
                else str(remark).strip()[:255]
            )
            rmk = rmk or None

        to_write.append((mid, area, qty, u_final, rmk, name_st, spec_cell))

    if not to_write:
        db.session.rollback()
        return 0, errors, failed_rows

    try:
        batch = create_movement_batch(
            category=category,
            biz_date=biz_date,
            direction=direction,
            source=BATCH_SOURCE_EXCEL,
            line_count=len(to_write),
            created_by=created_by,
            original_filename=original_filename,
        )
        for mid, area, qty, unit, remark, name_st, spec_cell in to_write:
            create_manual_movement(
                category=category,
                direction=direction,
                product_id=0,
                material_id=mid,
                storage_area=area,
                quantity=qty,
                unit=unit,
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


def import_movements_from_parsed_lines_by_category(
    parsed_lines: List[
        Tuple[int, str, str, str, Decimal, Optional[str], Optional[str]]
    ],
    *,
    category: str,
    direction: str,
    biz_date,
    created_by: int,
    original_filename: Optional[str] = None,
) -> Tuple[int, List[str], List[Dict[str, Any]]]:
    """
    根据 category 选择对应的导入逻辑：
    - finished -> Product
    - semi/material -> SemiMaterial
    """
    if category == INV_FINISHED:
        return import_finished_movements_from_parsed_lines(
            parsed_lines,
            direction=direction,
            biz_date=biz_date,
            created_by=created_by,
            original_filename=original_filename,
        )
    if category in (INV_SEMI, INV_MATERIAL):
        return import_semi_material_movements_from_parsed_lines(
            parsed_lines,
            category=category,
            direction=direction,
            biz_date=biz_date,
            created_by=created_by,
            original_filename=original_filename,
        )
    raise ValueError("请选择正确的 category。")


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
        spec_cell = (
            (spec_raw or "").strip()
            if isinstance(spec_raw, str)
            else str(spec_raw or "").strip()
        )
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
                or qty != 0
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

        if qty < 0:
            _append_fail("数量不能为负数")
            continue
        if direction == "out" and qty <= 0:
            _append_fail("出库数量须大于 0")
            continue

        u = None
        if unit is not None:
            u = unit.strip()[:16] if isinstance(unit, str) else str(unit).strip()[:16]
            u = u or None
        rmk = None
        if remark is not None:
            rmk = (
                remark.strip()[:255]
                if isinstance(remark, str)
                else str(remark).strip()[:255]
            )
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
    source_purchase_order_id: Optional[int] = None,
    source_purchase_receipt_id: Optional[int] = None,
) -> InventoryMovement:
    source_type = (
        SOURCE_PROCUREMENT
        if source_purchase_order_id or source_purchase_receipt_id
        else SOURCE_MANUAL
    )
    m = InventoryMovement(
        category=category,
        direction=direction,
        product_id=product_id,
        material_id=material_id,
        storage_area=storage_area.strip()[:32],
        quantity=quantity,
        unit=(unit.strip()[:16] if unit else None),
        biz_date=biz_date,
        source_type=source_type,
        source_delivery_id=None,
        source_delivery_item_id=None,
        source_purchase_order_id=source_purchase_order_id,
        source_purchase_receipt_id=source_purchase_receipt_id,
        remark=(remark.strip()[:255] if remark else None),
        created_by=created_by,
        movement_batch_id=movement_batch_id,
    )
    db.session.add(m)
    db.session.flush()
    orchestrator_engine.emit_event(
        event_type=EVENT_INVENTORY_CHANGED,
        biz_key=f"inventory_movement:{m.id}",
        payload={
            "source_id": int(m.id),
            "version": int(m.id),
            "source": "inventory_svc.create_manual_movement",
        },
    )
    return m


def suggest_storage_area_for_category_item(category: str, item_id: int) -> str:
    """
    按历史流水或期初推断默认仓储区；无则返回空串。
    - finished：item_id -> product_id
    - semi/material：item_id -> material_id
    """
    if not item_id:
        return ""

    # 历史流水优先
    q = InventoryMovement.query.filter(InventoryMovement.storage_area != "")
    if category == INV_FINISHED:
        q = q.filter(
            InventoryMovement.category == INV_FINISHED,
            InventoryMovement.product_id == item_id,
        )
    elif category in (INV_SEMI, INV_MATERIAL):
        q = q.filter(
            InventoryMovement.category == category,
            InventoryMovement.material_id == item_id,
        )
    else:
        return ""
    m = q.order_by(InventoryMovement.id.desc()).first()
    if m and (m.storage_area or "").strip():
        return (m.storage_area or "").strip()[:32]

    # 再看期初
    o_q = InventoryOpeningBalance.query.filter(
        InventoryOpeningBalance.storage_area != ""
    )
    if category == INV_FINISHED:
        o_q = o_q.filter(
            InventoryOpeningBalance.category == INV_FINISHED,
            InventoryOpeningBalance.product_id == item_id,
        )
    else:
        o_q = o_q.filter(
            InventoryOpeningBalance.category == category,
            InventoryOpeningBalance.material_id == item_id,
        )
    o = o_q.order_by(InventoryOpeningBalance.id.asc()).first()
    if o and (o.storage_area or "").strip():
        return (o.storage_area or "").strip()[:32]
    return ""


def suggest_storage_area_for_product(product_id: int) -> str:
    """兼容旧代码：成品默认仓储区建议。"""
    return suggest_storage_area_for_category_item(INV_FINISHED, product_id)


def _like_pat(kw: str) -> str:
    s = kw.strip()
    if not s:
        return ""
    esc = s.replace("%", r"\%").replace("_", r"\_")
    return f"%{esc}%"


def _movement_detail_query(
    *,
    categories: List[str],
    start_date,
    end_date,
    category: str = "",
    direction: str = "",
    storage_area_kw: str = "",
    name_spec_kw: str = "",
):
    valid_scope = [c for c in categories if c in (INV_FINISHED, INV_SEMI, INV_MATERIAL)]
    if not valid_scope:
        return None

    q = (
        db.session.query(
            InventoryMovement.id.label("movement_id"),
            InventoryMovement.movement_batch_id,
            InventoryMovement.category,
            InventoryMovement.direction,
            InventoryMovement.biz_date,
            InventoryMovement.storage_area,
            InventoryMovement.quantity,
            InventoryMovement.unit,
            InventoryMovement.source_type,
            InventoryMovement.source_delivery_id,
            InventoryMovement.source_purchase_order_id,
            InventoryMovement.source_purchase_receipt_id,
            InventoryMovement.remark,
            InventoryMovement.created_at,
            Product.product_code.label("f_code"),
            Product.name.label("f_name"),
            Product.spec.label("f_spec"),
            SemiMaterial.code.label("m_code"),
            SemiMaterial.name.label("m_name"),
            SemiMaterial.spec.label("m_spec"),
        )
        .outerjoin(
            Product,
            and_(
                InventoryMovement.category == INV_FINISHED,
                InventoryMovement.product_id == Product.id,
            ),
        )
        .outerjoin(
            SemiMaterial,
            and_(
                InventoryMovement.category.in_([INV_SEMI, INV_MATERIAL]),
                InventoryMovement.material_id == SemiMaterial.id,
            ),
        )
        .filter(InventoryMovement.category.in_(valid_scope))
        .filter(InventoryMovement.biz_date >= start_date)
        .filter(InventoryMovement.biz_date <= end_date)
    )

    if category in (INV_FINISHED, INV_SEMI, INV_MATERIAL):
        q = q.filter(InventoryMovement.category == category)
    if direction in ("in", "out"):
        q = q.filter(InventoryMovement.direction == direction)
    if storage_area_kw.strip():
        q = q.filter(
            InventoryMovement.storage_area.like(
                _like_pat(storage_area_kw), escape="\\"
            )
        )
    if name_spec_kw.strip():
        name_spec_pat = _like_pat(name_spec_kw)
        q = q.filter(
            or_(
                and_(
                    InventoryMovement.category == INV_FINISHED,
                    or_(
                        Product.product_code.like(name_spec_pat, escape="\\"),
                        Product.name.like(name_spec_pat, escape="\\"),
                        func.coalesce(Product.spec, "").like(name_spec_pat, escape="\\"),
                    ),
                ),
                and_(
                    InventoryMovement.category.in_([INV_SEMI, INV_MATERIAL]),
                    or_(
                        SemiMaterial.code.like(name_spec_pat, escape="\\"),
                        SemiMaterial.name.like(name_spec_pat, escape="\\"),
                        func.coalesce(SemiMaterial.spec, "").like(
                            name_spec_pat, escape="\\"
                        ),
                    ),
                ),
            )
        )
    return q


def _movement_detail_row_to_dict(row) -> dict[str, Any]:
    is_finished = row.category == INV_FINISHED
    code = row.f_code if is_finished else row.m_code
    name = row.f_name if is_finished else row.m_name
    spec = row.f_spec if is_finished else row.m_spec
    return {
        "movement_id": int(row.movement_id),
        "movement_batch_id": row.movement_batch_id,
        "biz_date": row.biz_date,
        "category": row.category,
        "direction": row.direction,
        "storage_area": row.storage_area or "",
        "item_code": code or "",
        "item_name": name or "",
        "item_spec": spec or "",
        "quantity": row.quantity,
        "unit": row.unit or "",
        "source_type": row.source_type or "",
        "source_delivery_id": row.source_delivery_id,
        "source_purchase_order_id": row.source_purchase_order_id,
        "source_purchase_receipt_id": row.source_purchase_receipt_id,
        "remark": row.remark or "",
        "created_at": row.created_at,
    }


def query_movement_rows_paginated(
    *,
    categories: List[str],
    start_date,
    end_date,
    category: str = "",
    direction: str = "",
    storage_area_kw: str = "",
    name_spec_kw: str = "",
    page: int = 1,
    per_page: int = 30,
) -> Tuple[List[dict[str, Any]], int]:
    """按与导出一致的条件分页查询库存进出明细。"""
    q = _movement_detail_query(
        categories=categories,
        start_date=start_date,
        end_date=end_date,
        category=category,
        direction=direction,
        storage_area_kw=storage_area_kw,
        name_spec_kw=name_spec_kw,
    )
    if q is None:
        return [], 0

    page = max(1, int(page))
    per_page = max(1, min(int(per_page), 100))
    total = q.order_by(None).count()
    rows = (
        q.order_by(InventoryMovement.biz_date.desc(), InventoryMovement.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return [_movement_detail_row_to_dict(r) for r in rows], int(total)


def query_movement_export_rows(
    *,
    categories: List[str],
    start_date,
    end_date,
    category: str = "",
    direction: str = "",
    storage_area_kw: str = "",
    name_spec_kw: str = "",
    limit: int = 50000,
) -> Tuple[List[dict[str, Any]], bool]:
    """查询库存进出明细导出行；返回 (rows, exceeded_limit)。"""
    q = _movement_detail_query(
        categories=categories,
        start_date=start_date,
        end_date=end_date,
        category=category,
        direction=direction,
        storage_area_kw=storage_area_kw,
        name_spec_kw=name_spec_kw,
    )
    if q is None:
        return [], False

    fetch_limit = max(1, int(limit)) + 1
    rows = (
        q.order_by(InventoryMovement.biz_date.desc(), InventoryMovement.id.desc())
        .limit(fetch_limit)
        .all()
    )
    exceeded = len(rows) > int(limit)
    if exceeded:
        rows = rows[: int(limit)]

    out = [_movement_detail_row_to_dict(r) for r in rows]
    return out, exceeded


def query_stock_aggregate(
    *,
    category: str = "",
    storage_area_kw: str = "",
    spec_kw: str = "",
    name_spec_kw: str = "",
    series: str = "",
    page: int = 1,
    per_page: int = 30,
) -> Tuple[List[dict[str, Any]], int]:
    """库存查询按 item 聚合；仓储区以逗号拼接展示。"""
    page = max(1, page)
    per_page = max(1, min(per_page, 100))
    offset = (page - 1) * per_page

    where_parts = ["1=1"]
    params: dict[str, Any] = {}

    if category in (INV_FINISHED, INV_SEMI, INV_MATERIAL):
        where_parts.append("b.category = :category")
        params["category"] = category
    if storage_area_kw.strip():
        where_parts.append("b.storage_area LIKE :sa_pat ESCAPE '\\\\'")
        params["sa_pat"] = _like_pat(storage_area_kw)
    if spec_kw.strip():
        where_parts.append(
            "((b.category = 'finished' AND b.product_id > 0 AND COALESCE(p.spec,'') LIKE :spec_pat ESCAPE '\\\\')"
            " OR (b.category IN ('semi','material') AND b.material_id > 0 AND COALESCE(sm.spec,'') LIKE :spec_pat ESCAPE '\\\\')"
            " OR b.category NOT IN ('finished','semi','material'))"
        )
        params["spec_pat"] = _like_pat(spec_kw)
    if name_spec_kw.strip():
        where_parts.append(
            "((b.category = 'finished' AND b.product_id > 0 AND ("
            "p.name LIKE :ns_pat ESCAPE '\\\\' OR COALESCE(p.spec,'') LIKE :ns_pat ESCAPE '\\\\' OR p.product_code LIKE :ns_pat ESCAPE '\\\\') )"
            " OR (b.category IN ('semi','material') AND b.material_id > 0 AND ("
            "sm.name LIKE :ns_pat ESCAPE '\\\\' OR COALESCE(sm.spec,'') LIKE :ns_pat ESCAPE '\\\\' OR sm.code LIKE :ns_pat ESCAPE '\\\\') )"
            " OR b.category NOT IN ('finished','semi','material'))"
        )
        params["ns_pat"] = _like_pat(name_spec_kw)
    series_trim = (series or "").strip()
    if series_trim:
        where_parts.append(
            "((b.category = 'finished' AND b.product_id > 0 AND TRIM(COALESCE(p.series,'')) = :series)"
            " OR (b.category IN ('semi','material') AND b.material_id > 0 AND TRIM(COALESCE(sm.series,'')) = :series))"
        )
        params["series"] = series_trim[:64]

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
LEFT JOIN semi_material sm ON b.material_id = sm.id AND b.category IN ('semi','material') AND b.material_id > 0
WHERE {where_sql}
"""

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
  COALESCE(p.product_code, sm.code) AS product_code,
  COALESCE(p.name, sm.name) AS product_name,
  COALESCE(p.spec, sm.spec) AS product_spec,
  COALESCE(p.series, sm.series) AS product_series
{inner}
ORDER BY b.storage_area, b.category, b.product_id, b.material_id
"""
    )
    rows = db.session.execute(data_sql, params).mappings().all()
    merged_map: dict[tuple[str, int, int], dict[str, Any]] = {}
    for r in rows:
        key = (
            str(r["category"]),
            int(r["product_id"] or 0),
            int(r["material_id"] or 0),
        )
        opening = Decimal(str(r["opening_qty"]))
        qi = Decimal(str(r["qty_in"]))
        qo = Decimal(str(r["qty_out"]))
        ps = r.get("product_series")
        product_series = (str(ps).strip() if ps is not None else "") or None
        storage_area = ((r["storage_area"] or "") if "storage_area" in r else "").strip()
        if key not in merged_map:
            merged_map[key] = {
                "category": r["category"],
                "product_id": r["product_id"],
                "material_id": r["material_id"],
                "storage_area": "",
                "opening_qty": Decimal("0"),
                "qty_in": Decimal("0"),
                "qty_out": Decimal("0"),
                "closing_qty": Decimal("0"),
                "product_code": r["product_code"],
                "product_name": r["product_name"],
                "product_spec": r["product_spec"],
                "product_series": product_series,
                "_areas": set(),
            }
        target = merged_map[key]
        target["opening_qty"] += opening
        target["qty_in"] += qi
        target["qty_out"] += qo
        target["closing_qty"] = target["opening_qty"] + target["qty_in"] - target["qty_out"]
        if storage_area:
            target["_areas"].add(storage_area)
        if not target.get("product_code") and r.get("product_code"):
            target["product_code"] = r.get("product_code")
        if not target.get("product_name") and r.get("product_name"):
            target["product_name"] = r.get("product_name")
        if (not target.get("product_spec")) and r.get("product_spec"):
            target["product_spec"] = r.get("product_spec")
        if (not target.get("product_series")) and product_series:
            target["product_series"] = product_series

    merged_rows = []
    for item in merged_map.values():
        areas = sorted(item.pop("_areas"))
        item["storage_area"] = ",".join(areas)
        merged_rows.append(item)

    merged_rows.sort(
        key=lambda x: (
            x.get("storage_area") or "",
            x.get("category") or "",
            int(x.get("product_id") or 0),
            int(x.get("material_id") or 0),
        )
    )
    total = len(merged_rows)
    paged = merged_rows[offset : offset + per_page]
    return paged, int(total)


def list_distinct_stock_series_options() -> List[str]:
    """成品、半成品、采购物料已维护的系列值（去重排序），供库存结存查询下拉筛选。"""
    labels: set[str] = set()
    for (raw,) in (
        db.session.query(Product.series)
        .filter(Product.series.isnot(None))
        .filter(func.trim(Product.series) != "")
        .distinct()
        .all()
    ):
        labels.add(str(raw).strip())
    for (raw,) in (
        db.session.query(SemiMaterial.series)
        .filter(SemiMaterial.kind.in_((INV_SEMI, INV_MATERIAL)))
        .filter(SemiMaterial.series.isnot(None))
        .filter(func.trim(SemiMaterial.series) != "")
        .distinct()
        .all()
    ):
        labels.add(str(raw).strip())
    return sorted(labels)


def _d_inv(val: Any) -> Decimal:
    if val is None:
        return Decimal(0)
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def _pid_mid_for_aggregate_item(category: str, item_id: int) -> Tuple[int, int]:
    """与生产测算一致：finished 用 product_id；semi/material 用 material_id。"""
    iid = int(item_id)
    if category == INV_FINISHED:
        return iid, 0
    return 0, iid


def ledger_qty_aggregate(category: str, item_id: int) -> Decimal:
    """
    台账结存（忽略仓储区）：期初 + 入 − 出，按 category + 成品/物料 id 汇总。
    """
    pid, mid = _pid_mid_for_aggregate_item(category, item_id)
    opening_qty = (
        db.session.query(
            func.coalesce(func.sum(InventoryOpeningBalance.opening_qty), 0)
        )
        .filter(
            InventoryOpeningBalance.category == category,
            InventoryOpeningBalance.product_id == pid,
            InventoryOpeningBalance.material_id == mid,
        )
        .scalar()
    )
    qty_in_out = (
        db.session.query(
            func.coalesce(
                func.sum(
                    case(
                        (
                            InventoryMovement.direction == "in",
                            InventoryMovement.quantity,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("qty_in"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            InventoryMovement.direction == "out",
                            InventoryMovement.quantity,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("qty_out"),
        )
        .filter(
            InventoryMovement.category == category,
            InventoryMovement.product_id == pid,
            InventoryMovement.material_id == mid,
        )
        .one()
    )
    return _d_inv(opening_qty) + _d_inv(qty_in_out.qty_in) - _d_inv(qty_in_out.qty_out)


def on_hand_for_movement_line(
    category: str, item_id: int, storage_area: Optional[str] = None
) -> Decimal:
    """
    库存录入行展示用结存。
    仓储区为空：与 ledger_qty_aggregate 相同（全仓合计）。
    仓储区非空：该 category + 成品/物料 + 仓储区 维度的期初 + 入 − 出。
    """
    area = (storage_area or "").strip()[:32]
    if not area:
        return ledger_qty_aggregate(category, item_id)
    if category not in (INV_FINISHED, INV_SEMI, INV_MATERIAL):
        return Decimal(0)
    pid, mid = _pid_mid_for_aggregate_item(category, item_id)
    opening_qty = (
        db.session.query(func.coalesce(func.sum(InventoryOpeningBalance.opening_qty), 0))
        .filter(
            InventoryOpeningBalance.category == category,
            InventoryOpeningBalance.product_id == pid,
            InventoryOpeningBalance.material_id == mid,
            InventoryOpeningBalance.storage_area == area,
        )
        .scalar()
    )
    qty_in_out = (
        db.session.query(
            func.coalesce(
                func.sum(
                    case(
                        (InventoryMovement.direction == "in", InventoryMovement.quantity),
                        else_=0,
                    )
                ),
                0,
            ).label("qty_in"),
            func.coalesce(
                func.sum(
                    case(
                        (InventoryMovement.direction == "out", InventoryMovement.quantity),
                        else_=0,
                    )
                ),
                0,
            ).label("qty_out"),
        )
        .filter(
            InventoryMovement.category == category,
            InventoryMovement.product_id == pid,
            InventoryMovement.material_id == mid,
            InventoryMovement.storage_area == area,
        )
        .one()
    )
    return _d_inv(opening_qty) + _d_inv(qty_in_out.qty_in) - _d_inv(qty_in_out.qty_out)


def reserved_active_qty_aggregate(category: str, item_id: int) -> Decimal:
    """全仓汇总：status=active 的预留数量合计。"""
    pid, mid = _pid_mid_for_aggregate_item(category, item_id)
    total = (
        db.session.query(func.coalesce(func.sum(InventoryReservation.reserved_qty), 0))
        .filter(
            InventoryReservation.status == RES_STATUS_ACTIVE,
            InventoryReservation.category == category,
            InventoryReservation.product_id == pid,
            InventoryReservation.material_id == mid,
        )
        .scalar()
    )
    return _d_inv(total)


def atp_for_item_aggregate(category: str, item_id: int) -> Decimal:
    """可用量 ATP = max(0, 台账结存 − 有效预留)。"""
    on_hand = ledger_qty_aggregate(category, item_id)
    reserved = reserved_active_qty_aggregate(category, item_id)
    atp = on_hand - reserved
    if atp < 0:
        return Decimal(0)
    return atp


def delete_reservations_for_preplan(*, preplan_id: int) -> int:
    """删除某预计划下全部预留（重算/改草稿/删除预计划前调用）。"""
    return int(
        db.session.query(InventoryReservation)
        .filter(
            InventoryReservation.ref_type == RES_REF_PREPLAN,
            InventoryReservation.ref_id == int(preplan_id),
        )
        .delete(synchronize_session=False)
    )


def rebuild_preplan_reservations_from_measure(
    *, preplan_id: int, created_by: int
) -> None:
    """
    按测算结果写入预留：工单父项 stock_covered + 子项 component_need.stock_covered，
    按 (category, product_id, material_id) 合并为若干行。
    调用前须已 delete_reservations_for_preplan（测算开头已删）。
    """
    from app.models import ProductionComponentNeed, ProductionWorkOrder

    totals: Dict[Tuple[str, int, int], Decimal] = defaultdict(lambda: Decimal(0))

    def _add(cat: str, pid: int, mid: int, qty: Any) -> None:
        q = _d_inv(qty)
        if q <= 0:
            return
        key = (cat, int(pid or 0), int(mid or 0))
        totals[key] += q

    for wo in (
        db.session.query(ProductionWorkOrder)
        .filter(ProductionWorkOrder.preplan_id == int(preplan_id))
        .all()
    ):
        sc = wo.stock_covered_qty
        pk = (wo.parent_kind or "").strip()
        if pk == INV_FINISHED:
            _add(INV_FINISHED, wo.parent_product_id, 0, sc)
        elif pk == INV_SEMI:
            _add(INV_SEMI, 0, wo.parent_material_id, sc)
        elif pk == INV_MATERIAL:
            _add(INV_MATERIAL, 0, wo.parent_material_id, sc)

    for n in (
        db.session.query(ProductionComponentNeed)
        .filter(ProductionComponentNeed.preplan_id == int(preplan_id))
        .all()
    ):
        sc = n.stock_covered_qty
        ck = (n.child_kind or "").strip()
        if ck == INV_FINISHED:
            _add(INV_FINISHED, n.child_material_id, 0, sc)
        elif ck == INV_SEMI:
            _add(INV_SEMI, 0, n.child_material_id, sc)
        else:
            _add(INV_MATERIAL, 0, n.child_material_id, sc)

    for (cat, pid, mid), qty in totals.items():
        if qty <= 0:
            continue
        db.session.add(
            InventoryReservation(
                category=cat,
                product_id=pid,
                material_id=mid,
                storage_area="",
                ref_type=RES_REF_PREPLAN,
                ref_id=int(preplan_id),
                reserved_qty=qty,
                status=RES_STATUS_ACTIVE,
                remark=None,
                created_by=int(created_by),
            )
        )
