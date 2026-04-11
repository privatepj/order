"""期初结存与进出明细（台账）；product_id/material_id 用 0 表示未使用，便于 MySQL 唯一约束。"""

from __future__ import annotations

from app import db


class InventoryMovementBatch(db.Model):
    """手工/Excel/送货出库等一次提交对应的批次头。"""

    __tablename__ = "inventory_movement_batch"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.String(16), nullable=False)
    biz_date = db.Column(db.Date, nullable=False)
    direction = db.Column(db.String(8), nullable=False)
    source = db.Column(db.String(16), nullable=False)
    line_count = db.Column(db.Integer, nullable=False, default=0)
    original_filename = db.Column(db.String(255))
    source_delivery_id = db.Column(db.Integer)
    remark = db.Column(db.String(255))
    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    movements = db.relationship(
        "InventoryMovement",
        back_populates="batch",
        primaryjoin="InventoryMovementBatch.id == foreign(InventoryMovement.movement_batch_id)",
    )
    delivery = db.relationship(
        "Delivery",
        primaryjoin="foreign(InventoryMovementBatch.source_delivery_id) == Delivery.id",
        lazy=True,
        viewonly=True,
    )


class InventoryOpeningBalance(db.Model):
    __tablename__ = "inventory_opening_balance"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.String(16), nullable=False)
    product_id = db.Column(db.Integer, nullable=False, default=0)
    material_id = db.Column(db.Integer, nullable=False, default=0)
    storage_area = db.Column(db.String(32), nullable=False, default="")
    opening_qty = db.Column(db.Numeric(26, 8), nullable=False, default=0)
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

    material = db.relationship(
        "SemiMaterial",
        primaryjoin="foreign(InventoryOpeningBalance.material_id) == SemiMaterial.id",
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
    quantity = db.Column(db.Numeric(26, 8), nullable=False)
    unit = db.Column(db.String(16))
    biz_date = db.Column(db.Date, nullable=False)
    source_type = db.Column(db.String(16), nullable=False, default="manual")
    source_delivery_id = db.Column(db.Integer)
    source_delivery_item_id = db.Column(db.Integer)
    source_purchase_order_id = db.Column(db.Integer)
    source_purchase_receipt_id = db.Column(db.Integer)
    remark = db.Column(db.String(255))
    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    movement_batch_id = db.Column(db.Integer)

    batch = db.relationship(
        "InventoryMovementBatch",
        back_populates="movements",
        primaryjoin="foreign(InventoryMovement.movement_batch_id) == InventoryMovementBatch.id",
    )

    product = db.relationship(
        "Product",
        primaryjoin="foreign(InventoryMovement.product_id) == Product.id",
        lazy=True,
    )

    material = db.relationship(
        "SemiMaterial",
        primaryjoin="foreign(InventoryMovement.material_id) == SemiMaterial.id",
        lazy=True,
    )
    purchase_order = db.relationship(
        "PurchaseOrder",
        primaryjoin="foreign(InventoryMovement.source_purchase_order_id) == PurchaseOrder.id",
        lazy=True,
        viewonly=True,
    )
    purchase_receipt = db.relationship(
        "PurchaseReceipt",
        primaryjoin="foreign(InventoryMovement.source_purchase_receipt_id) == PurchaseReceipt.id",
        lazy=True,
        viewonly=True,
    )
