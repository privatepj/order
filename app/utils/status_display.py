from __future__ import annotations

from typing import Dict, Mapping, Optional


# 说明：数据库里保存的是英文状态码；这里只负责“展示层”转换为中文。
_DOMAIN_TO_MAP: Dict[str, Mapping[str, str]] = {
    # 机台
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

    # 快递单号池
    "express_waybill_status": {
        "available": "可用",
        "used": "已使用",
    },

    # 生产：预生产计划、事故
    "production_preplan_status": {
        "draft": "草稿",
        "planned": "已测算",
    },
    "production_incident_status": {
        "open": "进行中",
        "closed": "已关闭",
    },

    # 采购：请购、采购单、收货
    "procurement_requisition_status": {
        "draft": "草稿",
        "ordered": "已下单",
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

    # 送货单
    "delivery_status": {
        "created": "待发",
        "shipped": "已发",
        "expired": "失效",
    },
}


def status_zh(code: Optional[str], domain: str) -> str:
    """
    Jinja filter：把英文状态码转换为中文。

    - code 为空：返回 `-`
    - code 未知：返回 `未知`
    """

    if code is None:
        return "-"
    s = str(code).strip()
    if not s:
        return "-"
    m = _DOMAIN_TO_MAP.get(domain) or {}
    return m.get(s) or "未知"


