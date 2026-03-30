from __future__ import annotations

from app import db


class ProductionPreplan(db.Model):
    __tablename__ = "production_preplan"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    source_type = db.Column(db.String(16), nullable=False, default="manual")
    plan_date = db.Column(db.Date, nullable=False)
    customer_id = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(16), nullable=False, default="draft")
    remark = db.Column(db.String(255))

    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    lines = db.relationship(
        "ProductionPreplanLine",
        back_populates="preplan",
        cascade="all, delete-orphan",
        order_by="ProductionPreplanLine.line_no",
        primaryjoin="ProductionPreplan.id == foreign(ProductionPreplanLine.preplan_id)",
        lazy="select",
    )

