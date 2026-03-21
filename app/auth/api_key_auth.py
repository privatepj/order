"""API Key 鉴权：供 OpenClaw / 外部调用专用接口使用，与 Flask-Login 会话隔离。"""
import os
from functools import wraps

from flask import g, request, jsonify


def get_api_key_from_request():
    """从请求头读取 API Key：支持 X-API-Key 或 Authorization: Bearer <key>。"""
    key = request.headers.get("X-API-Key")
    if key:
        return key.strip() or None
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:].strip() or None
    return None


def require_api_key(f):
    """装饰器：校验 API Key，未配置或错误时返回 401/503。"""

    @wraps(f)
    def wrapped(*args, **kwargs):
        g.audit_auth = "api_key"
        configured_key = os.environ.get("OPENCLAW_API_KEY") or os.environ.get("AI_API_KEY")
        if not configured_key:
            return jsonify(ok=False, error="API Key 未配置，该接口不可用。"), 503
        provided = get_api_key_from_request()
        if not provided or provided != configured_key:
            return jsonify(ok=False, error="无效或缺失的 API Key。"), 401
        return f(*args, **kwargs)

    return wrapped
