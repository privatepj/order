from __future__ import annotations

from app import db


class ProductionMaterialPlanDetail(db.Model):
    __tablename__ = "production_material_plan_detail"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    preplan_id = db.Column(db.Integer, nullable=False, index=True)
    work_order_id = db.Column(db.Integer, nullable=False, index=True)
    operation_id = db.Column(db.Integer)
    component_need_id = db.Column(db.Integer)

    child_kind = db.Column(db.String(16), nullable=False)
    child_material_id = db.Column(db.Integer, nullable=False, default=0)

    required_qty = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    scrap_qty = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    net_required_qty = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    stock_covered_qty = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    shortage_qty = db.Column(db.Numeric(18, 4), nullable=False, default=0)

    unit = db.Column(db.String(16))
    remark = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

