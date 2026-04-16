"""CRM：工单（Ticket）相关业务逻辑。"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import CrmTicket, CrmTicketActivity, Customer, User


_TICKET_STATUS_VALUES = frozenset({"open", "in_progress", "resolved", "closed"})

_TICKET_STATUS_TRANSITIONS = {
    "open": {"in_progress", "resolved", "closed"},
    "in_progress": {"resolved", "closed"},
    "resolved": {"closed"},
    "closed": set(),
}


def next_ticket_code() -> str:
    """生成新的工单编码 T0001 形式。"""
    q = (
        db.session.query(CrmTicket.ticket_code)
        .filter((CrmTicket.ticket_code.like("T%")) | (CrmTicket.ticket_code.like("t%")))
    )
    max_num = 0
    for (code,) in q.all():
        if not code or len(code) < 2:
            continue
        if code[0] not in ("T", "t"):
            continue
        try:
            max_num = max(max_num, int(code[1:]))
        except ValueError:
            continue

    next_num = max_num + 1
    while True:
        candidate = f"T{next_num:04d}"
        exists = CrmTicket.query.filter_by(ticket_code=candidate).first()
        if not exists:
            return candidate
        next_num += 1


def create_ticket_from_data(data: Dict[str, Any]) -> Tuple[Optional[CrmTicket], Optional[str]]:
    customer_id = data.get("customer_id")
    if not customer_id:
        return None, "请选择客户 customer_id。"
    if not db.session.get(Customer, int(customer_id)):
        return None, "客户不存在。"

    ticket = CrmTicket(
        ticket_code=next_ticket_code(),
        customer_id=int(customer_id),
        ticket_type=(data.get("ticket_type") or "support").strip() or "support",
        priority=(data.get("priority") or "normal").strip() or "normal",
        status=(data.get("status") or "open").strip() or "open",
        subject=(data.get("subject") or "").strip() or None,
        description=(data.get("description") or "").strip() or None,
        assignee_user_id=int(data["assignee_user_id"]) if data.get("assignee_user_id") else None,
        due_date=_to_date_or_none(data.get("due_date")),
        tags=(data.get("tags") or "").strip() or None,
        remark=(data.get("remark") or "").strip() or None,
    )
    db.session.add(ticket)
    try:
        db.session.commit()
        return ticket, None
    except IntegrityError:
        db.session.rollback()
        return None, "保存失败：工单编码冲突，请稍后重试。"


def update_ticket_from_data(ticket: CrmTicket, data: Dict[str, Any]) -> Optional[str]:
    customer_id = data.get("customer_id")
    if customer_id:
        if not db.session.get(Customer, int(customer_id)):
            return "客户不存在。"
        ticket.customer_id = int(customer_id)

    ticket.ticket_type = (data.get("ticket_type") or ticket.ticket_type or "support").strip() or "support"
    ticket.priority = (data.get("priority") or ticket.priority or "normal").strip() or "normal"
    ticket.status = (data.get("status") or ticket.status).strip() or "open"
    ticket.subject = (data.get("subject") or "").strip() or None
    ticket.description = (data.get("description") or "").strip() or None
    ticket.assignee_user_id = (
        int(data["assignee_user_id"]) if data.get("assignee_user_id") else None
    )
    ticket.due_date = _to_date_or_none(data.get("due_date"))
    ticket.tags = (data.get("tags") or "").strip() or None
    ticket.remark = (data.get("remark") or "").strip() or None

    db.session.add(ticket)
    db.session.commit()
    return None


def set_ticket_status(ticket: CrmTicket, next_status: str) -> Optional[str]:
    next_status = (next_status or "").strip()
    if next_status not in _TICKET_STATUS_VALUES:
        return f"工单状态不合法：{next_status}。"
    if ticket.status == next_status:
        return None
    allowed = _TICKET_STATUS_TRANSITIONS.get(ticket.status, set())
    if next_status not in allowed:
        return f"不允许的状态流转：{ticket.status} -> {next_status}。"

    ticket.status = next_status
    db.session.add(ticket)
    db.session.commit()
    return None


def add_ticket_activity(
    ticket: CrmTicket,
    *,
    actor_user_id: Optional[int],
    activity_type: str = "note",
    content: str,
) -> Optional[str]:
    if not content or not str(content).strip():
        return "内容不能为空。"

    # actor_user_id 可选，但若传入则做逻辑校验
    if actor_user_id is not None and not db.session.get(User, int(actor_user_id)):
        return "指定的处理人不存在。"

    act = CrmTicketActivity(
        ticket_id=ticket.id,
        actor_user_id=int(actor_user_id) if actor_user_id else None,
        activity_type=(activity_type or "note").strip() or "note",
        content=str(content).strip(),
    )
    db.session.add(act)
    db.session.commit()
    return None


def _to_date_or_none(v: Any):
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

