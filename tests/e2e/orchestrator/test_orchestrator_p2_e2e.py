from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app import create_app, db
from app.config import Config
from app.models import (
    OrchestratorAction,
    OrchestratorAiAdvice,
    OrchestratorAiAdviceMetric,
    OrchestratorAuditLog,
    OrchestratorEvent,
)
from app.services import orchestrator_engine
from app.services.orchestrator_contracts import (
    EVENT_MACHINE_ABNORMAL,
    EVENT_ORDER_CHANGED,
    EVENT_PRODUCTION_OPERATION_REPORTED,
    EVENT_QUALITY_FAILED,
    build_idempotency_key,
)


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def app_ctx(app):
    with app.app_context():
        yield


def _mk_event(event_type: str, payload: dict) -> OrchestratorEvent:
    return orchestrator_engine.ingest_event(
        event_type=event_type,
        biz_key=f"order:{int(payload.get('order_id') or 1)}",
        payload=payload,
        trace_id=None,
        idempotency_key=build_idempotency_key(
            event_type=event_type,
            biz_key=f"order:{int(payload.get('order_id') or 1)}",
            source_id=payload.get("source_id"),
            version=payload.get("version"),
        ),
        occurred_at=datetime.now(),
    )


def test_e2e_01_ingest_idempotent(app_ctx):
    payload = {"order_id": 1, "source_id": 1, "version": 1}
    idem = build_idempotency_key(event_type=EVENT_ORDER_CHANGED, biz_key="order:1", source_id=1, version=1)
    a = orchestrator_engine.ingest_event(
        event_type=EVENT_ORDER_CHANGED,
        biz_key="order:1",
        payload=payload,
        trace_id=None,
        idempotency_key=idem,
        occurred_at=datetime.now(),
    )
    b = orchestrator_engine.ingest_event(
        event_type=EVENT_ORDER_CHANGED,
        biz_key="order:1",
        payload=payload,
        trace_id=None,
        idempotency_key=idem,
        occurred_at=datetime.now(),
    )
    db.session.commit()
    assert a.id == b.id


def test_e2e_02_payload_contract_validation(app_ctx):
    with pytest.raises(ValueError):
        orchestrator_engine.ingest_event(
            event_type=EVENT_ORDER_CHANGED,
            biz_key="order:1",
            payload={"order_id": 1},
            trace_id=None,
            idempotency_key="bad:1",
            occurred_at=datetime.now(),
        )


def test_e2e_03_rule_enhance_three_paths(app_ctx, monkeypatch):
    monkeypatch.setattr(
        orchestrator_engine,
        "_order_shortage_summary",
        lambda _oid: {"has_shortage": True, "lines": [{"order_item_id": 1, "product_id": 1, "shortage_qty": 10}]},
    )
    evt = _mk_event(
        EVENT_ORDER_CHANGED,
        {
            "order_id": 2,
            "source_id": 2,
            "version": 1,
            "allow_alternative": True,
            "allow_outsource": True,
            "allow_secondary_supplier": True,
        },
    )
    db.session.flush()
    actions = orchestrator_engine.evaluate_event(evt)
    kinds = {x.action_type for x in actions}
    assert "ApplyAlternativeMaterial" in kinds
    assert "CreateOutsourceOrder" in kinds
    assert "SwitchSecondarySupplier" in kinds


def test_e2e_04_operation_reported_event_action(app_ctx):
    evt = _mk_event(
        EVENT_PRODUCTION_OPERATION_REPORTED,
        {"order_id": 9, "work_order_id": 10, "source_id": 10, "version": 1},
    )
    db.session.flush()
    actions = orchestrator_engine.evaluate_event(evt)
    assert any(x.action_type == "MoveOrderStatus" for x in actions)


def test_e2e_05_quality_failed_actions(app_ctx):
    evt = _mk_event(
        EVENT_QUALITY_FAILED,
        {"order_id": 3, "qc_result": "failed", "source_id": 3, "version": 1},
    )
    db.session.flush()
    actions = orchestrator_engine.evaluate_event(evt)
    kinds = [x.action_type for x in actions]
    assert "TriggerQualityHold" in kinds
    assert "TriggerQualityRework" in kinds


def test_e2e_06_machine_abnormal_generates_alert_action(app_ctx):
    evt = orchestrator_engine.ingest_event(
        event_type=EVENT_MACHINE_ABNORMAL,
        biz_key="incident:7",
        payload={"incident_id": 7, "severity": "H", "source_id": 7, "version": 1},
        trace_id=None,
        idempotency_key="incident:7:1",
        occurred_at=datetime.now(),
    )
    db.session.flush()
    actions = orchestrator_engine.evaluate_event(evt)
    assert any(x.action_type == "EscalateDeviceAlert" for x in actions)


def test_e2e_07_conditional_replay_dry_run(app_ctx, monkeypatch):
    monkeypatch.setattr(
        orchestrator_engine,
        "evaluate_event",
        lambda _evt: [
            OrchestratorAction(event_id=1, action_type="CreatePreplan", action_key="k1", payload={}),
            OrchestratorAction(event_id=1, action_type="MoveOrderStatus", action_key="k2", payload={}),
        ],
    )
    evt = _mk_event(EVENT_ORDER_CHANGED, {"order_id": 5, "source_id": 5, "version": 1})
    db.session.commit()
    out = orchestrator_engine.replay_event_conditional(evt.id, created_by=1, dry_run=True, allow_high_risk=False)
    assert out["dry_run"] is True
    assert "CreatePreplan" in out["blocked_action_types"]


def test_e2e_08_batch_recover_dead(app_ctx):
    evt = _mk_event(EVENT_ORDER_CHANGED, {"order_id": 6, "source_id": 6, "version": 1})
    db.session.flush()
    action = OrchestratorAction(
        id=9001,
        event_id=evt.id,
        action_type="CreateProcurementRequest",
        action_key="dead:1",
        payload={},
        status="dead",
    )
    db.session.add(action)
    db.session.commit()
    out = orchestrator_engine.recover_dead_actions_batch(event_type=EVENT_ORDER_CHANGED, limit=50)
    db.session.commit()
    db.session.refresh(action)
    assert out["recovered"] >= 1
    assert action.status == "pending"


def test_e2e_09_ai_advice_create_and_adopt_metric(app_ctx):
    evt = _mk_event(EVENT_ORDER_CHANGED, {"order_id": 8, "source_id": 8, "version": 1})
    db.session.flush()
    advice = orchestrator_engine.create_ai_advice(
        event_id=evt.id,
        advice_type="supplier_strategy",
        recommended_action="SwitchSecondarySupplier",
        confidence=Decimal("0.8000"),
        reason="test",
        meta={},
    )
    db.session.commit()
    adopted = orchestrator_engine.adopt_ai_advice(advice.id, adopted_by=1)
    db.session.commit()
    metric = OrchestratorAiAdviceMetric.query.filter_by(advice_id=advice.id).first()
    assert adopted.is_adopted is True
    assert metric is not None and metric.is_adopted is True


def test_e2e_10_ai_metrics_endpoint_data(app_ctx):
    evt = _mk_event(EVENT_ORDER_CHANGED, {"order_id": 11, "source_id": 11, "version": 1})
    db.session.flush()
    advice = OrchestratorAiAdvice(
        id=7001,
        event_id=evt.id,
        advice_type="material_strategy",
        recommended_action="ApplyAlternativeMaterial",
        confidence=Decimal("0.7000"),
        reason="seed",
        meta={},
        is_adopted=True,
        adopted_by=1,
        adopted_at=datetime.now(),
    )
    db.session.add(advice)
    db.session.flush()
    db.session.add(
        OrchestratorAiAdviceMetric(
            id=8001,
            advice_id=advice.id,
            event_id=evt.id,
            advice_type=advice.advice_type,
            is_adopted=True,
            adopted_latency_seconds=5,
            metric_note="seeded",
        )
    )
    db.session.commit()
    metrics = orchestrator_engine.get_ai_adoption_metrics()
    assert metrics["total"] >= 1
    assert "material_strategy" in metrics["advice_type_hits"]


def test_e2e_11_process_event_generates_audit(app_ctx, monkeypatch):
    monkeypatch.setattr(
        orchestrator_engine,
        "execute_action",
        lambda action, created_by: {"action_type": action.action_type, "created_by": created_by},
    )
    evt = _mk_event(EVENT_ORDER_CHANGED, {"order_id": 12, "source_id": 12, "version": 1})
    db.session.commit()
    out = orchestrator_engine.process_event(evt.id, created_by=1)
    db.session.commit()
    logs = OrchestratorAuditLog.query.filter_by(event_id=evt.id).all()
    assert out["event_id"] == evt.id
    assert len(logs) >= 1
