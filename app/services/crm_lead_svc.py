"""CRM：线索（Lead）相关业务逻辑。"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import CrmLead


def next_lead_code() -> str:
    """生成新的线索编码 L0001 形式。"""

    q = (
        db.session.query(CrmLead.lead_code)
        .filter((CrmLead.lead_code.like("L%")) | (CrmLead.lead_code.like("l%")))
    )
    max_num = 0
    for (code,) in q.all():
        if not code or len(code) < 2:
            continue
        prefix = code[0]
        if prefix not in ("L", "l"):
            continue
        try:
            max_num = max(max_num, int(code[1:]))
        except ValueError:
            continue
    next_num = max_num + 1
    while True:
        candidate = f"L{next_num:04d}"
        exists = CrmLead.query.filter_by(lead_code=candidate).first()
        if not exists:
            return candidate
        next_num += 1


def create_lead_from_data(data: Dict[str, Any]) -> Tuple[Optional[CrmLead], Optional[str]]:
    name = (data.get("customer_name") or "").strip()
    if not name:
        return None, "客户名称为必填。"

    lead = CrmLead(
        lead_code=next_lead_code(),
        customer_id=int(data["customer_id"]) if data.get("customer_id") else None,
        customer_name=name,
        contact=(data.get("contact") or "").strip() or None,
        phone=(data.get("phone") or "").strip() or None,
        source=(data.get("source") or "manual").strip() or "manual",
        status=(data.get("status") or "new").strip() or "new",
        tags=(data.get("tags") or "").strip() or None,
        remark=(data.get("remark") or "").strip() or None,
    )
    db.session.add(lead)
    try:
        db.session.commit()
        return lead, None
    except IntegrityError:
        db.session.rollback()
        return None, "保存失败：线索编码冲突，请稍后重试。"


def update_lead_from_data(lead: CrmLead, data: Dict[str, Any]) -> Optional[str]:
    name = (data.get("customer_name") or "").strip()
    if not name:
        return "客户名称为必填。"

    lead.customer_id = int(data["customer_id"]) if data.get("customer_id") else None
    lead.customer_name = name
    lead.contact = (data.get("contact") or "").strip() or None
    lead.phone = (data.get("phone") or "").strip() or None
    lead.source = (data.get("source") or lead.source or "manual").strip() or "manual"
    lead.status = (data.get("status") or lead.status).strip() or "new"
    lead.tags = (data.get("tags") or "").strip() or None
    lead.remark = (data.get("remark") or "").strip() or None
    db.session.add(lead)
    try:
        db.session.commit()
        return None
    except IntegrityError:
        db.session.rollback()
        return "保存失败：请稍后重试。"

