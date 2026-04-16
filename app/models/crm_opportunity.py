from app import db


class CrmOpportunity(db.Model):
    __tablename__ = "crm_opportunity"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    opp_code = db.Column(db.String(64), nullable=False, unique=True)

    # 逻辑外键：不在库建 FK 约束
    lead_id = db.Column(db.Integer, nullable=True)
    customer_id = db.Column(db.Integer, nullable=False)

    stage = db.Column(db.String(32), nullable=False, default="draft")
    expected_amount = db.Column(db.Numeric(26, 8))
    currency = db.Column(db.String(16))
    expected_close_date = db.Column(db.Date)

    salesperson = db.Column(db.String(64), default="GaoMeiHua", nullable=False)
    customer_order_no = db.Column(db.String(64))
    order_date = db.Column(db.Date)
    required_date = db.Column(db.Date)
    payment_type = db.Column(db.String(16), default="monthly", nullable=False)

    remark = db.Column(db.String(255))
    tags = db.Column(db.String(255))

    # 逻辑外键：成交后生成的 SalesOrder.id（不建 FK 约束）
    won_order_id = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    lines = db.relationship(
        "CrmOpportunityLine",
        primaryjoin="CrmOpportunity.id == foreign(CrmOpportunityLine.opportunity_id)",
        backref="opportunity",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="CrmOpportunityLine.id",
    )

    customer = db.relationship(
        "Customer",
        primaryjoin="foreign(CrmOpportunity.customer_id) == Customer.id",
        lazy="joined",
    )

    won_order = db.relationship(
        "SalesOrder",
        primaryjoin="foreign(CrmOpportunity.won_order_id) == SalesOrder.id",
        lazy="joined",
    )

