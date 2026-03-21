"""OpenClaw / AI 专用 API：对话式订单与送货单，API Key 鉴权。"""
from flask import Blueprint

bp = Blueprint("openclaw", __name__, url_prefix="/api/openclaw")

from app.openclaw import routes  # noqa: E402, F401
