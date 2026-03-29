"""客户创建逻辑，供 Web 与 OpenClaw 共用（OpenClaw 走最小字段集）。"""
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Customer, Company


def next_customer_code() -> str:
    """生成新的客户编码 C0001 形式（与 Web 客户新增一致）。"""
    q = (
        db.session.query(Customer.customer_code)
        .filter(
            db.or_(
                Customer.customer_code.like("C%"),
                Customer.customer_code.like("c%"),
            )
        )
    )
    max_num = 0
    for (code,) in q.all():
        if not code or len(code) < 2:
            continue
        if code[0] not in ("C", "c"):
            continue
        try:
            max_num = max(max_num, int(code[1:]))
        except ValueError:
            continue

    next_num = max_num + 1
    while True:
        candidate = f"C{next_num:04d}"
        exists = Customer.query.filter_by(customer_code=candidate).first()
        if not exists:
            return candidate
        next_num += 1


def _normalize_payment_terms(raw: Optional[str]) -> Optional[str]:
    s = (raw or "").strip()
    if not s:
        return None
    low = s.lower()
    if low == "monthly":
        return "月结"
    if low == "cash":
        return "现金"
    return s


def create_customer_from_data(data: Dict[str, Any]) -> Tuple[Optional[Customer], Optional[str]]:
    """
    创建单条客户（单主体）。data: name, company_id 必填；
    short_code?, contact?, phone?, fax?, address?, payment_terms?, remark?, tax_point?
    """
    name = (data.get("name") or "").strip()
    if not name:
        return None, "客户名称为必填。"

    try:
        company_id = int(data.get("company_id"))
    except (TypeError, ValueError):
        return None, "请选择经营主体 company_id。"

    if not db.session.get(Company, company_id):
        return None, "经营主体不存在。"

    tp_raw = data.get("tax_point")

    max_tries = 3
    for attempt in range(max_tries):
        c = Customer()
        c.customer_code = next_customer_code()
        c.name = name
        c.company_id = company_id
        c.short_code = (data.get("short_code") or "").strip() or None
        c.contact = (data.get("contact") or "").strip() or None
        c.phone = (data.get("phone") or "").strip() or None
        c.fax = (data.get("fax") or "").strip() or None
        c.address = (data.get("address") or "").strip() or None
        c.payment_terms = _normalize_payment_terms(data.get("payment_terms"))
        c.remark = (data.get("remark") or "").strip() or None
        c.tax_point = None
        if tp_raw is not None and str(tp_raw).strip():
            try:
                c.tax_point = Decimal(str(tp_raw))
            except (InvalidOperation, ValueError):
                c.tax_point = None
        db.session.add(c)
        try:
            db.session.commit()
            return c, None
        except IntegrityError:
            db.session.rollback()
            db.session.expunge_all()
            if attempt == max_tries - 1:
                return None, "保存失败：客户编码冲突，请稍后重试。"

    return None, "保存失败：客户编码冲突，请稍后重试。"
