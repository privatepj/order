from __future__ import annotations

from app import db


class ProductionPreplanLine(db.Model):
    __tablename__ = "production_preplan_line"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    preplan_id = db.Column(db.Integer, nullable=False)
    line_no = db.Column(db.Integer, nullable=False, default=1)

    source_type = db.Column(db.String(16), nullable=False, default="manual")
    source_order_item_id = db.Column(db.Integer)

    product_id = db.Column(db.Integer, nullable=False, default=0)
    quantity = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    unit = db.Column(db.String(16))
    remark = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    preplan = db.relationship(
        "ProductionPreplan",
        back_populates="lines",
        primaryjoin="foreign(ProductionPreplanLine.preplan_id) == ProductionPreplan.id",
        lazy=True,
    )

    product = db.relationship(
        "Product",
        primaryjoin="foreign(ProductionPreplanLine.product_id) == Product.id",
        lazy=True,
        viewonly=True,
    )

