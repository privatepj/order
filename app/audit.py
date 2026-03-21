import time

from flask import current_app, g, has_request_context, request
from flask_login import current_user

from app import db
from app.models import AuditLog

AUDIT_UI_CLICK_ENDPOINT = "main.audit_ui_click"


def _trunc(s, n):
    if s is None:
        return None
    s = str(s)
    if len(s) <= n:
        return s
    return s[: n - 3] + "..."


def _client_ip():
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        first = xff.split(",")[0].strip()
        return _trunc(first, 45) or "-"
    return _trunc(request.remote_addr or "", 45) or "-"


def _auth_type():
    if getattr(g, "audit_auth", None) == "api_key":
        return "api_key"
    if current_user.is_authenticated:
        return "session"
    return "anonymous"


def persist_audit(response):
    if not has_request_context():
        return response
    if request.path.startswith("/static/"):
        return response

    t0 = getattr(g, "_audit_t0", None)
    duration_ms = None
    if t0 is not None:
        duration_ms = int((time.perf_counter() - t0) * 1000)

    qs = request.query_string
    if qs:
        try:
            qs = qs.decode("utf-8", errors="replace")
        except Exception:
            qs = str(qs)
    else:
        qs = None

    is_ui_route = request.endpoint == AUDIT_UI_CLICK_ENDPOINT
    if is_ui_route and hasattr(g, "audit_ui_payload"):
        event_type = "ui_click"
        ui_payload = g.audit_ui_payload
        extra = ui_payload if isinstance(ui_payload, dict) else {}
    else:
        event_type = "http"
        extra = None

    row = AuditLog(
        event_type=event_type,
        method=_trunc(request.method, 8),
        path=_trunc(request.path, 512),
        query_string=_trunc(qs, 2048) if qs else None,
        status_code=response.status_code,
        duration_ms=duration_ms,
        user_id=int(current_user.get_id()) if current_user.is_authenticated else None,
        auth_type=_auth_type(),
        ip=_client_ip(),
        user_agent=_trunc(request.headers.get("User-Agent"), 512),
        endpoint=_trunc(request.endpoint or "", 128) if request.endpoint else None,
        extra=extra,
    )

    try:
        db.session.add(row)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("audit_log persist failed")

    return response


def register_audit_hooks(app):
    @app.before_request
    def _audit_timer():
        g._audit_t0 = time.perf_counter()

    @app.after_request
    def _audit_after(response):
        return persist_audit(response)
