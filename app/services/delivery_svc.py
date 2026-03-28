"""送货单创建逻辑，供 Web 表单与 OpenClaw API 共用。"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional, Tuple

from sqlalchemy import func as sa_func

from app import db
from app.models import (
    Customer,
    Company,
    SalesOrder,
    OrderItem,
    Delivery,
    DeliveryItem,
    ExpressCompany,
    ExpressWaybill,
)
from app.utils.billing_period import period_start_containing, next_period_start


def _next_delivery_no_for_customer(customer_id: int, delivery_date: date) -> str:
    """主体送货编号前缀 + YYYYMMDD + 业务周期内序号（4 位）。"""
    cust = db.session.get(Customer, customer_id)
    if not cust:
        return f"DL{delivery_date.strftime('%Y%m%d')}0001"
    company = (
        db.session.query(Company)
        .filter(Company.id == cust.company_id)
        .with_for_update()
        .first()
    )
    if not company:
        return f"DL{delivery_date.strftime('%Y%m%d')}0001"
    cycle = int(company.billing_cycle_day or 1)
    ps = period_start_containing(delivery_date, cycle)
    pe = next_period_start(ps, cycle)
    prefix = (company.delivery_no_prefix or company.code or "DL").strip()
    n = (
        db.session.query(sa_func.count(Delivery.id))
        .join(Customer, Delivery.customer_id == Customer.id)
        .filter(
            Customer.company_id == company.id,
            Delivery.delivery_date >= ps,
            Delivery.delivery_date < pe,
        )
        .scalar()
    )
    seq = (n or 0) + 1
    return f"{prefix}{delivery_date.strftime('%Y%m%d')}{seq:04d}"


def _allocate_waybill(express_company_id: int, delivery_id: int) -> Optional[ExpressWaybill]:
    w = (
        db.session.query(ExpressWaybill)
        .filter(
            ExpressWaybill.express_company_id == express_company_id,
            ExpressWaybill.status == "available",
        )
        .order_by(ExpressWaybill.id)
        .with_for_update()
        .first()
    )
    if not w:
        return None
    w.status = "used"
    w.delivery_id = delivery_id
    w.used_at = datetime.now()
    return w


def _allocate_waybill_by_no(
    express_company_id: int, delivery_id: int, waybill_no: str
) -> Optional[ExpressWaybill]:
    no = (waybill_no or "").strip()
    if not no:
        return None
    w = (
        db.session.query(ExpressWaybill)
        .filter(
            ExpressWaybill.express_company_id == express_company_id,
            ExpressWaybill.waybill_no == no,
            ExpressWaybill.status == "available",
        )
        .with_for_update()
        .first()
    )
    if not w:
        return None
    w.status = "used"
    w.delivery_id = delivery_id
    w.used_at = datetime.now()
    return w


def get_pending_order_items(customer_id: int, order_id: Optional[int] = None):
    """该客户下待发货订单行（可选按 order_id 过滤）。返回与 routes 中 _pending_order_items 一致结构。"""
    q = (
        db.session.query(OrderItem, SalesOrder)
        .join(SalesOrder, OrderItem.order_id == SalesOrder.id)
        .filter(SalesOrder.customer_id == customer_id)
    )
    if order_id:
        q = q.filter(OrderItem.order_id == order_id)
    items = q.order_by(SalesOrder.order_no, OrderItem.id).all()
    item_ids = [it.id for it, _ in items if it.id]
    if item_ids:
        rows = (
            db.session.query(
                DeliveryItem.order_item_id,
                sa_func.coalesce(sa_func.sum(DeliveryItem.quantity), 0),
            )
            .join(Delivery, DeliveryItem.delivery_id == Delivery.id)
            .filter(
                Delivery.status == "shipped",
                DeliveryItem.order_item_id.in_(item_ids),
            )
            .group_by(DeliveryItem.order_item_id)
            .all()
        )
        delivered_map = {r[0]: float(r[1] or 0) for r in rows}
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


def get_default_express_company() -> Optional[ExpressCompany]:
    """默认快递：顺丰。按 code 或 name 匹配（SF、顺丰等）。"""
    for code in ("SF", "顺丰", "SHUNFENG"):
        ec = (
            ExpressCompany.query.filter(
                ExpressCompany.is_active.is_(True),
                sa_func.upper(ExpressCompany.code) == code.upper(),
            )
            .first()
        )
        if ec:
            return ec
    ec = (
        ExpressCompany.query.filter(
            ExpressCompany.is_active.is_(True),
            ExpressCompany.code != "LEGACY",
            ExpressCompany.name.like("%顺丰%"),
        )
        .first()
    )
    return ec


def _is_self_delivery(data: dict[str, Any]) -> bool:
    v = data.get("self_delivery")
    if v is True:
        return True
    if isinstance(v, (int, float)) and int(v) == 1:
        return True
    if isinstance(v, str) and v.strip().lower() in ("1", "true", "yes", "on"):
        return True
    return False


def create_delivery_from_data(data: dict[str, Any]) -> Tuple[Optional[Delivery], Optional[str]]:
    """
    根据字典数据创建送货单。
    data: customer_id, lines: [{ order_item_id, quantity }],
          self_delivery?（True 表示自配送，不占单号池，express_company_id 置空）,
          express_company_id?, waybill_no?（非自配送：非空时先尝试占用池中可用同号，否则手写落库不入池）,
          delivery_date?, driver?, plate_no?, remark?
    非自配送且未传 express_company_id 时使用默认顺丰并占号；缺省 delivery_date 为今天。
    非自配送时 waybill_no 为空则按 id 顺序自动占号；非空则池内可用则占号，否则仅保存单号（express_waybill_id 为空）。
    返回 (delivery, None) 成功；(None, error_message) 失败。
    """
    customer_id = data.get("customer_id")
    if not customer_id:
        return None, "请选择客户。"

    self_delivery = _is_self_delivery(data)
    express_company_id: Optional[int] = None

    if self_delivery:
        express_company_id = None
    else:
        express_company_id = data.get("express_company_id")
        if not express_company_id:
            default_ec = get_default_express_company()
            if not default_ec:
                return None, "未配置默认快递（顺丰），请指定 express_company_id。"
            express_company_id = default_ec.id

        ec = ExpressCompany.query.get(express_company_id)
        if not ec or ec.code == "LEGACY" or not ec.is_active:
            return None, "请选择有效的快递公司。"

    delivery_date_str = data.get("delivery_date")
    delivery_date = date.today()
    if delivery_date_str:
        try:
            delivery_date = date.fromisoformat(
                delivery_date_str if isinstance(delivery_date_str, str) else str(delivery_date_str)
            )
        except ValueError:
            pass

    driver = (data.get("driver") or "").strip() or None
    plate_no = (data.get("plate_no") or "").strip() or None
    remark = (data.get("remark") or "").strip() or None

    lines = data.get("lines") or []
    if not isinstance(lines, list) or not lines:
        return None, "请至少选择一行并填写本次送货数量。"

    order_item_ids = []
    quantities = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        try:
            oi_id = int(line.get("order_item_id") or 0)
        except (TypeError, ValueError):
            continue
        try:
            qty = Decimal(str(line.get("quantity") or 0))
        except Exception:
            qty = Decimal(0)
        if oi_id and qty > 0:
            order_item_ids.append(oi_id)
            quantities.append(qty)

    if not order_item_ids or not quantities:
        return None, "请至少选择一行并填写本次送货数量。"

    delivery_no = _next_delivery_no_for_customer(customer_id, delivery_date)
    delivery = Delivery(
        delivery_no=delivery_no,
        delivery_date=delivery_date,
        customer_id=customer_id,
        express_company_id=express_company_id,
        status="created",
        driver=driver,
        plate_no=plate_no,
        remark=remark,
    )
    db.session.add(delivery)
    db.session.flush()

    if not self_delivery and express_company_id is not None:
        prefer = (data.get("waybill_no") or "").strip()
        if prefer:
            if len(prefer) > 64:
                db.session.rollback()
                return None, "快递单号不能超过 64 个字符。"
            w = _allocate_waybill_by_no(express_company_id, delivery.id, prefer)
            if w:
                delivery.express_waybill_id = w.id
                delivery.waybill_no = w.waybill_no
            else:
                delivery.express_waybill_id = None
                delivery.waybill_no = prefer
        else:
            w = _allocate_waybill(express_company_id, delivery.id)
            if not w:
                db.session.rollback()
                return None, "该快递公司暂无可用单号，请先录入单号池。"
            delivery.express_waybill_id = w.id
            delivery.waybill_no = w.waybill_no

    for i, oi_id in enumerate(order_item_ids):
        qty = quantities[i] if i < len(quantities) else Decimal(0)
        if qty <= 0:
            continue
        item = OrderItem.query.get(oi_id)
        if not item:
            continue
        di = DeliveryItem(
            delivery_id=delivery.id,
            order_item_id=item.id,
            order_id=item.order_id,
            product_name=item.product_name,
            customer_material_no=item.customer_material_no,
            quantity=qty,
            unit=item.unit,
        )
        db.session.add(di)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return None, "保存送货单失败，请重试。"
    return delivery, None
