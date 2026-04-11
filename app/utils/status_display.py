from __future__ import annotations

from typing import Dict, Mapping, Optional


_DOMAIN_TO_MAP: Dict[str, Mapping[str, str]] = {
    "machine_status": {
        "enabled": "启用",
        "disabled": "停用",
        "maintenance": "维修中",
        "scrapped": "报废",
    },
    "machine_runtime_status": {
        "running": "运行中",
        "idle": "空闲",
        "fault": "故障",
    },
    "machine_schedule_state": {
        "available": "可用",
        "unavailable": "不可用",
    },
    "express_waybill_status": {
        "available": "可用",
        "used": "已使用",
    },
    "production_preplan_status": {
        "draft": "草稿",
        "planned": "已测算",
    },
    "production_incident_status": {
        "open": "进行中",
        "closed": "已关闭",
    },
    "procurement_requisition_status": {
        "draft": "草稿",
        "signed": "已签字",
        "partial_ordered": "部分生成采购单",
        "ordered": "已生成采购单",
        "cancelled": "已取消",
    },
    "procurement_po_status": {
        "draft": "草稿",
        "ordered": "已下单",
        "partially_received": "部分收货",
        "received": "已收货",
        "cancelled": "已取消",
    },
    "procurement_receipt_status": {
        "draft": "草稿",
        "posted": "已过账",
    },
    "procurement_reconcile_status": {
        "pending": "待对比",
        "matched": "一致",
        "exception": "异常",
    },
    "procurement_stockin_approval_status": {
        "matched": "正常确认",
        "exception": "异常确认",
    },
    "delivery_status": {
        "created": "待发",
        "shipped": "已发",
        "expired": "失效",
    },
}


def status_zh(code: Optional[str], domain: str) -> str:
    if code is None:
        return "-"
    text = str(code).strip()
    if not text:
        return "-"
    return (_DOMAIN_TO_MAP.get(domain) or {}).get(text) or "未知"
