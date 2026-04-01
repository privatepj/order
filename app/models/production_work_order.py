from __future__ import annotations

from app import db


class ProductionWorkOrder(db.Model):
    __tablename__ = "production_work_order"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    preplan_id = db.Column(db.Integer, nullable=False)
    root_preplan_line_id = db.Column(db.Integer)

    parent_kind = db.Column(db.String(16), nullable=False)
    parent_product_id = db.Column(db.Integer, nullable=False, default=0)
    parent_material_id = db.Column(db.Integer, nullable=False, default=0)

    plan_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="planned")

    demand_qty = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    stock_covered_qty = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    to_produce_qty = db.Column(db.Numeric(18, 4), nullable=False, default=0)

    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    remark = db.Column(db.String(255))

    component_needs = db.relationship(
        "ProductionComponentNeed",
        back_populates="work_order",
        cascade="all, delete-orphan",
        order_by="ProductionComponentNeed.id",
        primaryjoin="ProductionWorkOrder.id == foreign(ProductionComponentNeed.work_order_id)",
        lazy="select",
    )

    operations = db.relationship(
        "ProductionWorkOrderOperation",
        back_populates="work_order",
        cascade="all, delete-orphan",
        order_by="ProductionWorkOrderOperation.step_no",
        primaryjoin="ProductionWorkOrder.id == foreign(ProductionWorkOrderOperation.work_order_id)",
        lazy="select",
    )

    parent_product = db.relationship(
        "Product",
        primaryjoin="foreign(ProductionWorkOrder.parent_product_id) == Product.id",
        lazy=True,
        viewonly=True,
    )

    parent_material = db.relationship(
        "SemiMaterial",
        primaryjoin="foreign(ProductionWorkOrder.parent_material_id) == SemiMaterial.id",
        lazy=True,
        viewonly=True,
    )

