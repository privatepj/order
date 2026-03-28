"""快递单号入池：短码前缀校验与写入 express_waybill。"""
from __future__ import annotations

from typing import Literal, Optional, Tuple

from app import db
from app.models import ExpressWaybill

WAYBILL_MAX_LEN = 64

ApplyResult = Literal["inserted", "skipped", "invalid"]


def waybill_matches_company_code(waybill_no: str, company_code: str) -> bool:
    w = (waybill_no or "").strip().upper()
    c = (company_code or "").strip().upper()
    if not w or not c:
        return False
    return w.startswith(c)


def validate_waybill_for_pool(waybill_no: str, company_code: str) -> Optional[str]:
    """通过返回 None，否则返回简短错误说明（用于 Excel 行提示）。"""
    w = (waybill_no or "").strip()
    if not w:
        return "单号为空"
    if len(w) > WAYBILL_MAX_LEN:
        return f"单号超过 {WAYBILL_MAX_LEN} 个字符"
    if not waybill_matches_company_code(w, company_code):
        return "单号开头与所选快递公司短码不一致"
    return None


def apply_waybill_to_pool(
    express_company_id: int,
    company_code: str,
    waybill_no: str,
) -> Tuple[ApplyResult, Optional[str]]:
    """
    校验并入池。未校验通过返回 invalid + 原因；已存在返回 skipped；新增返回 inserted。
    调用方负责在同一事务末尾 commit。
    """
    err = validate_waybill_for_pool(waybill_no, company_code)
    if err:
        return "invalid", err
    w = waybill_no.strip()
    exists = (
        db.session.query(ExpressWaybill.id)
        .filter_by(express_company_id=express_company_id, waybill_no=w)
        .first()
    )
    if exists:
        return "skipped", None
    db.session.add(
        ExpressWaybill(
            express_company_id=express_company_id,
            waybill_no=w,
            status="available",
        )
    )
    return "inserted", None
