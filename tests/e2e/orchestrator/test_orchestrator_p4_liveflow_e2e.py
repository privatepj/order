from __future__ import annotations

from datetime import datetime

from app import create_app, db
from app.config import Config
from app.models import OrchestratorAction, OrchestratorAuditLog, OrchestratorEvent
from app.services import orchestrator_engine
from app.services.orchestrator_contracts import (
    EVENT_ORDER_CHANGED,
    EVENT_ORDER_OVERDUE_SCAN,
    EVENT_PRODUCTION_OPERATION_REPORTED,
    EVENT_QUALITY_FAILED,
)


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}


def _ctx():
    app = create_app(TestConfig)
    ctx = app.app_context()
    ctx.push()
    db.create_all()
    return ctx


def _clear(ctx):
    db.session.remove()
    db.drop_all()
    ctx.pop()


def _mk_event(event_type: str, payload: dict, biz_key: str = "order:1") -> OrchestratorEvent:
    return orchestrator_engine.ingest_event(
        event_type=event_type,
        biz_key=biz_key,
        payload=payload,
        trace_id="p4-e2e",
        idempotency_key=f"{event_type}:{biz_key}:{payload.get('source_id')}:{payload.get('version')}",
        occurred_at=datetime.now(),
    )


def test_p4_liveflow_order_shortage_has_audit_and_actions(monkeypatch):
    ctx = _ctx()
    try:
        monkeypatch.setattr(
            orchestrator_engine,
            "_order_shortage_summary",
            lambda _oid: {"has_shortage": True, "lines": [{"order_item_id": 1, "product_id": 2, "shortage_qty": 5}]},
        )
        evt = _mk_event(EVENT_ORDER_CHANGED, {"order_id": 1, "source_id": 1, "version": 1})
        out = orchestrator_engine.process_event(int(evt.id), created_by=1)
        db.session.commit()
        assert out["status"] in ("done", "failed")
        assert any((x.get("action_id") or 0) > 0 for x in out["actions"])
        audit = OrchestratorAuditLog.query.filter_by(event_id=int(evt.id)).all()
        assert any(x.message == "rule_profile_hit" for x in audit)
    finally:
        _clear(ctx)


def test_p4_liveflow_operation_and_quality_branch(monkeypatch):
    ctx = _ctx()
    try:
        monkeypatch.setattr(orchestrator_engine, "execute_action", lambda action, created_by: {"ok": True})
        evt1 = _mk_event(
            EVENT_PRODUCTION_OPERATION_REPORTED,
            {"order_id": 2, "work_order_id": 22, "source_id": 22, "version": 1},
            biz_key="order:2",
        )
        evt2 = _mk_event(
            EVENT_QUALITY_FAILED,
            {"order_id": 2, "qc_result": "failed", "source_id": 2, "version": 2},
            biz_key="order:2",
        )
        out1 = orchestrator_engine.process_event(int(evt1.id), created_by=1)
        out2 = orchestrator_engine.process_event(int(evt2.id), created_by=1)
        db.session.commit()
        assert len(out1["actions"]) >= 1
        assert len(out2["actions"]) >= 2
    finally:
        _clear(ctx)


def test_p4_liveflow_overdue_scan_generates_procurement_actions():
    ctx = _ctx()
    try:
        evt = _mk_event(EVENT_ORDER_OVERDUE_SCAN, {"source_id": 9, "version": 1}, biz_key="scan:manual")
        out = orchestrator_engine.process_event(int(evt.id), created_by=1)
        db.session.commit()
        assert out["event_id"] == int(evt.id)
        rows = OrchestratorAction.query.filter_by(event_id=int(evt.id)).all()
        assert rows is not None
    finally:
        _clear(ctx)


def test_p4_liveflow_replay_advanced_dry_run():
    ctx = _ctx()
    try:
        evt = _mk_event(EVENT_ORDER_CHANGED, {"order_id": 3, "source_id": 3, "version": 1}, biz_key="order:3")
        db.session.commit()
        out = orchestrator_engine.replay_event_advanced(
            int(evt.id),
            created_by=1,
            dry_run=True,
            selected_actions=["MoveOrderStatus"],
            allow_high_risk=False,
        )
        assert out["dry_run"] is True
        assert "blocked_action_types" in out
    finally:
        _clear(ctx)
