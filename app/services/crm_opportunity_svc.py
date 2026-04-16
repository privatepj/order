"""CRM：机会（Opportunity）相关业务逻辑。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import CrmOpportunity, CrmOpportunityLine, CrmLead, CustomerProduct
from app.models import Customer, SalesOrder
from app.services import order_svc


_OPP_STAGE_VALUES = frozenset({"draft", "qualified", "negotiating", "won", "lost"})

_OPP_STAGE_TRANSITIONS: Dict[str, set[str]] = {
    # 起点：draft（新建）
    "draft": {"qualified", "lost"},
    "qualified": {"negotiating", "won", "lost"},
    "negotiating": {"won", "lost"},
    "won": set(),
    "lost": set(),
}


def next_opportunity_code() -> str:
    """生成新的机会编码 O0001 形式。"""
    q = (
        db.session.query(CrmOpportunity.opp_code)
        .filter((CrmOpportunity.opp_code.like("O%")) | (CrmOpportunity.opp_code.like("o%")))
    )
    max_num = 0
    for (code,) in q.all():
        if not code or len(code) < 2:
            continue
        if code[0] not in ("O", "o"):
            continue
        try:
            max_num = max(max_num, int(code[1:]))
        except ValueError:
            continue

    next_num = max_num + 1
    while True:
        candidate = f"O{next_num:04d}"
        exists = CrmOpportunity.query.filter_by(opp_code=candidate).first()
        if not exists:
            return candidate
        next_num += 1


def create_opportunity_from_data(data: Dict[str, Any]) -> Tuple[Optional[CrmOpportunity], Optional[str]]:
    """创建单条机会。data：lead_id?、customer_id 必填、stage?。"""
    customer_id = data.get("customer_id")
    if not customer_id:
        return None, "请选择客户 customer_id。"
    if not db.session.get(Customer, int(customer_id)):
        return None, "客户不存在。"

    stage = (data.get("stage") or "draft").strip()
    if stage not in _OPP_STAGE_VALUES:
        return None, f"机会状态不合法：{stage}。"

    lead_id = data.get("lead_id")
    lead_id = int(lead_id) if lead_id else None
    if lead_id and not db.session.get(CrmLead, lead_id):
        return None, "线索 lead_id 不存在。"

    opp = CrmOpportunity(
        opp_code=next_opportunity_code(),
        lead_id=lead_id,
        customer_id=int(customer_id),
        stage=stage,
        expected_amount=_to_decimal_or_none(data.get("expected_amount")),
        currency=(data.get("currency") or "").strip() or None,
        expected_close_date=_to_date_or_none(data.get("expected_close_date")),
        salesperson=(data.get("salesperson") or "GaoMeiHua").strip() or "GaoMeiHua",
        customer_order_no=(data.get("customer_order_no") or "").strip() or None,
        order_date=_to_date_or_none(data.get("order_date")),
        required_date=_to_date_or_none(data.get("required_date")),
        payment_type=(data.get("payment_type") or "monthly").strip() or "monthly",
        remark=(data.get("remark") or "").strip() or None,
        tags=(data.get("tags") or "").strip() or None,
    )
    db.session.add(opp)
    try:
        db.session.commit()
        return opp, None
    except IntegrityError:
        db.session.rollback()
        return None, "保存失败：机会编码冲突，请稍后重试。"


def update_opportunity_from_data(opp: CrmOpportunity, data: Dict[str, Any]) -> Optional[str]:
    stage = (data.get("stage") or opp.stage).strip()
    if stage not in _OPP_STAGE_VALUES:
        return f"机会状态不合法：{stage}。"

    opp.customer_id = int(data["customer_id"]) if data.get("customer_id") else opp.customer_id
    opp.stage = stage
    opp.expected_amount = _to_decimal_or_none(data.get("expected_amount"))
    opp.currency = (data.get("currency") or "").strip() or None
    opp.expected_close_date = _to_date_or_none(data.get("expected_close_date"))
    opp.salesperson = (data.get("salesperson") or opp.salesperson or "GaoMeiHua").strip() or "GaoMeiHua"
    opp.customer_order_no = (data.get("customer_order_no") or "").strip() or None
    opp.order_date = _to_date_or_none(data.get("order_date"))
    opp.required_date = _to_date_or_none(data.get("required_date"))
    opp.payment_type = (data.get("payment_type") or opp.payment_type or "monthly").strip() or "monthly"
    opp.remark = (data.get("remark") or "").strip() or None
    opp.tags = (data.get("tags") or "").strip() or None
    db.session.add(opp)
    try:
        db.session.commit()
        return None
    except IntegrityError:
        db.session.rollback()
        return "保存失败：请稍后重试。"


def set_opportunity_stage(opp: CrmOpportunity, next_stage: str) -> Optional[str]:
    next_stage = (next_stage or "").strip()
    if next_stage not in _OPP_STAGE_VALUES:
        return f"机会状态不合法：{next_stage}。"
    if opp.stage == next_stage:
        return None
    allowed = _OPP_STAGE_TRANSITIONS.get(opp.stage, set())
    if next_stage not in allowed:
        return f"不允许的状态流转：{opp.stage} -> {next_stage}。"

    if next_stage == "won":
        # won 之前必须有可生成订单的客户产品行
        line_rows = list(opp.lines or [])
        if not line_rows:
            return "无法标记为已成交：请先维护机会产品行（至少一行）。"
        for line in line_rows:
            if (
                not line.customer_product_id
                or not line.quantity
                or Decimal(str(line.quantity or 0)) <= 0
            ):
                return "无法标记为已成交：存在数量<=0的机会产品行。"

    opp.stage = next_stage
    db.session.add(opp)
    db.session.commit()
    return None


def add_opportunity_line(
    opp: CrmOpportunity,
    *,
    customer_product_id: int,
    quantity: Any,
    is_sample: bool = False,
    is_spare: bool = False,
    remark: Optional[str] = None,
) -> Tuple[Optional[CrmOpportunityLine], Optional[str]]:
    if not customer_product_id:
        return None, "请选择客户产品 customer_product_id。"
    # 校验该 customer_product 属于当前客户（逻辑校验）
    cp = db.session.get(CustomerProduct, int(customer_product_id))
    if not cp:
        return None, "客户产品不存在。"
    if int(cp.customer_id) != int(opp.customer_id):
        return None, "该客户产品不属于当前机会客户。"

    q = _to_decimal_or_none(quantity) or Decimal("0")
    if q <= 0:
        return None, "数量必须 > 0。"

    existing = (
        CrmOpportunityLine.query.filter_by(opportunity_id=opp.id, customer_product_id=cp.id).first()
    )
    if existing:
        # 简化：如果行已存在，就覆盖数量与标记
        existing.quantity = q
        existing.is_sample = bool(is_sample)
        existing.is_spare = bool(is_spare)
        existing.remark = (remark or "").strip() or None
        db.session.add(existing)
        try:
            db.session.commit()
            return existing, None
        except Exception:
            db.session.rollback()
            return None, "保存失败，请稍后重试。"

    line = CrmOpportunityLine(
        opportunity_id=opp.id,
        customer_product_id=cp.id,
        quantity=q,
        is_sample=bool(is_sample),
        is_spare=bool(is_spare),
        remark=(remark or "").strip() or None,
    )
    db.session.add(line)
    try:
        db.session.commit()
        return line, None
    except Exception:
        db.session.rollback()
        return None, "保存失败，请稍后重试。"


def remove_opportunity_line(opp: CrmOpportunity, line_id: int) -> None:
    line = CrmOpportunityLine.query.filter_by(id=line_id, opportunity_id=opp.id).first()
    if not line:
        return
    db.session.delete(line)
    db.session.commit()


def generate_order_from_opportunity(
    opp_id: int, *, generation_data: Dict[str, Any]
) -> Tuple[Optional[SalesOrder], Optional[str]]:
    """
    从机会生成 SalesOrder。
    generation_data 可覆盖：customer_order_no、salesperson、order_date、required_date、payment_type、remark
    """
    opp = db.session.get(CrmOpportunity, opp_id)
    if not opp:
        return None, "机会不存在。"

    # 加载行与客户产品
    lines = list(opp.lines or [])
    if not lines:
        return None, "无法生成订单：机会产品行为空。"

    items: List[Dict[str, Any]] = []
    for line in lines:
        if not line.customer_product_id:
            return None, "无法生成订单：存在无效客户产品。"
        items.append(
            {
                "customer_product_id": int(line.customer_product_id),
                "quantity": line.quantity,
                "is_sample": bool(line.is_sample),
                "is_spare": bool(line.is_spare),
            }
        )

    data = {
        "customer_id": opp.customer_id,
        "customer_order_no": (generation_data.get("customer_order_no") or opp.customer_order_no or "").strip() or None,
        "salesperson": (generation_data.get("salesperson") or opp.salesperson or "GaoMeiHua").strip() or "GaoMeiHua",
        "order_date": generation_data.get("order_date") or opp.order_date,
        "required_date": generation_data.get("required_date") or opp.required_date,
        "payment_type": generation_data.get("payment_type") or opp.payment_type,
        "remark": (generation_data.get("remark") or opp.remark or "").strip() or None,
        "items": items,
    }

    order, err = order_svc.create_order_from_data(data)
    if err or not order:
        return None, err or "订单生成失败。"

    # 更新机会：won + won_order_id
    opp.won_order_id = order.id
    opp.stage = "won"
    db.session.add(opp)
    db.session.commit()
    return order, None


def _to_decimal_or_none(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


def _to_date_or_none(v: Any):
    # Flask request.form 里通常是字符串 YYYY-MM-DD；SQLite 下兼容 date.fromisoformat
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        from datetime import date

        return date.fromisoformat(s)
    except Exception:
        return None

