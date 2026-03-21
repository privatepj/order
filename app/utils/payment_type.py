"""订单付款类型：月结 / 现金（样板为旧数据兼容）。"""
from typing import Optional

PAYMENT_TYPE_LABELS = {
    "monthly": "月结",
    "cash": "现金",
}
LEGACY_PAYMENT_TYPE_LABELS = {
    **PAYMENT_TYPE_LABELS,
    "sample": "样板",
}
VALID_PAYMENT_TYPES = frozenset(PAYMENT_TYPE_LABELS)


def payment_type_label(code: Optional[str]) -> str:
    if not code:
        return "月结"
    return LEGACY_PAYMENT_TYPE_LABELS.get(code, code)


def normalize_payment_type(value: Optional[str]) -> str:
    v = (value or "").strip()
    # 旧数据：样板单统一按现金处理（新建入口不再提供样板）。
    if v == "sample":
        return "cash"
    if v in VALID_PAYMENT_TYPES:
        return v
    return "monthly"
