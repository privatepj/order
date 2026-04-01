from __future__ import annotations

from app import db


class ProductionCostPlanDetail(db.Model):
    __tablename__ = "production_cost_plan_detail"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    preplan_id = db.Column(db.Integer, nullable=False, index=True)
    work_order_id = db.Column(db.Integer, nullable=False, index=True)
    operation_id = db.Column(db.Integer)

    cost_category = db.Column(db.String(16), nullable=False)
    amount = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    currency = db.Column(db.String(8), nullable=False, default="CNY")

    unit_cost = db.Column(db.Numeric(18, 6))
    qty_basis = db.Column(db.Numeric(18, 4))

    remark = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

