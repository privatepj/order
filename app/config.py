import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-me"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or "mysql+pymysql://root:@localhost:3306/sydixon_order"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # 角色代码（与 role 表 code 一致）
    ROLE_ADMIN = "admin"
    ROLE_SALES = "sales"
    ROLE_WAREHOUSE = "warehouse"
    ROLE_FINANCE = "finance"

    # OpenClaw / AI 专用 API 鉴权（可选；不配置则 /api/openclaw 返回 503）
    OPENCLAW_API_KEY = os.environ.get("OPENCLAW_API_KEY") or os.environ.get("AI_API_KEY")

    # 送货单标记已发时自动出库写入的默认仓储区（必填方可自动出库）
    INVENTORY_DEFAULT_STORAGE_AREA = (
        os.environ.get("INVENTORY_DEFAULT_STORAGE_AREA") or ""
    ).strip()
