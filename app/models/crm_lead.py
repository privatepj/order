from app import db


class CrmLead(db.Model):
    __tablename__ = "crm_lead"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    lead_code = db.Column(db.String(64), nullable=False, unique=True)

    # 逻辑外键：不在库建 FK 约束
    customer_id = db.Column(db.Integer, nullable=True)

    # 线索快照字段（允许 lead 尚未转为既有 customer）
    customer_name = db.Column(db.String(128), nullable=False)
    contact = db.Column(db.String(64))
    phone = db.Column(db.String(32))

    source = db.Column(db.String(64), default="manual", nullable=False)
    status = db.Column(db.String(32), nullable=False, default="new")
    tags = db.Column(db.String(255))
    remark = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    opportunities = db.relationship(
        "CrmOpportunity",
        primaryjoin="CrmLead.id == foreign(CrmOpportunity.lead_id)",
        backref="lead",
        lazy="dynamic",
    )

