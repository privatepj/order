from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import case, func
from flask import current_app

from app import db
from app.models import (
    CustomerProduct,
    InventoryMovement,
    InventoryOpeningBalance,
    OrchestratorAction,
    OrchestratorAiAdvice,
    OrchestratorAiAdviceMetric,
    OrchestratorAuditLog,
    OrchestratorEvent,
    OrchestratorReplayJob,
    OrchestratorRuleProfile,
    OrderItem,
    ProductionPreplan,
    ProductionPreplanLine,
    SalesOrder,
)
from app.services import order_svc, production_svc
from app.services.orchestrator_ai_provider import get_default_provider
from app.services.orchestrator_contracts import (
    EVENT_DELIVERY_SHIPPED,
    EVENT_INVENTORY_CHANGED,
    EVENT_ORDER_CHANGED,
    EVENT_ORDER_OVERDUE_SCAN,
    EVENT_PROCUREMENT_RECEIVED,
    EVENT_PRODUCTION_OPERATION_REPORTED,
    EVENT_MACHINE_ABNORMAL,
    EVENT_MACHINE_RECOVERED,
    EVENT_QUALITY_INSPECTION_STARTED,
    EVENT_PRODUCTION_MEASURED,
    EVENT_PRODUCTION_REPORTED,
    EVENT_QUALITY_FAILED,
    EVENT_QUALITY_PASSED,
    EVENT_QUALITY_REWORKED,
    EVENT_TYPES,
    build_idempotency_key,
    validate_event_payload,
)
from app.services.orchestrator_state_machine import validate_hard_constraints


ACTION_CREATE_PREPLAN = "CreatePreplan"
ACTION_RUN_PRODUCTION_MEASURE = "RunProductionMeasure"
ACTION_MOVE_ORDER_STATUS = "MoveOrderStatus"
ACTION_CREATE_PROCUREMENT_REQUEST = "CreateProcurementRequest"
ACTION_APPLY_ALTERNATIVE_MATERIAL = "ApplyAlternativeMaterial"
ACTION_CREATE_OUTSOURCE_ORDER = "CreateOutsourceOrder"
ACTION_SWITCH_SECONDARY_SUPPLIER = "SwitchSecondarySupplier"
ACTION_ESCALATE_DEVICE_ALERT = "EscalateDeviceAlert"
ACTION_TRIGGER_QUALITY_REWORK = "TriggerQualityRework"
ACTION_TRIGGER_QUALITY_HOLD = "TriggerQualityHold"
HIGH_RISK_ACTIONS = (ACTION_CREATE_PREPLAN, ACTION_RUN_PRODUCTION_MEASURE)


def _audit(
    *,
    event_id: Optional[int],
    action_id: Optional[int],
    level: str,
    message: str,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    next_id = (db.session.query(func.coalesce(func.max(OrchestratorAuditLog.id), 0)).scalar() or 0) + 1
    db.session.add(
        OrchestratorAuditLog(
            id=int(next_id),
            event_id=event_id,
            action_id=action_id,
            level=level,
            message=message[:500],
            detail=detail,
        )
    )


def log_manual_audit(
    *,
    level: str,
    message: str,
    detail: Optional[Dict[str, Any]] = None,
    event_id: Optional[int] = None,
    action_id: Optional[int] = None,
) -> None:
    _audit(
        event_id=event_id,
        action_id=action_id,
        level=level,
        message=message,
        detail=detail,
    )


def ingest_event(
    *,
    event_type: str,
    biz_key: str,
    payload: Optional[Dict[str, Any]],
    trace_id: Optional[str],
    idempotency_key: str,
    occurred_at: datetime,
) -> OrchestratorEvent:
    if event_type not in EVENT_TYPES:
        raise ValueError("不支持的事件类型。")
    validate_event_payload(event_type, payload or {})
    existed = OrchestratorEvent.query.filter_by(idempotency_key=idempotency_key).first()
    if existed:
        return existed
    next_id = (db.session.query(func.coalesce(func.max(OrchestratorEvent.id), 0)).scalar() or 0) + 1
    evt = OrchestratorEvent(
        id=int(next_id),
        event_type=event_type,
        biz_key=biz_key,
        trace_id=trace_id,
        idempotency_key=idempotency_key,
        payload=payload or {},
        status="new",
        occurred_at=occurred_at,
    )
    db.session.add(evt)
    db.session.flush()
    _audit(event_id=evt.id, action_id=None, level="info", message="event_ingested", detail={"event_type": event_type})
    return evt


def emit_event(
    *,
    event_type: str,
    biz_key: str,
    payload: Dict[str, Any],
    trace_id: Optional[str] = None,
    occurred_at: Optional[datetime] = None,
) -> OrchestratorEvent:
    source_id = payload.get("source_id")
    version = payload.get("version")
    idem_key = build_idempotency_key(
        event_type=event_type,
        biz_key=biz_key,
        source_id=source_id,
        version=version,
    )
    return ingest_event(
        event_type=event_type,
        biz_key=biz_key,
        payload=payload,
        trace_id=trace_id,
        idempotency_key=idem_key,
        occurred_at=occurred_at or datetime.now(),
    )


def _stock_total_for_product(product_id: int) -> Decimal:
    opening = (
        db.session.query(func.coalesce(func.sum(InventoryOpeningBalance.opening_qty), 0))
        .filter(
            InventoryOpeningBalance.category == "finished",
            InventoryOpeningBalance.product_id == int(product_id),
        )
        .scalar()
    )
    in_out = (
        db.session.query(
            func.coalesce(func.sum(case((InventoryMovement.direction == "in", InventoryMovement.quantity), else_=0)), 0),
            func.coalesce(func.sum(case((InventoryMovement.direction == "out", InventoryMovement.quantity), else_=0)), 0),
        )
        .filter(
            InventoryMovement.category == "finished",
            InventoryMovement.product_id == int(product_id),
        )
        .one()
    )
    return Decimal(str(opening or 0)) + Decimal(str(in_out[0] or 0)) - Decimal(str(in_out[1] or 0))


def _order_shortage_summary(order_id: int) -> Dict[str, Any]:
    rows = (
        db.session.query(OrderItem, CustomerProduct.product_id)
        .outerjoin(CustomerProduct, CustomerProduct.id == OrderItem.customer_product_id)
        .filter(OrderItem.order_id == order_id)
        .all()
    )
    shortage_lines: List[Dict[str, Any]] = []
    has_shortage = False
    for item, product_id in rows:
        need = Decimal(str(item.quantity or 0))
        if not product_id:
            shortage_lines.append({"order_item_id": item.id, "product_id": 0, "shortage_qty": float(need)})
            has_shortage = has_shortage or need > 0
            continue
        stock = _stock_total_for_product(int(product_id))
        shortage = need - stock
        if shortage > 0:
            has_shortage = True
            shortage_lines.append(
                {
                    "order_item_id": item.id,
                    "product_id": int(product_id),
                    "shortage_qty": float(shortage),
                    "required_qty": float(need),
                    "stock_qty": float(stock),
                    "unit": item.unit,
                }
            )
    return {"has_shortage": has_shortage, "lines": shortage_lines}


def _order_ids_for_preplan(preplan_id: int) -> List[int]:
    rows = (
        db.session.query(OrderItem.order_id)
        .join(ProductionPreplanLine, ProductionPreplanLine.source_order_item_id == OrderItem.id)
        .filter(ProductionPreplanLine.preplan_id == int(preplan_id))
        .distinct()
        .all()
    )
    return [int(r[0]) for r in rows if r and r[0]]


def _create_action(event_id: int, action_type: str, payload: Dict[str, Any]) -> OrchestratorAction:
    action_key = f"{event_id}:{action_type}:{payload.get('order_id', '')}:{payload.get('preplan_id', '')}"
    existed = OrchestratorAction.query.filter_by(action_key=action_key).first()
    if existed:
        return existed
    next_id = (db.session.query(func.coalesce(func.max(OrchestratorAction.id), 0)).scalar() or 0) + 1
    action = OrchestratorAction(
        id=int(next_id),
        event_id=event_id,
        action_type=action_type,
        action_key=action_key,
        payload=payload,
        status="pending",
    )
    db.session.add(action)
    db.session.flush()
    return action


def _build_shortage_strategy(*, payload: Dict[str, Any], shortage: Dict[str, Any]) -> Dict[str, Any]:
    profile = get_active_rule_profiles()[0] if get_active_rule_profiles() else None
    return {
        "rule_code": str((payload.get("rule_code") or ((profile or {}).get("rule_code") or "default_shortage"))),
        "allow_alternative": bool(payload.get("allow_alternative", (profile or {}).get("allow_alternative", False))),
        "allow_outsource": bool(payload.get("allow_outsource", (profile or {}).get("allow_outsource", False))),
        "allow_secondary_supplier": bool(payload.get("allow_secondary_supplier", (profile or {}).get("allow_secondary_supplier", False))),
        "shortage_line_count": len((shortage or {}).get("lines") or []),
    }


def _auto_generate_advice_for_event(event: OrchestratorEvent, actions: List[OrchestratorAction]) -> None:
    if not actions:
        return
    provider = get_default_provider()
    payload = dict(event.payload or {})
    suggestions = provider.generate(
        event_type=str(event.event_type),
        payload=payload,
        action_types=[x.action_type for x in actions],
    )
    for item in suggestions:
        _ = create_ai_advice(
            event_id=int(event.id),
            advice_type=str(item.get("advice_type") or "strategy"),
            recommended_action=str(item.get("recommended_action") or ""),
            confidence=item.get("confidence"),
            reason=str(item.get("reason") or ""),
            meta=item.get("meta") or {},
        )


def evaluate_event(event: OrchestratorEvent) -> List[OrchestratorAction]:
    payload = dict(event.payload or {})
    actions: List[OrchestratorAction] = []
    order_id = int(payload.get("order_id") or 0)

    if event.event_type == EVENT_ORDER_CHANGED and order_id > 0:
        shortage = _order_shortage_summary(order_id)
        strategy = _build_shortage_strategy(payload=payload, shortage=shortage)
        _audit(
            event_id=int(event.id),
            action_id=None,
            level="info",
            message="rule_profile_hit",
            detail={"rule_code": strategy.get("rule_code"), "shortage": bool(shortage["has_shortage"])},
        )
        if shortage["has_shortage"]:
            actions.append(_create_action(event.id, ACTION_CREATE_PREPLAN, {"order_id": order_id, "shortage": shortage}))
            actions.append(_create_action(event.id, ACTION_CREATE_PROCUREMENT_REQUEST, {"order_id": order_id, "shortage": shortage}))
            if strategy["allow_alternative"]:
                actions.append(
                    _create_action(
                        event.id,
                        ACTION_APPLY_ALTERNATIVE_MATERIAL,
                        {"order_id": order_id, "shortage": shortage, "rule_context": strategy},
                    )
                )
            if strategy["allow_outsource"]:
                actions.append(
                    _create_action(
                        event.id,
                        ACTION_CREATE_OUTSOURCE_ORDER,
                        {"order_id": order_id, "shortage": shortage, "rule_context": strategy},
                    )
                )
            if strategy["allow_secondary_supplier"]:
                actions.append(
                    _create_action(
                        event.id,
                        ACTION_SWITCH_SECONDARY_SUPPLIER,
                        {"order_id": order_id, "shortage": shortage, "rule_context": strategy},
                    )
                )
        else:
            actions.append(_create_action(event.id, ACTION_MOVE_ORDER_STATUS, {"order_id": order_id, "target_status": "pending"}))

    if event.event_type in (EVENT_INVENTORY_CHANGED, EVENT_PROCUREMENT_RECEIVED) and order_id > 0:
        shortage = _order_shortage_summary(order_id)
        if not shortage["has_shortage"]:
            actions.append(_create_action(event.id, ACTION_RUN_PRODUCTION_MEASURE, {"order_id": order_id}))

    if event.event_type == EVENT_DELIVERY_SHIPPED and order_id > 0:
        actions.append(_create_action(event.id, ACTION_MOVE_ORDER_STATUS, {"order_id": order_id, "target_status": "delivered"}))
    if event.event_type == EVENT_PRODUCTION_MEASURED:
        preplan_id = int(payload.get("preplan_id") or 0)
        for oid in _order_ids_for_preplan(preplan_id):
            actions.append(_create_action(event.id, ACTION_MOVE_ORDER_STATUS, {"order_id": oid, "target_status": "partial"}))
    if event.event_type == EVENT_PRODUCTION_REPORTED and order_id > 0:
        actions.append(_create_action(event.id, ACTION_MOVE_ORDER_STATUS, {"order_id": order_id, "target_status": "partial"}))
    if event.event_type == EVENT_PRODUCTION_OPERATION_REPORTED and order_id > 0:
        actions.append(_create_action(event.id, ACTION_MOVE_ORDER_STATUS, {"order_id": order_id, "target_status": "partial"}))
    if event.event_type == EVENT_QUALITY_PASSED and order_id > 0:
        actions.append(_create_action(event.id, ACTION_MOVE_ORDER_STATUS, {"order_id": order_id, "target_status": "partial"}))
    if event.event_type == EVENT_QUALITY_FAILED and order_id > 0:
        actions.append(_create_action(event.id, ACTION_TRIGGER_QUALITY_HOLD, {"order_id": order_id, "target_status": "pending"}))
        actions.append(_create_action(event.id, ACTION_TRIGGER_QUALITY_REWORK, {"order_id": order_id}))
    if event.event_type == EVENT_QUALITY_REWORKED and order_id > 0:
        actions.append(_create_action(event.id, ACTION_MOVE_ORDER_STATUS, {"order_id": order_id, "target_status": "partial"}))
    if event.event_type == EVENT_QUALITY_INSPECTION_STARTED and order_id > 0:
        actions.append(_create_action(event.id, ACTION_MOVE_ORDER_STATUS, {"order_id": order_id, "target_status": "pending"}))
    if event.event_type in (EVENT_MACHINE_ABNORMAL, EVENT_MACHINE_RECOVERED):
        actions.append(
            _create_action(
                event.id,
                ACTION_ESCALATE_DEVICE_ALERT,
                {
                    "incident_id": int(payload.get("incident_id") or 0),
                    "severity": str(payload.get("severity") or ""),
                    "status": event.event_type,
                },
            )
        )
    if event.event_type == EVENT_ORDER_OVERDUE_SCAN:
        overdue_rows = (
            SalesOrder.query.filter(
                SalesOrder.required_date.isnot(None),
                SalesOrder.required_date < datetime.now().date(),
                SalesOrder.status.in_(("pending", "partial")),
            )
            .order_by(SalesOrder.id.asc())
            .limit(200)
            .all()
        )
        for so in overdue_rows:
            actions.append(
                _create_action(
                    event.id,
                    ACTION_CREATE_PROCUREMENT_REQUEST,
                    {"order_id": int(so.id), "overdue": True, "required_date": str(so.required_date)},
                )
            )

    return actions


def _execute_create_preplan(action: OrchestratorAction, created_by: int) -> Dict[str, Any]:
    order_id = int((action.payload or {}).get("order_id") or 0)
    shortage_lines = list(((action.payload or {}).get("shortage") or {}).get("lines") or [])
    order = db.session.get(SalesOrder, order_id)
    if not order:
        raise ValueError("订单不存在。")
    preplan = ProductionPreplan(
        source_type="combined",
        plan_date=datetime.now().date(),
        customer_id=int(order.customer_id or 0),
        status="draft",
        remark=f"orchestrator from order#{order_id}",
        created_by=created_by,
    )
    db.session.add(preplan)
    db.session.flush()
    line_no = 1
    for row in shortage_lines:
        product_id = int(row.get("product_id") or 0)
        shortage_qty = Decimal(str(row.get("shortage_qty") or 0))
        if product_id <= 0 or shortage_qty <= 0:
            continue
        db.session.add(
            ProductionPreplanLine(
                preplan_id=preplan.id,
                line_no=line_no,
                source_type="order_item",
                source_order_item_id=int(row.get("order_item_id") or 0) or None,
                product_id=product_id,
                quantity=shortage_qty,
                unit=row.get("unit"),
                remark="auto-generated by orchestrator",
            )
        )
        line_no += 1
    if line_no == 1:
        raise ValueError("无有效缺口行，未生成预生产计划。")
    return {"preplan_id": preplan.id}


def _execute_run_production_measure(action: OrchestratorAction, created_by: int) -> Dict[str, Any]:
    order_id = int((action.payload or {}).get("order_id") or 0)
    preplan = (
        ProductionPreplan.query.filter(
            ProductionPreplan.remark.like(f"%order#{order_id}%"),
            ProductionPreplan.status.in_(("draft", "planned")),
        )
        .order_by(ProductionPreplan.id.desc())
        .first()
    )
    if not preplan:
        raise ValueError("未找到可执行测算的预生产计划。")
    work_order_ids = production_svc.measure_production_for_preplan(preplan_id=preplan.id, created_by=created_by)
    return {"preplan_id": preplan.id, "work_order_count": len(work_order_ids)}


def _execute_move_order_status(action: OrchestratorAction, _: int) -> Dict[str, Any]:
    order_id = int((action.payload or {}).get("order_id") or 0)
    target_status = str((action.payload or {}).get("target_status") or "pending")
    order = db.session.get(SalesOrder, order_id)
    if not order:
        raise ValueError("订单不存在。")
    valid, reason = validate_hard_constraints(
        target_stage="done" if target_status == "delivered" else "confirmed",
        material_ready=True,
        qc_passed=True,
        has_delivery_items=True,
    )
    if not valid:
        raise ValueError(reason)
    order.status = target_status
    db.session.add(order)
    return {"order_id": order.id, "status": order.status}


def _execute_create_procurement_request(action: OrchestratorAction, _: int) -> Dict[str, Any]:
    shortage = ((action.payload or {}).get("shortage") or {}).get("lines") or []
    return {"suggested_procurement_lines": len(shortage)}


def _execute_alternative_material(action: OrchestratorAction, _: int) -> Dict[str, Any]:
    shortage = ((action.payload or {}).get("shortage") or {}).get("lines") or []
    return {"alt_material_candidates": len(shortage), "strategy": "rule_template"}


def _execute_outsource(action: OrchestratorAction, _: int) -> Dict[str, Any]:
    shortage = ((action.payload or {}).get("shortage") or {}).get("lines") or []
    return {"outsource_lines": len(shortage), "strategy": "rule_template"}


def _execute_switch_secondary_supplier(action: OrchestratorAction, _: int) -> Dict[str, Any]:
    shortage = ((action.payload or {}).get("shortage") or {}).get("lines") or []
    return {"secondary_supplier_lines": len(shortage), "strategy": "rule_template"}


def _execute_escalate_device_alert(action: OrchestratorAction, _: int) -> Dict[str, Any]:
    payload = dict(action.payload or {})
    return {
        "incident_id": int(payload.get("incident_id") or 0),
        "severity": str(payload.get("severity") or ""),
        "escalated": True,
    }


def _execute_quality_rework(action: OrchestratorAction, _: int) -> Dict[str, Any]:
    return {"rework_created": True, "order_id": int((action.payload or {}).get("order_id") or 0)}


def execute_action(action: OrchestratorAction, *, created_by: int) -> Dict[str, Any]:
    if action.action_type == ACTION_CREATE_PREPLAN:
        return _execute_create_preplan(action, created_by)
    if action.action_type == ACTION_RUN_PRODUCTION_MEASURE:
        return _execute_run_production_measure(action, created_by)
    if action.action_type == ACTION_MOVE_ORDER_STATUS:
        return _execute_move_order_status(action, created_by)
    if action.action_type == ACTION_CREATE_PROCUREMENT_REQUEST:
        return _execute_create_procurement_request(action, created_by)
    if action.action_type == ACTION_APPLY_ALTERNATIVE_MATERIAL:
        return _execute_alternative_material(action, created_by)
    if action.action_type == ACTION_CREATE_OUTSOURCE_ORDER:
        return _execute_outsource(action, created_by)
    if action.action_type == ACTION_SWITCH_SECONDARY_SUPPLIER:
        return _execute_switch_secondary_supplier(action, created_by)
    if action.action_type == ACTION_ESCALATE_DEVICE_ALERT:
        return _execute_escalate_device_alert(action, created_by)
    if action.action_type in (ACTION_TRIGGER_QUALITY_REWORK, ACTION_TRIGGER_QUALITY_HOLD):
        return _execute_quality_rework(action, created_by)
    raise ValueError("未知动作类型。")


def process_event(event_id: int, *, created_by: int) -> Dict[str, Any]:
    evt = db.session.get(OrchestratorEvent, event_id)
    if not evt:
        raise ValueError("事件不存在。")
    evt.status = "processing"
    evt.attempts = int(evt.attempts or 0) + 1
    db.session.add(evt)
    db.session.flush()

    actions = evaluate_event(evt)
    if not _is_event_execution_enabled(evt):
        _audit(
            event_id=evt.id,
            action_id=None,
            level="warn",
            message="execution_skipped_by_feature_flag",
            detail={"biz_key": evt.biz_key, "operator_id": int(created_by), "source": "process_event"},
        )
        evt.status = "done"
        evt.processed_at = datetime.now()
        db.session.add(evt)
        db.session.flush()
        return {"event_id": evt.id, "status": "done", "actions": [], "skipped": True}
    _auto_generate_advice_for_event(evt, actions)
    action_results = []
    for action in actions:
        try:
            result = execute_action(action, created_by=created_by)
            action.status = "done"
            action.executed_at = datetime.now()
            action.error_message = None
            db.session.add(action)
            _audit(
                event_id=evt.id,
                action_id=action.id,
                level="info",
                message="action_done",
                detail={"operator_id": int(created_by), "source": "process_event", "result": result},
            )
            action_results.append({"action_id": action.id, "status": "done", "result": result})
        except Exception as ex:
            action.retry_count = int(action.retry_count or 0) + 1
            if isinstance(ex, ValueError):
                action.status = "dead"
            else:
                action.status = "dead" if action.retry_count >= 3 else "failed"
            wait_minutes = 10 if action.retry_count <= 1 else (30 if action.retry_count == 2 else 60)
            action.next_retry_at = datetime.now() + timedelta(minutes=wait_minutes) if action.status == "failed" else None
            action.error_message = str(ex)[:500]
            db.session.add(action)
            _audit(
                event_id=evt.id,
                action_id=action.id,
                level="error",
                message="action_failed",
                detail={"operator_id": int(created_by), "source": "process_event", "error": str(ex)},
            )
            action_results.append({"action_id": action.id, "status": action.status, "error": str(ex)})

    evt.status = "done" if all(x["status"] == "done" for x in action_results) else "failed"
    evt.error_message = None if evt.status == "done" else "存在失败动作"
    evt.processed_at = datetime.now()
    db.session.add(evt)
    db.session.flush()
    return {"event_id": evt.id, "status": evt.status, "actions": action_results}


def retry_due_actions(*, created_by: int, limit: int = 200) -> int:
    if not _ops_switch_enabled("orchestrator.retry_enabled", bool(current_app.config.get("ORCHESTRATOR_RETRY_ENABLED", True))):
        return 0
    now = datetime.now()
    rows = (
        OrchestratorAction.query.filter(
            OrchestratorAction.status == "failed",
            OrchestratorAction.next_retry_at.isnot(None),
            OrchestratorAction.next_retry_at <= now,
        )
        .order_by(OrchestratorAction.id.asc())
        .limit(max(1, min(int(limit or 200), 500)))
        .all()
    )
    retried = 0
    for action in rows:
        try:
            result = execute_action(action, created_by=created_by)
            action.status = "done"
            action.executed_at = datetime.now()
            action.error_message = None
            db.session.add(action)
            _audit(
                event_id=action.event_id,
                action_id=action.id,
                level="info",
                message="action_retry_done",
                detail={"operator_id": int(created_by), "source": "retry_due_actions", "result": result},
            )
            retried += 1
        except Exception as ex:
            action.retry_count = int(action.retry_count or 0) + 1
            if isinstance(ex, ValueError):
                action.status = "dead"
            else:
                action.status = "dead" if action.retry_count >= 3 else "failed"
            wait_minutes = 10 if action.retry_count <= 1 else (30 if action.retry_count == 2 else 60)
            action.next_retry_at = datetime.now() + timedelta(minutes=wait_minutes) if action.status == "failed" else None
            action.error_message = str(ex)[:500]
            db.session.add(action)
            _audit(
                event_id=action.event_id,
                action_id=action.id,
                level="error",
                message="action_retry_failed",
                detail={"operator_id": int(created_by), "source": "retry_due_actions", "error": str(ex)},
            )
    return retried


def replay_event(event_id: int, *, created_by: int) -> Dict[str, Any]:
    return replay_event_advanced(
        event_id,
        created_by=created_by,
        dry_run=False,
        allow_high_risk=False,
        selected_actions=[],
    )


def replay_event_advanced(
    event_id: int,
    *,
    created_by: int,
    dry_run: bool = False,
    allow_high_risk: bool = False,
    selected_actions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if not _ops_switch_enabled("orchestrator.replay_enabled", bool(current_app.config.get("ORCHESTRATOR_REPLAY_ENABLED", True))):
        raise ValueError("replay 已被运行开关关闭。")
    evt = db.session.get(OrchestratorEvent, event_id)
    if not evt:
        raise ValueError("事件不存在。")
    _audit(
        event_id=int(evt.id),
        action_id=None,
        level="info",
        message="replay_advanced_requested",
        detail={
            "operator_id": int(created_by),
            "dry_run": bool(dry_run),
            "allow_high_risk": bool(allow_high_risk),
            "selected_actions": list(selected_actions or []),
            "source": "replay_event_advanced",
        },
    )
    evaluated = evaluate_event(evt)
    blocked = []
    selected: List[OrchestratorAction] = []
    allowed = set(selected_actions or [])
    for action in evaluated:
        if allowed and action.action_type not in allowed:
            continue
        if not allow_high_risk and action.action_type in HIGH_RISK_ACTIONS:
            blocked.append(action.action_type)
            continue
        selected.append(action)
    if dry_run:
        try:
            db.session.add(
                OrchestratorReplayJob(
                    event_id=int(evt.id),
                    dry_run=True,
                    allow_high_risk=bool(allow_high_risk),
                    selected_actions=[x.action_type for x in selected],
                    blocked_actions=blocked,
                    status="done",
                    created_by=int(created_by),
                )
            )
        except Exception:
            pass
        return {
            "event_id": int(evt.id),
            "dry_run": True,
            "selected_action_types": [x.action_type for x in selected],
            "blocked_action_types": blocked,
        }
    if blocked:
        db.session.add(
            OrchestratorReplayJob(
                event_id=int(evt.id),
                dry_run=False,
                allow_high_risk=bool(allow_high_risk),
                selected_actions=[x.action_type for x in selected],
                blocked_actions=blocked,
                status="blocked",
                created_by=int(created_by),
            )
        )
        raise ValueError(f"存在高风险动作被阻断: {','.join(blocked)}")
    replayed = ingest_event(
        event_type=evt.event_type,
        biz_key=evt.biz_key,
        payload=dict(evt.payload or {}),
        trace_id=evt.trace_id,
        idempotency_key=f"{evt.idempotency_key}:conditional:{int(datetime.now().timestamp())}",
        occurred_at=datetime.now(),
    )
    db.session.add(
        OrchestratorReplayJob(
            event_id=int(evt.id),
            dry_run=False,
            allow_high_risk=bool(allow_high_risk),
            selected_actions=[x.action_type for x in selected],
            blocked_actions=blocked,
            status="done",
            created_by=int(created_by),
        )
    )
    return process_event(replayed.id, created_by=created_by)


def replay_event_conditional(
    event_id: int,
    *,
    created_by: int,
    dry_run: bool = False,
    allow_high_risk: bool = False,
    only_action_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return replay_event_advanced(
        event_id,
        created_by=created_by,
        dry_run=dry_run,
        allow_high_risk=allow_high_risk,
        selected_actions=only_action_types or [],
    )


def recover_dead_action(action_id: int) -> Dict[str, Any]:
    action = db.session.get(OrchestratorAction, action_id)
    if not action:
        raise ValueError("动作不存在。")
    if action.status != "dead":
        raise ValueError("仅 dead 动作允许恢复。")
    action.status = "pending"
    action.next_retry_at = datetime.now()
    action.error_message = None
    db.session.add(action)
    _audit(event_id=action.event_id, action_id=action.id, level="warn", message="action_recovered", detail={"from": "dead", "to": "pending"})
    return {"action_id": action.id, "status": action.status}


def recover_dead_actions_batch(
    *,
    event_type: Optional[str] = None,
    action_type: Optional[str] = None,
    limit: int = 200,
) -> Dict[str, Any]:
    q = OrchestratorAction.query.join(OrchestratorEvent, OrchestratorEvent.id == OrchestratorAction.event_id).filter(
        OrchestratorAction.status == "dead"
    )
    if event_type:
        q = q.filter(OrchestratorEvent.event_type == event_type)
    if action_type:
        q = q.filter(OrchestratorAction.action_type == action_type)
    rows = q.order_by(OrchestratorAction.id.asc()).limit(max(1, min(int(limit or 200), 500))).all()
    recovered = 0
    for action in rows:
        action.status = "pending"
        action.next_retry_at = datetime.now()
        action.error_message = None
        db.session.add(action)
        recovered += 1
    return {"scanned": len(rows), "recovered": recovered}


def recompute_order(order_id: int) -> None:
    order_svc.recompute_orders_status_for_order_ids([int(order_id)])


def get_dashboard_summary() -> Dict[str, Any]:
    pending_events = OrchestratorEvent.query.filter_by(status="new").count()
    failed_events = OrchestratorEvent.query.filter_by(status="failed").count()
    pending_actions = OrchestratorAction.query.filter(OrchestratorAction.status.in_(("pending", "failed"))).count()
    dead_actions = OrchestratorAction.query.filter_by(status="dead").count()
    done_actions = OrchestratorAction.query.filter_by(status="done").count()
    total_actions = OrchestratorAction.query.count() or 1
    success_rate = float(done_actions) / float(total_actions)

    hit_rows = (
        db.session.query(OrchestratorAction.action_type, func.count(OrchestratorAction.id))
        .group_by(OrchestratorAction.action_type)
        .all()
    )
    last_24h = datetime.now() - timedelta(hours=24)
    done_24h = OrchestratorAction.query.filter(
        OrchestratorAction.status == "done",
        OrchestratorAction.updated_at >= last_24h,
    ).count()
    total_24h = OrchestratorAction.query.filter(OrchestratorAction.updated_at >= last_24h).count() or 1
    dead_actions_24h = OrchestratorAction.query.filter(
        OrchestratorAction.status == "dead",
        OrchestratorAction.updated_at >= last_24h,
    ).count()
    failed_events_24h = OrchestratorEvent.query.filter(
        OrchestratorEvent.status == "failed",
        OrchestratorEvent.processed_at.isnot(None),
        OrchestratorEvent.processed_at >= last_24h,
    ).count()
    replay_blocked_24h = OrchestratorReplayJob.query.filter(
        OrchestratorReplayJob.status == "blocked",
        OrchestratorReplayJob.created_at >= last_24h,
    ).count()
    scan_actions_24h = (
        db.session.query(func.count(OrchestratorAction.id))
        .join(OrchestratorEvent, OrchestratorEvent.id == OrchestratorAction.event_id)
        .filter(
            OrchestratorEvent.event_type == EVENT_ORDER_OVERDUE_SCAN,
            OrchestratorAction.created_at >= last_24h,
        )
        .scalar()
        or 0
    )
    ai = get_ai_adoption_metrics()
    return {
        "pending_events": pending_events,
        "failed_events": failed_events,
        "pending_actions": pending_actions,
        "dead_actions": dead_actions,
        "success_rate": round(success_rate, 4),
        "success_rate_24h": round(float(done_24h) / float(total_24h), 4),
        "dead_actions_24h": int(dead_actions_24h),
        "failed_events_24h": int(failed_events_24h),
        "replay_blocked_24h": int(replay_blocked_24h),
        "scan_actions_24h": int(scan_actions_24h),
        "action_hits": {k: int(v) for k, v in hit_rows},
        "ai_metrics": ai,
    }


def get_active_rule_profiles() -> List[Dict[str, Any]]:
    rows = (
        OrchestratorRuleProfile.query.filter_by(is_active=True)
        .order_by(OrchestratorRuleProfile.priority.asc(), OrchestratorRuleProfile.id.asc())
        .all()
    )
    return [
        {
            "id": int(x.id),
            "rule_code": x.rule_code,
            "rule_name": x.rule_name,
            "allow_alternative": bool(x.allow_alternative),
            "allow_outsource": bool(x.allow_outsource),
            "allow_secondary_supplier": bool(x.allow_secondary_supplier),
            "priority": int(x.priority or 0),
        }
        for x in rows
    ]


def _is_event_execution_enabled(event: OrchestratorEvent) -> bool:
    if bool(current_app.config.get("ORCHESTRATOR_KILL_SWITCH")):
        return False
    company_whitelist = [x.strip() for x in str(current_app.config.get("ORCHESTRATOR_COMPANY_WHITELIST") or "").split(",") if x.strip()]
    if company_whitelist:
        company_id = str((event.payload or {}).get("company_id") or "").strip()
        if company_id and company_id not in company_whitelist:
            return False
    biz_key_whitelist = [x.strip() for x in str(current_app.config.get("ORCHESTRATOR_BIZ_KEY_WHITELIST") or "").split(",") if x.strip()]
    if biz_key_whitelist:
        if str(event.biz_key or "") not in biz_key_whitelist:
            return False
    return True


def get_order_timeline(order_id: int, *, limit: int = 500) -> Dict[str, Any]:
    oid = int(order_id)
    key = f"order:{oid}"
    preplan_rows = (
        db.session.query(ProductionPreplanLine.preplan_id)
        .join(OrderItem, OrderItem.id == ProductionPreplanLine.source_order_item_id)
        .filter(OrderItem.order_id == oid)
        .distinct()
        .all()
    )
    related_preplan_ids = {int(r[0]) for r in preplan_rows if r and r[0]}

    # 兼容两类口径：
    # 1) biz_key=order:{order_id}
    # 2) payload.order_id={order_id}（例如 demo 数据 biz_key 非数字）
    # 同时把 payload.preplan_id 命中的生产测算事件也纳入订单轨迹。
    candidates = (
        OrchestratorEvent.query.filter(
            OrchestratorEvent.biz_key.like("order:%")
            | OrchestratorEvent.biz_key.like("preplan:%")
        )
        .order_by(OrchestratorEvent.id.desc())
        .limit(max(50, min(int(limit or 500), 1000)))
        .all()
    )
    events: List[OrchestratorEvent] = []
    for e in candidates:
        payload = dict(e.payload or {})
        p_order_id = int(payload.get("order_id") or 0)
        p_preplan_id = int(payload.get("preplan_id") or 0)
        if e.biz_key == key or p_order_id == oid or (
            p_preplan_id > 0 and p_preplan_id in related_preplan_ids
        ):
            events.append(e)
    event_ids = [e.id for e in events]
    actions = (
        OrchestratorAction.query.filter(OrchestratorAction.event_id.in_(event_ids))
        .order_by(OrchestratorAction.id.desc())
        .all()
        if event_ids
        else []
    )
    actions_by_event: Dict[int, List[OrchestratorAction]] = {}
    for a in actions:
        actions_by_event.setdefault(int(a.event_id), []).append(a)
    return {
        "order_id": int(order_id),
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "status": e.status,
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
                "actions": [
                    {
                        "id": a.id,
                        "action_type": a.action_type,
                        "status": a.status,
                        "retry_count": int(a.retry_count or 0),
                        "error_message": a.error_message,
                    }
                    for a in actions_by_event.get(int(e.id), [])
                ],
            }
            for e in events
        ],
    }


def get_event_actions(event_id: int) -> List[Dict[str, Any]]:
    rows = OrchestratorAction.query.filter_by(event_id=event_id).order_by(OrchestratorAction.id.asc()).all()
    return [
        {
            "id": x.id,
            "action_type": x.action_type,
            "status": x.status,
            "retry_count": int(x.retry_count or 0),
            "next_retry_at": x.next_retry_at.isoformat() if x.next_retry_at else None,
            "error_message": x.error_message,
        }
        for x in rows
    ]


def emit_overdue_scan_event(*, source: str = "system.scan", source_id: int = 1, version: int = 1) -> OrchestratorEvent:
    if not _ops_switch_enabled(
        "orchestrator.overdue_scan_enabled",
        bool(current_app.config.get("ORCHESTRATOR_OVERDUE_SCAN_ENABLED", True)),
    ):
        raise ValueError("overdue scan 已被运行开关关闭。")
    return emit_event(
        event_type=EVENT_ORDER_OVERDUE_SCAN,
        biz_key=f"scan:{datetime.now().strftime('%Y%m%d%H%M')}",
        payload={"source_id": int(source_id), "version": int(version), "source": source},
    )


def create_ai_advice(
    *,
    event_id: int,
    advice_type: str,
    recommended_action: str,
    confidence: Optional[Decimal],
    reason: Optional[str],
    meta: Optional[Dict[str, Any]],
) -> OrchestratorAiAdvice:
    next_id = (db.session.query(func.coalesce(func.max(OrchestratorAiAdvice.id), 0)).scalar() or 0) + 1
    row = OrchestratorAiAdvice(
        id=int(next_id),
        event_id=event_id,
        advice_type=advice_type,
        recommended_action=recommended_action,
        confidence=confidence,
        reason=reason,
        meta=meta or {},
        is_adopted=False,
    )
    db.session.add(row)
    db.session.flush()
    db.session.add(
        OrchestratorAiAdviceMetric(
            id=int((db.session.query(func.coalesce(func.max(OrchestratorAiAdviceMetric.id), 0)).scalar() or 0) + 1),
            advice_id=int(row.id),
            event_id=int(event_id),
            advice_type=advice_type,
            is_adopted=False,
            adopted_latency_seconds=None,
            result_score=None,
            metric_note="created",
        )
    )
    return row


def get_ai_adoption_metrics() -> Dict[str, Any]:
    last_24h = datetime.now() - timedelta(hours=24)
    total = OrchestratorAiAdvice.query.count()
    adopted = OrchestratorAiAdvice.query.filter_by(is_adopted=True).count()
    total_24h = OrchestratorAiAdvice.query.filter(OrchestratorAiAdvice.created_at >= last_24h).count()
    adopted_24h = OrchestratorAiAdvice.query.filter(
        OrchestratorAiAdvice.created_at >= last_24h,
        OrchestratorAiAdvice.is_adopted == 1,
    ).count()
    rows = (
        db.session.query(OrchestratorAiAdvice.advice_type, func.count(OrchestratorAiAdvice.id))
        .group_by(OrchestratorAiAdvice.advice_type)
        .all()
    )
    avg_latency = (
        db.session.query(func.avg(OrchestratorAiAdviceMetric.adopted_latency_seconds))
        .filter(OrchestratorAiAdviceMetric.is_adopted == 1)
        .scalar()
    )
    return {
        "total": int(total),
        "adopted": int(adopted),
        "adoption_rate": round(float(adopted) / float(total), 4) if total else 0.0,
        "adoption_rate_24h": round(float(adopted_24h) / float(total_24h), 4) if total_24h else 0.0,
        "advice_type_hits": {str(k): int(v) for k, v in rows},
        "avg_adopt_latency_seconds": int(avg_latency or 0),
    }


def adopt_ai_advice(advice_id: int, *, adopted_by: int) -> OrchestratorAiAdvice:
    row = db.session.get(OrchestratorAiAdvice, advice_id)
    if not row:
        raise ValueError("AI建议不存在。")
    row.is_adopted = True
    row.adopted_by = adopted_by
    row.adopted_at = datetime.now()
    db.session.add(row)
    metric = (
        OrchestratorAiAdviceMetric.query.filter_by(advice_id=int(row.id))
        .order_by(OrchestratorAiAdviceMetric.id.desc())
        .first()
    )
    if metric:
        metric.is_adopted = True
        if row.created_at:
            metric.adopted_latency_seconds = int((row.adopted_at - row.created_at).total_seconds())
        metric.metric_note = "adopted"
        db.session.add(metric)
    return row


def update_ai_advice_metric_result(
    *,
    advice_id: int,
    result_score: Optional[Decimal],
    metric_note: Optional[str],
) -> OrchestratorAiAdviceMetric:
    metric = (
        OrchestratorAiAdviceMetric.query.filter_by(advice_id=int(advice_id))
        .order_by(OrchestratorAiAdviceMetric.id.desc())
        .first()
    )
    if not metric:
        raise ValueError("metric 不存在，请先创建或采纳 AI 建议。")
    metric.result_score = result_score
    metric.metric_note = metric_note or metric.metric_note
    db.session.add(metric)
    return metric


def update_or_create_ai_metric_from_advice(advice_id: int) -> Optional[OrchestratorAiAdviceMetric]:
    advice = db.session.get(OrchestratorAiAdvice, int(advice_id))
    if not advice:
        return None
    metric = (
        OrchestratorAiAdviceMetric.query.filter_by(advice_id=int(advice.id))
        .order_by(OrchestratorAiAdviceMetric.id.desc())
        .first()
    )
    if not metric:
        metric = OrchestratorAiAdviceMetric(
            id=int((db.session.query(func.coalesce(func.max(OrchestratorAiAdviceMetric.id), 0)).scalar() or 0) + 1),
            advice_id=int(advice.id),
            event_id=int(advice.event_id),
            advice_type=str(advice.advice_type),
            is_adopted=bool(advice.is_adopted),
            metric_note="backfill",
        )
    else:
        metric.is_adopted = bool(advice.is_adopted)
        metric.metric_note = metric.metric_note or "backfill"
    if advice.is_adopted and advice.adopted_at and advice.created_at:
        metric.adopted_latency_seconds = int((advice.adopted_at - advice.created_at).total_seconds())
    db.session.add(metric)
    return metric


def _ops_switch_enabled(flag_key: str, default_enabled: bool = True) -> bool:
    try:
        row = db.session.execute(
            db.text("SELECT flag_value FROM sys_feature_flag WHERE flag_key=:k LIMIT 1"),
            {"k": str(flag_key)},
        ).mappings().first()
        if row and row.get("flag_value") is not None:
            value = str(row.get("flag_value")).strip().lower()
            return value in ("1", "true", "on", "yes")
    except Exception:
        return bool(default_enabled)
    return bool(default_enabled)


def get_health_summary() -> Dict[str, Any]:
    dash = get_dashboard_summary()
    dead_actions = int(dash.get("dead_actions", 0))
    failed_events_24h = int(dash.get("failed_events_24h", 0))
    success_rate_24h = float(dash.get("success_rate_24h", 0.0))
    healthy = dead_actions == 0 and failed_events_24h <= 10 and success_rate_24h >= 0.9
    return {
        "healthy": healthy,
        "dead_actions": dead_actions,
        "failed_events_24h": failed_events_24h,
        "success_rate_24h": success_rate_24h,
        "thresholds": {"dead_actions": 0, "failed_events_24h": 10, "success_rate_24h_min": 0.9},
    }
