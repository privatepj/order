from __future__ import annotations

from typing import Any, Dict, Tuple


EVENT_ORDER_CHANGED = "order.changed"
EVENT_INVENTORY_CHANGED = "inventory.changed"
EVENT_PROCUREMENT_RECEIVED = "procurement.received"
EVENT_PRODUCTION_MEASURED = "production.measured"
EVENT_PRODUCTION_REPORTED = "production.reported"
EVENT_PRODUCTION_OPERATION_REPORTED = "production.operation.reported"
EVENT_MACHINE_ABNORMAL = "production.machine.abnormal"
EVENT_MACHINE_RECOVERED = "production.machine.recovered"
EVENT_QUALITY_INSPECTION_STARTED = "quality.inspection.started"
EVENT_QUALITY_PASSED = "quality.passed"
EVENT_QUALITY_FAILED = "quality.failed"
EVENT_QUALITY_REWORKED = "quality.reworked"
EVENT_ORDER_OVERDUE_SCAN = "order.overdue_scan"
EVENT_DELIVERY_SHIPPED = "delivery.shipped"

EVENT_REQUIRED_FIELDS: Dict[str, Tuple[str, ...]] = {
    EVENT_ORDER_CHANGED: ("order_id", "source_id", "version"),
    EVENT_INVENTORY_CHANGED: ("source_id", "version"),
    EVENT_PROCUREMENT_RECEIVED: ("source_id", "version"),
    EVENT_PRODUCTION_MEASURED: ("preplan_id", "source_id", "version"),
    EVENT_PRODUCTION_REPORTED: ("order_id", "source_id", "version"),
    EVENT_PRODUCTION_OPERATION_REPORTED: ("order_id", "work_order_id", "source_id", "version"),
    EVENT_MACHINE_ABNORMAL: ("source_id", "version", "incident_id", "severity"),
    EVENT_MACHINE_RECOVERED: ("source_id", "version", "incident_id"),
    EVENT_QUALITY_INSPECTION_STARTED: ("order_id", "source_id", "version"),
    EVENT_QUALITY_PASSED: ("order_id", "source_id", "version"),
    EVENT_QUALITY_FAILED: ("order_id", "source_id", "version", "qc_result"),
    EVENT_QUALITY_REWORKED: ("order_id", "source_id", "version"),
    EVENT_ORDER_OVERDUE_SCAN: ("source_id", "version"),
    EVENT_DELIVERY_SHIPPED: ("order_id", "source_id", "version"),
}

EVENT_TYPES = set(EVENT_REQUIRED_FIELDS.keys())


def build_idempotency_key(*, event_type: str, biz_key: str, source_id: Any, version: Any) -> str:
    return f"{event_type}:{biz_key}:{source_id}:{version}"


def validate_event_payload(event_type: str, payload: Dict[str, Any] | None) -> None:
    if event_type not in EVENT_TYPES:
        raise ValueError("不支持的事件类型。")
    data = payload or {}
    missing = [f for f in EVENT_REQUIRED_FIELDS[event_type] if data.get(f) in (None, "")]
    if missing:
        raise ValueError(f"payload 缺少必填字段: {', '.join(missing)}")
