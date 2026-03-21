from app import db


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        nullable=False,
    )
    event_type = db.Column(db.String(16), nullable=False)
    method = db.Column(db.String(8), nullable=True)
    path = db.Column(db.String(512), nullable=False)
    query_string = db.Column(db.String(2048), nullable=True)
    status_code = db.Column(db.SmallInteger, nullable=True)
    duration_ms = db.Column(db.Integer, nullable=True)
    user_id = db.Column(db.Integer, nullable=True)
    auth_type = db.Column(db.String(16), nullable=False)
    ip = db.Column(db.String(45), nullable=False)
    user_agent = db.Column(db.String(512), nullable=True)
    endpoint = db.Column(db.String(128), nullable=True)
    extra = db.Column(db.JSON, nullable=True)
