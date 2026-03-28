"""期初结存与进出明细（台账）；product_id/material_id 用 0 表示未使用，便于 MySQL 唯一约束。"""

from __future__ import annotations

from app import db


class InventoryOpeningBalance(db.Model):
    __tablename__ = "inventory_opening_balance"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.String(16), nullable=False)
    product_id = db.Column(db.Integer, nullable=False, default=0)
    material_id = db.Column(db.Integer, nullable=False, default=0)
    storage_area = db.Column(db.String(32), nullable=False, default="")
    opening_qty = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    unit = db.Column(db.String(16))
    remark = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    product = db.relationship(
        "Product",
        primaryjoin="foreign(InventoryOpeningBalance.product_id) == Product.id",
        lazy=True,
    )


class InventoryMovement(db.Model):
    __tablename__ = "inventory_movement"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.String(16), nullable=False)
    direction = db.Column(db.String(8), nullable=False)
    product_id = db.Column(db.Integer, nullable=False, default=0)
    material_id = db.Column(db.Integer, nullable=False, default=0)
    storage_area = db.Column(db.String(32), nullable=False, default="")
    quantity = db.Column(db.Numeric(18, 4), nullable=False)
    unit = db.Column(db.String(16))
    biz_date = db.Column(db.Date, nullable=False)
    source_type = db.Column(db.String(16), nullable=False, default="manual")
    source_delivery_id = db.Column(db.Integer)
    source_delivery_item_id = db.Column(db.Integer)
    remark = db.Column(db.String(255))
    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    product = db.relationship(
        "Product",
        primaryjoin="foreign(InventoryMovement.product_id) == Product.id",
        lazy=True,
    )
