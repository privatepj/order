"""订单创建/更新逻辑，供 Web 表单与 OpenClaw API 共用。"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import (
    Customer,
    Company,
    SalesOrder,
    OrderItem,
    Delivery,
    DeliveryItem,
    CustomerProduct,
)
from app.utils.billing_period import period_bounds_containing
from app.utils.decimal_scale import json_decimal, quantize_decimal
from app.utils.payment_type import normalize_payment_type, payment_type_label
from app.services.orchestrator_contracts import EVENT_ORDER_CHANGED


_SPARE_RATIO = Decimal("0.003")
_SPARE_ROUND_BASE = Decimal("10")


def _coerce_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return int(val) != 0
    if val is None:
        return False
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def calc_spare_quantity(main_qty: Any) -> Decimal:
    try:
        qty = Decimal(str(main_qty or 0))
    except Exception:
        qty = Decimal(0)
    if qty <= 0:
        return Decimal(0)
    raw = qty * _SPARE_RATIO
    if raw <= 0:
        return Decimal(0)
    if raw < _SPARE_ROUND_BASE:
        return _SPARE_ROUND_BASE
    rounded_units = (raw / _SPARE_ROUND_BASE).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return rounded_units * _SPARE_ROUND_BASE


def _parse_order_rows(items: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return rows
    for r in items:
        if not isinstance(r, dict):
            continue
        try:
            cp_id = (
                int(r["customer_product_id"])
                if r.get("customer_product_id") is not None
                else None
            )
        except (TypeError, ValueError, KeyError):
            cp_id = None
        try:
            qty = Decimal(str(r.get("quantity") or 0))
        except Exception:
            qty = Decimal(0)
        oi_id = None
        if r.get("order_item_id") is not None:
            try:
                oi_id = int(r["order_item_id"])
            except (TypeError, ValueError):
                pass
        if cp_id and qty > 0:
            rows.append(
                {
                    "customer_product_id": cp_id,
                    "quantity": qty,
                    "is_sample": _coerce_bool(r.get("is_sample")),
                    "is_spare": _coerce_bool(r.get("is_spare")),
                    "order_item_id": oi_id,
                }
            )
    return rows


def _with_auto_spare_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        expanded.append(row)
        should_auto_add = (
            row["order_item_id"] is None
            and not row["is_spare"]
            and row["quantity"] > 0
        )
        if not should_auto_add:
            continue
        next_row = rows[idx + 1] if idx + 1 < len(rows) else None
        has_immediate_spare = bool(
            next_row
            and next_row["is_spare"]
            and next_row["customer_product_id"] == row["customer_product_id"]
        )
        if has_immediate_spare:
            continue
        spare_qty = calc_spare_quantity(row["quantity"])
        if spare_qty <= 0:
            continue
        expanded.append(
            {
                "customer_product_id": row["customer_product_id"],
                "quantity": spare_qty,
                "is_sample": False,
                "is_spare": True,
                "order_item_id": None,
            }
        )
    return expanded


def _next_order_no_for_customer(customer_id: int) -> str:
    """按客户所属主体的前缀、业务月、当天 MMDD 生成序号（行锁 company 防并发）。"""
    today = date.today()
    cust = db.session.get(Customer, customer_id)
    if not cust:
        return f"SO{today.strftime('%Y%m%d')}001"
    company = (
        db.session.query(Company)
        .filter(Company.id == cust.company_id)
        .with_for_update()
        .first()
    )
    if not company:
        return f"SO{today.strftime('%Y%m%d')}001"
    cycle = int(company.billing_cycle_day or 1)
    prefix = (company.order_no_prefix or company.code or "SO").strip()
    start_dt, end_dt = period_bounds_containing(today, cycle)
    mmdd = today.strftime("%m%d")
    n = (
        db.session.query(func.count(SalesOrder.id))
        .join(Customer, SalesOrder.customer_id == Customer.id)
        .filter(
            Customer.company_id == company.id,
            SalesOrder.created_at >= start_dt,
            SalesOrder.created_at < end_dt,
        )
        .scalar()
    )
    seq = (n or 0) + 1
    # 并发/历史数据兜底：候选若已存在则继续 seq++ 查重
    while True:
        candidate = f"{prefix}{mmdd}{seq:03d}"
        if not SalesOrder.query.filter_by(order_no=candidate).first():
            return candidate
        seq += 1


def _shipped_qty_by_order_item_ids(order_item_ids: list[int]) -> dict[int, Decimal]:
    """仅统计送货单状态为 shipped 的明细数量。"""
    if not order_item_ids:
        return {}
    rows = (
        db.session.query(
            DeliveryItem.order_item_id,
            func.coalesce(func.sum(DeliveryItem.quantity), 0),
        )
        .join(Delivery, DeliveryItem.delivery_id == Delivery.id)
        .filter(
            Delivery.status == "shipped",
            DeliveryItem.order_item_id.in_(order_item_ids),
        )
        .group_by(DeliveryItem.order_item_id)
        .all()
    )
    return {r[0]: Decimal(str(r[1] or 0)) for r in rows}


def _order_status_from_items(order: SalesOrder) -> str:
    items = list(order.items or [])
    if not items:
        return "pending"
    item_ids = [i.id for i in items if i.id]
    delivered_map = _shipped_qty_by_order_item_ids(item_ids)
    all_delivered = True
    any_delivered = False
    for item in items:
        need = Decimal(str(item.quantity or 0))
        if need <= 0:
            continue
        delivered = delivered_map.get(item.id, Decimal(0))
        if delivered > 0:
            any_delivered = True
        if delivered < need:
            all_delivered = False
    if all_delivered and any_delivered:
        return "delivered"
    if any_delivered:
        return "partial"
    return "pending"


def recompute_orders_status_for_delivery(delivery_id: int) -> None:
    """根据当前库中已发(shipped)送货数量，重算本送货单涉及的所有订单状态。不 commit。"""
    rows = (
        db.session.query(DeliveryItem.order_id)
        .filter(DeliveryItem.delivery_id == delivery_id)
        .distinct()
        .all()
    )
    order_ids = [r[0] for r in rows if r[0] is not None]
    for oid in order_ids:
        order = (
            SalesOrder.query.options(joinedload(SalesOrder.items))
            .filter(SalesOrder.id == oid)
            .first()
        )
        if order:
            order.status = _order_status_from_items(order)
            db.session.add(order)


def recompute_orders_status_for_order_ids(order_ids: list[int]) -> None:
    """根据当前库中已发(shipped)送货数量，重算指定订单状态。不 commit。"""
    if not order_ids:
        return
    unique_ids = sorted({int(x) for x in order_ids if x})
    for oid in unique_ids:
        order = (
            SalesOrder.query.options(joinedload(SalesOrder.items))
            .filter(SalesOrder.id == oid)
            .first()
        )
        if order:
            order.status = _order_status_from_items(order)
            db.session.add(order)


def _order_item_ids_with_delivery(order_id: Optional[int]) -> set:
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


def _load_cp_for_order(customer_id: int, cp_id: int):
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


def create_order_from_data(
    data: dict[str, Any],
    existing_order: Optional[SalesOrder] = None,
) -> Tuple[Optional[SalesOrder], Optional[str]]:
    """
    根据字典数据创建或更新订单。
    data: customer_id, customer_order_no?, salesperson?, order_date?, required_date?,
          payment_type?, remark?, items: [{ customer_product_id, quantity, is_sample?, is_spare? }]
    返回 (order, None) 成功；(None, error_message) 失败。
    """
    customer_id = data.get("customer_id")
    if not customer_id:
        return None, "请选择客户。"

    customer_order_no = (data.get("customer_order_no") or "").strip() or None
    salesperson = (data.get("salesperson") or "GaoMeiHua").strip()
    order_date_str = data.get("order_date")
    required_date_str = data.get("required_date")
    remark = (data.get("remark") or "").strip() or None
    payment_type = normalize_payment_type(data.get("payment_type"))

    items = data.get("items") or []
    if not isinstance(items, list):
        return None, "订单行格式错误。"

    # 解析行：customer_product_id, quantity, is_sample?, order_item_id?（编辑时）
    rows = _with_auto_spare_rows(_parse_order_rows(items))

    if existing_order is None and not rows:
        return None, "请至少选择一行客户产品并填写数量。"

    for row in rows:
        if row["quantity"] > 0 and not row["customer_product_id"]:
            return None, "存在已填数量但未选择产品的行，请检查。"

    order = existing_order

    if order is None:
        order = SalesOrder()
        order.order_no = _next_order_no_for_customer(customer_id)

    order.customer_id = customer_id
    order.customer_order_no = customer_order_no
    order.salesperson = salesperson or "GaoMeiHua"
    order.order_date = None
    if order_date_str:
        try:
            order.order_date = date.fromisoformat(
                order_date_str if isinstance(order_date_str, str) else str(order_date_str)
            )
        except ValueError:
            pass
    order.required_date = None
    if required_date_str:
        try:
            order.required_date = date.fromisoformat(
                required_date_str if isinstance(required_date_str, str) else str(required_date_str)
            )
        except ValueError:
            pass
    order.remark = remark
    order.payment_type = payment_type

    # 并发下可能出现 order_no 唯一键冲突：在插入 sales_order 时重试 flush。
    max_tries = 3
    db.session.add(order)
    for attempt in range(max_tries):
        try:
            db.session.flush()
            break
        except IntegrityError:
            db.session.rollback()
            db.session.expunge_all()
            if existing_order is None:
                order.order_no = _next_order_no_for_customer(customer_id)
            db.session.add(order)
            if attempt == max_tries - 1:
                return None, "保存失败，请重试（订单号可能冲突）。"

    if order.id and existing_order:
        kept_ids = {r["order_item_id"] for r in rows if r["order_item_id"]}
        for oi in list(order.items):
            has_delivery = (
                db.session.query(DeliveryItem)
                .filter(DeliveryItem.order_item_id == oi.id)
                .first()
                is not None
            )
            if has_delivery:
                continue
            if oi.id not in kept_ids:
                db.session.delete(oi)

    for row in rows:
        cp_id = row["customer_product_id"]
        qty = row["quantity"]
        is_sample = row["is_sample"]
        is_spare = row["is_spare"]
        oi_id = row["order_item_id"]
        cp, p = _load_cp_for_order(customer_id, cp_id)
        if not cp or not p:
            db.session.rollback()
            return None, "存在无效的客户产品行，请重新选择。"
        pr = cp.price
        if is_sample or is_spare:
            pr = Decimal("0")
        if oi_id and order.id:
            item = OrderItem.query.filter_by(id=oi_id, order_id=order.id).first()
            if item:
                has_delivery = (
                    db.session.query(DeliveryItem)
                    .filter(DeliveryItem.order_item_id == item.id)
                    .first()
                    is not None
                )
                if has_delivery:
                    item.quantity = qty
                    item.compute_amount()
                    continue
                item.customer_product_id = cp_id
                item.product_name = p.name
                item.product_spec = p.spec
                item.customer_material_no = cp.customer_material_no
                item.quantity = qty
                item.unit = cp.unit or p.base_unit
                item.is_sample = bool(is_sample)
                item.is_spare = bool(is_spare)
                item.price = pr
                item.compute_amount()
                continue
        item = OrderItem(
            order_id=order.id,
            customer_product_id=cp_id,
            product_name=p.name,
            product_spec=p.spec,
            customer_material_no=cp.customer_material_no,
            quantity=qty,
            unit=cp.unit or p.base_unit,
            price=pr,
            is_sample=bool(is_sample),
            is_spare=bool(is_spare),
        )
        item.compute_amount()
        db.session.add(item)

    db.session.flush()
    order.status = _order_status_from_items(order)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return None, "保存失败，请重试（订单号可能冲突）。"
    from app.services import orchestrator_engine

    orchestrator_engine.emit_event(
        event_type=EVENT_ORDER_CHANGED,
        biz_key=f"order:{order.id}",
        payload={
            "order_id": int(order.id),
            "source_id": int(order.id),
            "version": int(order.updated_at.timestamp()) if order.updated_at else int(order.id),
            "source": "order_svc.create_order_from_data",
        },
    )
    db.session.commit()
    return order, None


def preview_order_create(data: dict[str, Any]) -> Tuple[Optional[str], dict[str, Any]]:
    """
    不写库：校验新建订单请求并返回供用户确认的摘要。
    返回 (error_message, summary)；无错误时 error_message 为 None。
    """
    summary: dict[str, Any] = {}
    customer_id = data.get("customer_id")
    if not customer_id:
        return "请选择客户。", summary

    cust = db.session.get(Customer, customer_id)
    if not cust:
        return "客户不存在。", summary

    summary["customer_id"] = int(customer_id)
    summary["customer_label"] = (cust.short_code or cust.customer_code or cust.name or str(cust.id))
    summary["order_no_note"] = "保存时由系统按经营主体与日期规则自动生成，请勿自拟。"

    customer_order_no = (data.get("customer_order_no") or "").strip() or None
    salesperson = (data.get("salesperson") or "GaoMeiHua").strip()
    order_date_str = data.get("order_date")
    required_date_str = data.get("required_date")
    remark = (data.get("remark") or "").strip() or None
    payment_type = normalize_payment_type(data.get("payment_type"))

    summary["customer_order_no"] = customer_order_no
    summary["salesperson"] = salesperson or "GaoMeiHua"
    summary["order_date"] = order_date_str
    summary["required_date"] = required_date_str
    summary["remark"] = remark
    summary["payment_type"] = payment_type
    summary["payment_type_label"] = payment_type_label(payment_type)

    items = data.get("items") or []
    if not isinstance(items, list):
        return "订单行格式错误。", summary

    rows = _with_auto_spare_rows(_parse_order_rows(items))

    if not rows:
        return "请至少选择一行客户产品并填写数量。", summary

    line_summaries = []
    for row in rows:
        cp_id = row["customer_product_id"]
        qty = row["quantity"]
        is_sample = row["is_sample"]
        is_spare = row["is_spare"]
        cp, p = _load_cp_for_order(int(customer_id), cp_id)
        if not cp or not p:
            return "存在无效的客户产品行，请重新选择。", summary
        pr = cp.price
        if is_sample or is_spare:
            pr = Decimal("0")
        amt = quantize_decimal(qty * pr) if pr is not None else None
        line_summaries.append({
            "customer_product_id": cp_id,
            "product_code": p.product_code or "",
            "product_name": p.name or "",
            "product_spec": (p.spec or "")[:128],
            "quantity": json_decimal(qty),
            "is_sample": is_sample,
            "is_spare": is_spare,
            "unit": cp.unit or p.base_unit or "",
            "unit_price": json_decimal(pr) if pr is not None else None,
            "line_amount": json_decimal(amt) if amt is not None else None,
        })

    summary["items"] = line_summaries
    return None, summary
