from __future__ import annotations

from app import db


class InventoryReservation(db.Model):
    """计划层库存占用：与台账分离，ATP = 台账结存 − 有效预留。"""

    __tablename__ = "inventory_reservation"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.String(16), nullable=False)
    product_id = db.Column(db.Integer, nullable=False, default=0)
    material_id = db.Column(db.Integer, nullable=False, default=0)
    storage_area = db.Column(db.String(32), nullable=False, default="")

    ref_type = db.Column(db.String(16), nullable=False)
    ref_id = db.Column(db.Integer, nullable=False)

    reserved_qty = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    status = db.Column(db.String(16), nullable=False, default="active")

    remark = db.Column(db.String(255))
    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )
