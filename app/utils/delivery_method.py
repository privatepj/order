from __future__ import annotations

from typing import Any, Optional


DELIVERY_METHOD_EXPRESS = "express"
DELIVERY_METHOD_SELF = "self_delivery"
DELIVERY_METHOD_PICKUP = "pickup"

VALID_DELIVERY_METHODS = {
    DELIVERY_METHOD_EXPRESS,
    DELIVERY_METHOD_SELF,
    DELIVERY_METHOD_PICKUP,
}

DELIVERY_METHOD_LABELS = {
    DELIVERY_METHOD_EXPRESS: "快递",
    DELIVERY_METHOD_SELF: "自配送",
    DELIVERY_METHOD_PICKUP: "自提",
}


def _is_truthy(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, (int, float)) and int(value) == 1:
        return True
    if isinstance(value, str) and value.strip().lower() in ("1", "true", "yes", "on"):
        return True
    return False


def coerce_delivery_method(value: Any) -> Optional[str]:
    text = (value or "").strip() if isinstance(value, str) else str(value or "").strip()
    return text if text in VALID_DELIVERY_METHODS else None


def resolve_delivery_method(
    value: Any = None,
    *,
    legacy_self_delivery: Any = None,
    express_company_id: Any = None,
    default_when_missing: Optional[str] = None,
) -> str:
    method = coerce_delivery_method(value)
    if method:
        return method
    if legacy_self_delivery is not None:
        return DELIVERY_METHOD_SELF if _is_truthy(legacy_self_delivery) else DELIVERY_METHOD_EXPRESS
    if default_when_missing in VALID_DELIVERY_METHODS:
        return default_when_missing
    return DELIVERY_METHOD_EXPRESS if express_company_id else DELIVERY_METHOD_SELF


def delivery_method_label(
    value: Any = None,
    *,
    legacy_self_delivery: Any = None,
    express_company_id: Any = None,
) -> str:
    method = resolve_delivery_method(
        value,
        legacy_self_delivery=legacy_self_delivery,
        express_company_id=express_company_id,
    )
    return DELIVERY_METHOD_LABELS.get(method, DELIVERY_METHOD_LABELS[DELIVERY_METHOD_SELF])


def delivery_method_display_name(
    value: Any = None,
    *,
    express_company_name: Optional[str] = None,
    legacy_self_delivery: Any = None,
    express_company_id: Any = None,
) -> str:
    method = resolve_delivery_method(
        value,
        legacy_self_delivery=legacy_self_delivery,
        express_company_id=express_company_id,
    )
    if method == DELIVERY_METHOD_EXPRESS:
        return (express_company_name or "").strip() or DELIVERY_METHOD_LABELS[DELIVERY_METHOD_EXPRESS]
    return DELIVERY_METHOD_LABELS.get(method, DELIVERY_METHOD_LABELS[DELIVERY_METHOD_SELF])


def delivery_method_waybill_display(
    value: Any = None,
    *,
    waybill_no: Optional[str] = None,
    legacy_self_delivery: Any = None,
    express_company_id: Any = None,
) -> str:
    method = resolve_delivery_method(
        value,
        legacy_self_delivery=legacy_self_delivery,
        express_company_id=express_company_id,
    )
    if method == DELIVERY_METHOD_EXPRESS:
        return (waybill_no or "").strip() or "-"
    return DELIVERY_METHOD_LABELS.get(method, DELIVERY_METHOD_LABELS[DELIVERY_METHOD_SELF])
