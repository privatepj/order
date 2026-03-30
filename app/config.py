import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env", encoding="utf-8-sig")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-me"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or "mysql+pymysql://root:@localhost:3306/sydixon_order?charset=utf8mb4"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # 角色代码（与 role 表 code 一致）
    ROLE_ADMIN = "admin"
    ROLE_SALES = "sales"
    ROLE_WAREHOUSE = "warehouse"
    ROLE_FINANCE = "finance"

    # OpenClaw：全局 Key（可选，与细项能力无关）；或用户 API Token（RBAC + openclaw.* 能力）
    OPENCLAW_API_KEY = os.environ.get("OPENCLAW_API_KEY") or os.environ.get("AI_API_KEY")

    # 送货单标记已发时自动出库写入的默认仓储区（必填方可自动出库）
    INVENTORY_DEFAULT_STORAGE_AREA = (
        os.environ.get("INVENTORY_DEFAULT_STORAGE_AREA") or ""
    ).strip()
