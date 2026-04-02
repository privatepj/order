from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from flask import jsonify, request
from flask_login import current_user, login_required

from app import db
from app.auth.capabilities import current_user_can_cap
from app.auth.decorators import capability_required, menu_required
from app.models import OrchestratorAiAdvice, OrchestratorEvent
from app.services import orchestrator_engine
from app.services.orchestrator_contracts import (
    EVENT_MACHINE_ABNORMAL,
    EVENT_MACHINE_RECOVERED,
    EVENT_PRODUCTION_OPERATION_REPORTED,
    EVENT_PRODUCTION_REPORTED,
    EVENT_QUALITY_FAILED,
    EVENT_QUALITY_INSPECTION_STARTED,
    EVENT_QUALITY_PASSED,
    EVENT_QUALITY_REWORKED,
    build_idempotency_key,
)


def _parse_dt(raw):
    s = (raw or "").strip()
    if not s:
        return datetime.now()
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.now()


def register_orchestrator_routes(bp):
    @bp.route("/orchestrator/events/ingest", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_event_ingest():
        data = request.get_json(silent=True) or {}
        event_type = (data.get("event_type") or "").strip()
        biz_key = (data.get("biz_key") or "").strip()
        payload = data.get("payload") or {}
        source_id = payload.get("source_id")
        version = payload.get("version")
        if not event_type or not biz_key:
            return jsonify({"ok": False, "error": "event_type/biz_key 必填"}), 400
        idempotency_key = (data.get("idempotency_key") or "").strip() or build_idempotency_key(
            event_type=event_type,
            biz_key=biz_key,
            source_id=source_id,
            version=version,
        )
        try:
            evt = orchestrator_engine.ingest_event(
                event_type=event_type,
                biz_key=biz_key,
                payload=payload,
                trace_id=(data.get("trace_id") or "").strip() or None,
                idempotency_key=idempotency_key,
                occurred_at=_parse_dt(data.get("occurred_at")),
            )
            db.session.commit()
            return jsonify({"ok": True, "event_id": evt.id, "status": evt.status})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/events/<int:event_id>/run", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_event_run(event_id: int):
        try:
            out = orchestrator_engine.process_event(event_id, created_by=int(current_user.id))
            db.session.commit()
            return jsonify({"ok": True, "data": out})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/actions/retry", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_retry_actions():
        try:
            n = orchestrator_engine.retry_due_actions(created_by=int(current_user.id))
            db.session.commit()
            return jsonify({"ok": True, "retried": n})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/events/<int:event_id>/replay", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_event_replay(event_id: int):
        try:
            out = orchestrator_engine.replay_event(event_id, created_by=int(current_user.id))
            db.session.commit()
            return jsonify({"ok": True, "data": out})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/events/<int:event_id>/replay-conditional", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_event_replay_conditional(event_id: int):
        data = request.get_json(silent=True) or {}
        try:
            out = orchestrator_engine.replay_event_conditional(
                event_id,
                created_by=int(current_user.id),
                dry_run=bool(data.get("dry_run")),
                allow_high_risk=bool(data.get("allow_high_risk")),
                only_action_types=[str(x) for x in (data.get("only_action_types") or []) if str(x).strip()],
            )
            db.session.commit()
            return jsonify({"ok": True, "data": out})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/events/<int:event_id>/replay-advanced", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_event_replay_advanced(event_id: int):
        data = request.get_json(silent=True) or {}
        try:
            if bool(data.get("allow_high_risk")) and not current_user_can_cap("orchestrator.replay.high_risk"):
                return jsonify({"ok": False, "error": "缺少高风险重放权限"}), 403
            out = orchestrator_engine.replay_event_advanced(
                event_id,
                created_by=int(current_user.id),
                dry_run=bool(data.get("dry_run")),
                allow_high_risk=bool(data.get("allow_high_risk")),
                selected_actions=[str(x) for x in (data.get("selected_actions") or []) if str(x).strip()],
            )
            db.session.commit()
            return jsonify({"ok": True, "data": out})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/actions/<int:action_id>/recover", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_action_recover(action_id: int):
        try:
            out = orchestrator_engine.recover_dead_action(action_id)
            db.session.commit()
            return jsonify({"ok": True, "data": out})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/actions/recover-batch", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("orchestrator.recover.batch")
    def orchestrator_action_recover_batch():
        data = request.get_json(silent=True) or {}
        try:
            out = orchestrator_engine.recover_dead_actions_batch(
                event_type=(data.get("event_type") or "").strip() or None,
                action_type=(data.get("action_type") or "").strip() or None,
                limit=int(data.get("limit") or 200),
            )
            db.session.commit()
            return jsonify({"ok": True, "data": out})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/orders/<int:order_id>/recompute", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_order_recompute(order_id: int):
        try:
            orchestrator_engine.recompute_order(order_id)
            db.session.commit()
            return jsonify({"ok": True, "order_id": order_id})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/dashboard", methods=["GET"])
    @login_required
    @menu_required("production_preplan")
    def orchestrator_dashboard():
        return jsonify({"ok": True, "data": orchestrator_engine.get_dashboard_summary()})

    @bp.route("/orchestrator/health", methods=["GET"])
    @login_required
    @menu_required("production_preplan")
    def orchestrator_health():
        return jsonify({"ok": True, "data": orchestrator_engine.get_health_summary()})

    @bp.route("/orchestrator/rules", methods=["GET"])
    @login_required
    @menu_required("production_preplan")
    def orchestrator_rules():
        return jsonify({"ok": True, "items": orchestrator_engine.get_active_rule_profiles()})

    @bp.route("/orchestrator/orders/<int:order_id>/timeline", methods=["GET"])
    @login_required
    @menu_required("production_preplan")
    def orchestrator_order_timeline(order_id: int):
        return jsonify({"ok": True, "data": orchestrator_engine.get_order_timeline(order_id)})

    @bp.route("/orchestrator/events/<int:event_id>/actions", methods=["GET"])
    @login_required
    @menu_required("production_preplan")
    def orchestrator_event_actions(event_id: int):
        return jsonify({"ok": True, "items": orchestrator_engine.get_event_actions(event_id)})

    @bp.route("/orchestrator/orders/<int:order_id>/production-reported", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_order_production_reported(order_id: int):
        try:
            evt = orchestrator_engine.emit_event(
                event_type=EVENT_PRODUCTION_REPORTED,
                biz_key=f"order:{int(order_id)}",
                payload={
                    "order_id": int(order_id),
                    "source_id": int(order_id),
                    "version": int(datetime.now().timestamp()),
                    "source": "routes_orchestrator.production_reported",
                },
            )
            out = orchestrator_engine.process_event(int(evt.id), created_by=int(current_user.id))
            db.session.commit()
            return jsonify({"ok": True, "data": out})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/orders/<int:order_id>/quality-passed", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_order_quality_passed(order_id: int):
        try:
            evt = orchestrator_engine.emit_event(
                event_type=EVENT_QUALITY_PASSED,
                biz_key=f"order:{int(order_id)}",
                payload={
                    "order_id": int(order_id),
                    "source_id": int(order_id),
                    "version": int(datetime.now().timestamp()),
                    "source": "routes_orchestrator.quality_passed",
                },
            )
            out = orchestrator_engine.process_event(int(evt.id), created_by=int(current_user.id))
            db.session.commit()
            return jsonify({"ok": True, "data": out})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/orders/<int:order_id>/operation-reported", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_order_operation_reported(order_id: int):
        data = request.get_json(silent=True) or {}
        try:
            evt = orchestrator_engine.emit_event(
                event_type=EVENT_PRODUCTION_OPERATION_REPORTED,
                biz_key=f"order:{int(order_id)}",
                payload={
                    "order_id": int(order_id),
                    "work_order_id": int(data.get("work_order_id") or 0),
                    "source_id": int(data.get("work_order_id") or order_id),
                    "version": int(datetime.now().timestamp()),
                    "source": "routes_orchestrator.operation_reported",
                },
            )
            out = orchestrator_engine.process_event(int(evt.id), created_by=int(current_user.id))
            db.session.commit()
            return jsonify({"ok": True, "data": out})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/orders/<int:order_id>/quality-started", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_order_quality_started(order_id: int):
        try:
            evt = orchestrator_engine.emit_event(
                event_type=EVENT_QUALITY_INSPECTION_STARTED,
                biz_key=f"order:{int(order_id)}",
                payload={
                    "order_id": int(order_id),
                    "source_id": int(order_id),
                    "version": int(datetime.now().timestamp()),
                    "source": "routes_orchestrator.quality_started",
                },
            )
            out = orchestrator_engine.process_event(int(evt.id), created_by=int(current_user.id))
            db.session.commit()
            return jsonify({"ok": True, "data": out})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/orders/<int:order_id>/quality-failed", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_order_quality_failed(order_id: int):
        data = request.get_json(silent=True) or {}
        try:
            evt = orchestrator_engine.emit_event(
                event_type=EVENT_QUALITY_FAILED,
                biz_key=f"order:{int(order_id)}",
                payload={
                    "order_id": int(order_id),
                    "qc_result": (data.get("qc_result") or "failed").strip(),
                    "source_id": int(order_id),
                    "version": int(datetime.now().timestamp()),
                    "source": "routes_orchestrator.quality_failed",
                },
            )
            out = orchestrator_engine.process_event(int(evt.id), created_by=int(current_user.id))
            db.session.commit()
            return jsonify({"ok": True, "data": out})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/orders/<int:order_id>/quality-reworked", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_order_quality_reworked(order_id: int):
        try:
            evt = orchestrator_engine.emit_event(
                event_type=EVENT_QUALITY_REWORKED,
                biz_key=f"order:{int(order_id)}",
                payload={
                    "order_id": int(order_id),
                    "source_id": int(order_id),
                    "version": int(datetime.now().timestamp()),
                    "source": "routes_orchestrator.quality_reworked",
                },
            )
            out = orchestrator_engine.process_event(int(evt.id), created_by=int(current_user.id))
            db.session.commit()
            return jsonify({"ok": True, "data": out})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/machines/incidents/<int:incident_id>/abnormal", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_machine_abnormal(incident_id: int):
        data = request.get_json(silent=True) or {}
        try:
            evt = orchestrator_engine.emit_event(
                event_type=EVENT_MACHINE_ABNORMAL,
                biz_key=f"incident:{int(incident_id)}",
                payload={
                    "incident_id": int(incident_id),
                    "severity": (data.get("severity") or "M").strip(),
                    "source_id": int(incident_id),
                    "version": int(datetime.now().timestamp()),
                    "source": "routes_orchestrator.machine_abnormal",
                },
            )
            out = orchestrator_engine.process_event(int(evt.id), created_by=int(current_user.id))
            db.session.commit()
            return jsonify({"ok": True, "data": out})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/machines/incidents/<int:incident_id>/recovered", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_machine_recovered(incident_id: int):
        try:
            evt = orchestrator_engine.emit_event(
                event_type=EVENT_MACHINE_RECOVERED,
                biz_key=f"incident:{int(incident_id)}",
                payload={
                    "incident_id": int(incident_id),
                    "source_id": int(incident_id),
                    "version": int(datetime.now().timestamp()),
                    "source": "routes_orchestrator.machine_recovered",
                },
            )
            out = orchestrator_engine.process_event(int(evt.id), created_by=int(current_user.id))
            db.session.commit()
            return jsonify({"ok": True, "data": out})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/scan/overdue", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_scan_overdue():
        try:
            evt = orchestrator_engine.emit_overdue_scan_event(
                source="routes_orchestrator.scan_overdue",
                source_id=int(current_user.id),
                version=int(datetime.now().timestamp()),
            )
            out = orchestrator_engine.process_event(int(evt.id), created_by=int(current_user.id))
            db.session.commit()
            return jsonify({"ok": True, "data": out})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/ai-advice", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_ai_advice_create():
        data = request.get_json(silent=True) or {}
        event_id = int(data.get("event_id") or 0)
        if event_id <= 0 or not db.session.get(OrchestratorEvent, event_id):
            return jsonify({"ok": False, "error": "event_id 无效"}), 400
        confidence = data.get("confidence")
        c = Decimal(str(confidence)) if confidence is not None else None
        try:
            row = orchestrator_engine.create_ai_advice(
                event_id=event_id,
                advice_type=(data.get("advice_type") or "priority").strip(),
                recommended_action=(data.get("recommended_action") or "").strip(),
                confidence=c,
                reason=(data.get("reason") or "").strip() or None,
                meta=data.get("meta") or {},
            )
            if not row.recommended_action:
                raise ValueError("recommended_action 必填")
            db.session.commit()
            return jsonify({"ok": True, "advice_id": row.id})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/ai-advice/<int:advice_id>/adopt", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def orchestrator_ai_advice_adopt(advice_id: int):
        try:
            row = orchestrator_engine.adopt_ai_advice(advice_id, adopted_by=int(current_user.id))
            db.session.commit()
            return jsonify({"ok": True, "advice_id": row.id, "adopted": True})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400

    @bp.route("/orchestrator/ai-advice", methods=["GET"])
    @login_required
    @menu_required("production_preplan")
    def orchestrator_ai_advice_list():
        rows = (
            OrchestratorAiAdvice.query.order_by(OrchestratorAiAdvice.id.desc())
            .limit(100)
            .all()
        )
        return jsonify(
            {
                "ok": True,
                "items": [
                    {
                        "id": x.id,
                        "event_id": x.event_id,
                        "advice_type": x.advice_type,
                        "recommended_action": x.recommended_action,
                        "confidence": float(x.confidence) if x.confidence is not None else None,
                        "is_adopted": bool(x.is_adopted),
                        "adopted_by": x.adopted_by,
                        "adopted_at": x.adopted_at.isoformat() if x.adopted_at else None,
                    }
                    for x in rows
                ],
            }
        )

    @bp.route("/orchestrator/ai-advice/metrics", methods=["GET"])
    @login_required
    @menu_required("production_preplan")
    def orchestrator_ai_advice_metrics():
        return jsonify({"ok": True, "data": orchestrator_engine.get_ai_adoption_metrics()})

    @bp.route("/orchestrator/ai-advice/<int:advice_id>/metric", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("orchestrator.metric.write")
    def orchestrator_ai_advice_metric_result(advice_id: int):
        data = request.get_json(silent=True) or {}
        try:
            score = data.get("result_score")
            note = (data.get("metric_note") or "").strip() or None
            row = orchestrator_engine.update_ai_advice_metric_result(
                advice_id=advice_id,
                result_score=Decimal(str(score)) if score is not None else None,
                metric_note=note,
            )
            db.session.commit()
            return jsonify({"ok": True, "metric_id": row.id})
        except Exception as ex:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(ex)}), 400
