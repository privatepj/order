from app import db


class CrmOpportunityLine(db.Model):
    __tablename__ = "crm_opportunity_line"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # 逻辑外键：不在库建 FK 约束
    opportunity_id = db.Column(db.Integer, nullable=False)
    customer_product_id = db.Column(db.Integer, nullable=False)

    quantity = db.Column(db.Numeric(26, 8), default=0, nullable=False)
    is_sample = db.Column(db.Boolean, nullable=False, default=False)
    is_spare = db.Column(db.Boolean, nullable=False, default=False)
    remark = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    customer_product = db.relationship(
        "CustomerProduct",
        primaryjoin="foreign(CrmOpportunityLine.customer_product_id) == CustomerProduct.id",
        lazy="joined",
    )

