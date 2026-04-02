from __future__ import annotations

from app import db


class SemiMaterial(db.Model):
    """
    半成品/物料主数据。
    说明：本项目不在 DB 层新增外键约束，库存台账通过 category + product_id/material_id 的语义关联（应用层保证）。
    """

    __tablename__ = "semi_material"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    kind = db.Column(db.String(16), nullable=False)  # semi / material
    code = db.Column(db.String(64), nullable=False, unique=True)
    name = db.Column(db.String(128), nullable=False)
    spec = db.Column(db.String(128))
    base_unit = db.Column(db.String(16))
    standard_unit_cost = db.Column(db.Numeric(18, 4), nullable=True)
    remark = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

