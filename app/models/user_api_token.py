from datetime import datetime

from app import db


class UserApiToken(db.Model):
    """OpenClaw / 外部 API 用户令牌：仅存哈希，明文仅在创建时展示一次。"""

    __tablename__ = "user_api_token"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    label = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)

    def is_valid_now(self) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at <= datetime.utcnow():
            return False
        return True
