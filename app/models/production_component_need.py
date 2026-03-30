from __future__ import annotations

from app import db


class ProductionComponentNeed(db.Model):
    __tablename__ = "production_component_need"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    preplan_id = db.Column(db.Integer, nullable=False)
    work_order_id = db.Column(db.Integer, nullable=False)
    root_preplan_line_id = db.Column(db.Integer)

    bom_header_id = db.Column(db.Integer)
    bom_line_id = db.Column(db.Integer)

    child_kind = db.Column(db.String(16), nullable=False)
    child_material_id = db.Column(db.Integer, nullable=False, default=0)

    required_qty = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    stock_covered_qty = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    shortage_qty = db.Column(db.Numeric(18, 4), nullable=False, default=0)

    coverage_mode = db.Column(db.String(16), nullable=False, default="stock")
    storage_area_hint = db.Column(db.String(32))
    unit = db.Column(db.String(16))
    remark = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    work_order = db.relationship(
        "ProductionWorkOrder",
        back_populates="component_needs",
        primaryjoin="foreign(ProductionComponentNeed.work_order_id) == ProductionWorkOrder.id",
        lazy=True,
    )

    child_material = db.relationship(
        "SemiMaterial",
        primaryjoin="foreign(ProductionComponentNeed.child_material_id) == SemiMaterial.id",
        lazy=True,
        viewonly=True,
    )

