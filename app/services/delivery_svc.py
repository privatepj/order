"""送货单创建逻辑，供 Web 表单与 OpenClaw API 共用。"""
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import func as sa_func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

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


def effective_customer_material_no(oi: OrderItem) -> str:
    """客户料号：优先当前客户产品主数据，否则用订单行快照（下单后补录/修改客户产品料号仍可带出）。"""
    if oi.customer_product:
        return (oi.customer_product.customer_material_no or oi.customer_material_no or "").strip()
    return (oi.customer_material_no or "").strip()


def _max_delivery_seq_suffix_for_company_period(
    company_id: int, prefix: str, ps: date, pe: date
) -> int:
    """业务周期内，以前缀开头且末四位为数字的送货单号之最大尾号；无可解析则 0。"""
    pl = len(prefix)
    min_len = pl + 8 + 4
    rows = (
        db.session.query(Delivery.delivery_no)
        .join(Customer, Delivery.customer_id == Customer.id)
        .filter(
            Customer.company_id == company_id,
            Delivery.delivery_date >= ps,
            Delivery.delivery_date < pe,
        )
        .all()
    )
    best = 0
    for (dno,) in rows:
        if not dno or len(dno) < min_len:
            continue
        if not dno.startswith(prefix):
            continue
        tail = dno[-4:]
        if not tail.isdigit():
            continue
        v = int(tail)
        if v > best:
            best = v
    return best


def _is_delivery_no_duplicate_integrity_error(exc: IntegrityError) -> bool:
    raw = str(exc.orig or exc).lower()
    return "delivery_no" in raw or "uk_delivery_no" in raw


def _next_free_delivery_no(prefix: str, date_part: str, start_seq: int) -> str:
    """从 start_seq 起递增，直到库中无同名 delivery_no。"""
    seq = start_seq
    while True:
        candidate = f"{prefix}{date_part}{seq:04d}"
        if not Delivery.query.filter_by(delivery_no=candidate).first():
            return candidate
        seq += 1


def _next_delivery_no_for_customer(customer_id: int, delivery_date: date) -> str:
    """主体送货编号前缀 + YYYYMMDD + 业务周期内序号（4 位）；序号取周期内已有单号尾号 max+1。"""
    date_part = delivery_date.strftime("%Y%m%d")
    cust = db.session.get(Customer, customer_id)
    if not cust:
        return _next_free_delivery_no("DL", date_part, 1)
    company = (
        db.session.query(Company)
        .filter(Company.id == cust.company_id)
        .with_for_update()
        .first()
    )
    if not company:
        return _next_free_delivery_no("DL", date_part, 1)
    cycle = int(company.billing_cycle_day or 1)
    ps = period_start_containing(delivery_date, cycle)
    pe = next_period_start(ps, cycle)
    prefix = (company.delivery_no_prefix or company.code or "DL").strip()
    max_seq = _max_delivery_seq_suffix_for_company_period(company.id, prefix, ps, pe)
    return _next_free_delivery_no(prefix, date_part, max_seq + 1)


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


def order_item_shipped_and_in_transit_maps(
    order_item_ids: list[int],
) -> Tuple[Dict[int, float], Dict[int, float]]:
    """各订单行：已发(shipped) 数量、待发(created) 占用数量。"""
    return (
        _delivery_qty_by_order_item_ids(order_item_ids, ("shipped",)),
        _delivery_qty_by_order_item_ids(order_item_ids, ("created",)),
    )


def _delivery_qty_by_order_item_ids(
    order_item_ids: list[int], statuses: Tuple[str, ...]
) -> Dict[int, float]:
    """按订单行汇总送货明细数量（仅统计给定送货单状态）。"""
    if not order_item_ids:
        return {}
    rows = (
        db.session.query(
            DeliveryItem.order_item_id,
            sa_func.coalesce(sa_func.sum(DeliveryItem.quantity), 0),
        )
        .join(Delivery, DeliveryItem.delivery_id == Delivery.id)
        .filter(
            Delivery.status.in_(list(statuses)),
            DeliveryItem.order_item_id.in_(order_item_ids),
        )
        .group_by(DeliveryItem.order_item_id)
        .all()
    )
    return {r[0]: float(r[1] or 0) for r in rows}


def get_pending_order_items(customer_id: int, order_id: Optional[int] = None):
    """该客户下还可继续开送货单的订单行（可选按 order_id 过滤）。

    已占用 = 状态为已发(shipped) + 待发(created) 的送货单行数量之和；失效(expired) 不计入。
    delivered_qty：仅已发数量；in_transit_qty：仅待发数量；remaining_qty = 订单行数量 - 已占用。
    """
    q = (
        db.session.query(OrderItem, SalesOrder)
        .join(SalesOrder, OrderItem.order_id == SalesOrder.id)
        .filter(SalesOrder.customer_id == customer_id)
        .options(joinedload(OrderItem.customer_product))
    )
    if order_id:
        q = q.filter(OrderItem.order_id == order_id)
    items = q.order_by(SalesOrder.order_no, OrderItem.id).all()
    item_ids = [it.id for it, _ in items if it.id]
    shipped_map = _delivery_qty_by_order_item_ids(item_ids, ("shipped",))
    in_transit_map = _delivery_qty_by_order_item_ids(item_ids, ("created",))
    result = []
    for item, order in items:
        shipped = shipped_map.get(item.id, 0.0)
        in_transit = in_transit_map.get(item.id, 0.0)
        need = float(item.quantity or 0)
        allocated = shipped + in_transit
        remaining = max(0, need - allocated)
        if remaining > 0:
            result.append(
                {
                    "order_item": item,
                    "order": order,
                    "delivered_qty": shipped,
                    "in_transit_qty": in_transit,
                    "remaining_qty": remaining,
                }
            )
    return result


def pending_remaining_qty_by_order_item_id(
    customer_id: int, order_id: Optional[int] = None
) -> Dict[int, Decimal]:
    """与 get_pending_order_items 相同的待发剩余量，便于建单前校验。仅含 remaining>0 的行。"""
    pending = get_pending_order_items(customer_id, order_id)
    out: Dict[int, Decimal] = {}
    for x in pending:
        oi = x["order_item"]
        if oi.id:
            out[oi.id] = Decimal(str(x["remaining_qty"]))
    return out


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


def preview_delivery_create(data: dict[str, Any]) -> Tuple[Optional[str], dict[str, Any]]:
    """
    不写库：校验创建送货单参数并返回摘要，供用户确认后再 POST /deliveries。
    返回 (error_message, summary)。
    """
    summary: Dict[str, Any] = {}
    customer_id = data.get("customer_id")
    if not customer_id:
        return "请选择客户。", summary

    cust = db.session.get(Customer, customer_id)
    if not cust:
        return "客户不存在。", summary

    summary["customer_id"] = int(customer_id)
    summary["customer_label"] = (cust.short_code or cust.customer_code or cust.name or str(cust.id))

    self_delivery = _is_self_delivery(data)
    express_company_id: Optional[int] = None
    ec: Optional[ExpressCompany] = None

    if self_delivery:
        express_company_id = None
    else:
        express_company_id = data.get("express_company_id")
        if not express_company_id:
            default_ec = get_default_express_company()
            if not default_ec:
                return "未配置默认快递（顺丰），请指定 express_company_id。", summary
            express_company_id = default_ec.id

        ec = ExpressCompany.query.get(express_company_id)
        if not ec or ec.code == "LEGACY" or not ec.is_active:
            return "请选择有效的快递公司。", summary

    delivery_date_str = data.get("delivery_date")
    delivery_date = date.today()
    if delivery_date_str:
        try:
            delivery_date = date.fromisoformat(
                delivery_date_str if isinstance(delivery_date_str, str) else str(delivery_date_str)
            )
        except ValueError:
            pass

    summary["delivery_date"] = delivery_date.isoformat()
    summary["self_delivery"] = self_delivery
    summary["express_company_id"] = express_company_id
    summary["express_company_name"] = (ec.name if ec else None)
    prefer_wb = (data.get("waybill_no") or "").strip()
    summary["waybill_no"] = prefer_wb or None
    summary["waybill_note"] = (
        "自配送不占运单池"
        if self_delivery
        else ("将尝试占用单号池中与此相同单号" if prefer_wb else "保存时将自动从单号池顺序占号")
    )
    summary["driver"] = (data.get("driver") or "").strip() or None
    summary["plate_no"] = (data.get("plate_no") or "").strip() or None
    summary["remark"] = (data.get("remark") or "").strip() or None
    summary["delivery_no_note"] = "保存时由系统按主体规则自动生成。"

    lines = data.get("lines") or []
    if not isinstance(lines, list) or not lines:
        return "请至少选择一行并填写本次送货数量。", summary

    order_item_ids = []
    quantities = []
    qty_by_oi: dict[int, Decimal] = defaultdict(Decimal)
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
            qty_by_oi[oi_id] += qty

    if not order_item_ids:
        return "请至少选择一行并填写本次送货数量。", summary

    order_id_filter: Optional[int] = None
    raw_oid = data.get("order_id")
    if raw_oid is not None and str(raw_oid).strip() != "":
        try:
            order_id_filter = int(raw_oid)
        except (TypeError, ValueError):
            return "order_id 格式无效。", summary
        so_chk = db.session.get(SalesOrder, order_id_filter)
        if not so_chk or so_chk.customer_id != customer_id:
            return "订单不属于所选客户。", summary
        summary["order_id"] = order_id_filter
        summary["order_no"] = so_chk.order_no

    remaining_map = pending_remaining_qty_by_order_item_id(int(customer_id), order_id_filter)
    line_out = []
    for oi_id, total_need in qty_by_oi.items():
        item = db.session.get(OrderItem, oi_id)
        if not item:
            return "存在无效的订单行。", summary
        order_row = db.session.get(SalesOrder, item.order_id)
        if not order_row or order_row.customer_id != customer_id:
            return "订单行与所选客户不一致。", summary
        if order_id_filter is not None and item.order_id != order_id_filter:
            return "订单行不属于指定的订单。", summary
        rem = remaining_map.get(oi_id, Decimal(0))
        if rem <= 0:
            return "所选订单行暂无待发数量（已发与待发送货单已占满订单数量）。", summary
        if total_need > rem:
            return "本次送货数量超过可发剩余（已含待发送货单占用，请核对或调整待发单）。", summary
        line_out.append({
            "order_item_id": oi_id,
            "quantity": float(total_need),
            "remaining_before": float(rem),
            "order_id": order_row.id,
            "order_no": order_row.order_no,
            "product_name": item.product_name or "",
            "product_spec": (item.product_spec or "")[:128],
        })

    summary["lines"] = line_out
    return None, summary


def create_delivery_from_data(data: dict[str, Any]) -> Tuple[Optional[Delivery], Optional[str]]:
    """
    根据字典数据创建送货单。
    data: customer_id, lines: [{ order_item_id, quantity }],
          order_id?（若传则所有行须属于该订单且订单须属于该客户）,
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
    qty_by_oi: dict[int, Decimal] = defaultdict(Decimal)
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
            qty_by_oi[oi_id] += qty

    if not order_item_ids or not quantities:
        return None, "请至少选择一行并填写本次送货数量。"

    order_id_filter: Optional[int] = None
    raw_oid = data.get("order_id")
    if raw_oid is not None and str(raw_oid).strip() != "":
        try:
            order_id_filter = int(raw_oid)
        except (TypeError, ValueError):
            return None, "order_id 格式无效。"
        so_chk = db.session.get(SalesOrder, order_id_filter)
        if not so_chk or so_chk.customer_id != customer_id:
            return None, "订单不属于所选客户。"

    remaining_map = pending_remaining_qty_by_order_item_id(customer_id, order_id_filter)
    for oi_id, total_need in qty_by_oi.items():
        item = db.session.get(OrderItem, oi_id)
        if not item:
            return None, "存在无效的订单行。"
        order_row = db.session.get(SalesOrder, item.order_id)
        if not order_row or order_row.customer_id != customer_id:
            return None, "订单行与所选客户不一致。"
        if order_id_filter is not None and item.order_id != order_id_filter:
            return None, "订单行不属于指定的订单。"
        rem = remaining_map.get(oi_id, Decimal(0))
        if rem <= 0:
            return None, "所选订单行暂无待发数量（已发与待发送货单已占满订单数量）。"
        if total_need > rem:
            return None, "本次送货数量超过可发剩余（已含待发送货单占用，请核对或调整待发单）。"

    max_commit_attempts = 12
    delivery: Optional[Delivery] = None
    for attempt in range(max_commit_attempts):
        try:
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
                item = (
                    OrderItem.query.options(joinedload(OrderItem.customer_product))
                    .filter_by(id=oi_id)
                    .first()
                )
                if not item:
                    continue
                di = DeliveryItem(
                    delivery_id=delivery.id,
                    order_item_id=item.id,
                    order_id=item.order_id,
                    product_name=item.product_name,
                    customer_material_no=effective_customer_material_no(item),
                    quantity=qty,
                    unit=item.unit,
                )
                db.session.add(di)

            db.session.commit()
            return delivery, None
        except IntegrityError as ex:
            db.session.rollback()
            if _is_delivery_no_duplicate_integrity_error(ex) and attempt < max_commit_attempts - 1:
                continue
            return None, "保存送货单失败，请重试。"

    return None, "保存送货单失败，请重试。"


def update_delivery_waybill_for_list(delivery_id: int, new_waybill_raw: str) -> Tuple[str, str]:
    """列表修改快递单号。返回 (flash_category, message)，category 含 success / info / warning / danger。"""
    delivery = db.session.get(Delivery, delivery_id)
    if not delivery:
        return "danger", "送货单不存在。"
    if delivery.status != "created":
        return "warning", "仅待发状态可修改快递单号。"
    new_wb = (new_waybill_raw or "").strip()
    old_wb = (delivery.waybill_no or "").strip()
    if new_wb == old_wb:
        return "info", "快递单号未变更。"
    if len(new_wb) > 64:
        return "danger", "快递单号不能超过 64 个字符。"

    if delivery.express_company_id is None:
        delivery.waybill_no = new_wb or None
        delivery.express_waybill_id = None
        db.session.add(delivery)
        try:
            db.session.commit()
            return "success", "快递单号已更新。"
        except IntegrityError:
            db.session.rollback()
            return "danger", "保存失败，请重试。"

    if not new_wb:
        return "danger", "非自配送时快递单号不能为空。"

    if delivery.express_waybill_id:
        w_old = db.session.get(ExpressWaybill, delivery.express_waybill_id)
        if w_old and w_old.delivery_id == delivery.id:
            w_old.status = "available"
            w_old.delivery_id = None
            w_old.used_at = None
            db.session.add(w_old)
        delivery.express_waybill_id = None

    ec_id = delivery.express_company_id
    w_new = _allocate_waybill_by_no(ec_id, delivery.id, new_wb)
    if w_new:
        delivery.express_waybill_id = w_new.id
        delivery.waybill_no = w_new.waybill_no
    else:
        delivery.express_waybill_id = None
        delivery.waybill_no = new_wb

    db.session.add(delivery)
    try:
        db.session.commit()
        return "success", "快递单号已更新。"
    except IntegrityError:
        db.session.rollback()
        return "danger", "保存失败，请重试。"
