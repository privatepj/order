from flask import g, request
from flask_login import login_required


def register_audit_routes(bp):
    @bp.post("/audit/ui-click")
    @login_required
    def audit_ui_click():
        g.audit_ui_payload = request.get_json(silent=True) or {}
        return "", 204
