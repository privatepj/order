"""OpenClaw 鉴权：环境变量全局 Key（兼容旧版）或用户 API Token + RBAC 能力码。"""
import hashlib
import os
import threading
import time
from collections import deque
from functools import wraps

from flask import g, jsonify, request

from app import db
from app.auth.api_key_auth import get_api_key_from_request
from app.auth.capabilities import user_can_cap
from app.models import User, UserApiToken

_openclaw_rate_lock = threading.Lock()
_openclaw_rate_buckets: dict[str, deque] = {}


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.strip().encode("utf-8")).hexdigest()


def _openclaw_rate_limit_ok() -> bool:
    try:
        limit = int((os.environ.get("OPENCLAW_RATE_LIMIT_PER_MINUTE") or "120").strip())
    except ValueError:
        limit = 120
    if limit <= 0:
        return True
    ip = (request.remote_addr or "").strip() or "unknown"
    now = time.time()
    with _openclaw_rate_lock:
        dq = _openclaw_rate_buckets.setdefault(ip, deque())
        while dq and dq[0] < now - 60.0:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
    return True


def require_openclaw(*cap_keys: str):
    """
    校验凭据：优先匹配 OPENCLAW_API_KEY（不设能力限制）；
    否则按 UserApiToken 解析用户，并要求具备 cap_keys 中任一能力（OR）。
    """
    if not cap_keys:
        raise ValueError("require_openclaw 至少需要一个能力键")

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not _openclaw_rate_limit_ok():
                return jsonify(ok=False, error="请求过于频繁，请稍后再试。"), 429

            provided = get_api_key_from_request()
            if not provided:
                return jsonify(ok=False, error="无效或缺失的凭据。"), 401

            global_key = (os.environ.get("OPENCLAW_API_KEY") or os.environ.get("AI_API_KEY") or "").strip()
            if global_key and provided == global_key:
                g.audit_auth = "api_key"
                g.openclaw_user = None
                g.openclaw_api_token_id = None
                return f(*args, **kwargs)

            th = _hash_token(provided)
            row = UserApiToken.query.filter_by(token_hash=th).first()
            if not row or not row.is_valid_now():
                return jsonify(ok=False, error="无效或缺失的凭据。"), 401

            user = db.session.get(User, row.user_id)
            if not user or not user.is_active:
                return jsonify(ok=False, error="用户已停用。"), 403
            if getattr(user, "role_code", None) == "pending":
                return jsonify(ok=False, error="用户尚未分配角色。"), 403

            g.audit_auth = "api_token"
            g.openclaw_user = user
            g.openclaw_api_token_id = row.id

            if not any(user_can_cap(user, k) for k in cap_keys):
                return jsonify(ok=False, error="没有权限调用此接口。"), 403

            return f(*args, **kwargs)

        return wrapped

    return decorator
