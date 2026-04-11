from __future__ import annotations

from app import db


class BomHeader(db.Model):
    """BOM 主表：父项 + 版本 + 是否生效。

    说明：
    - 不在 DB 层创建外键约束；ORM 关系通过 primaryjoin + foreign() 标注“逻辑外键”侧列。
    - parent_kind/parent_product_id/parent_material_id 的语义由应用层保证。
    """

    __tablename__ = "bom_header"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    parent_kind = db.Column(db.String(16), nullable=False)  # finished / semi / material
    parent_product_id = db.Column(db.Integer, nullable=False, default=0)
    parent_material_id = db.Column(db.Integer, nullable=False, default=0)

    version_no = db.Column(db.Integer, nullable=False, default=1)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    remark = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    lines = db.relationship(
        "BomLine",
        back_populates="header",
        cascade="all, delete-orphan",
        primaryjoin="BomHeader.id == foreign(BomLine.bom_header_id)",
    )

    parent_product = db.relationship(
        "Product",
        primaryjoin="foreign(BomHeader.parent_product_id) == Product.id",
        lazy=True,
    )
    parent_material = db.relationship(
        "SemiMaterial",
        primaryjoin="foreign(BomHeader.parent_material_id) == SemiMaterial.id",
        lazy=True,
    )


class BomLine(db.Model):
    """BOM 明细：子项用量。

    说明：当前范围将子项限定为半成品/物料（SemiMaterial），多层展开由递归逻辑在服务层完成。
    """

    __tablename__ = "bom_line"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    bom_header_id = db.Column(db.Integer, nullable=False)

    line_no = db.Column(db.Integer, nullable=False)
    child_kind = db.Column(db.String(16), nullable=False)  # semi / material
    child_material_id = db.Column(db.Integer, nullable=False, default=0)

    quantity = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    unit = db.Column(db.String(16))
    remark = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    header = db.relationship(
        "BomHeader",
        back_populates="lines",
        primaryjoin="foreign(BomLine.bom_header_id) == BomHeader.id",
    )

    child_material = db.relationship(
        "SemiMaterial",
        primaryjoin="foreign(BomLine.child_material_id) == SemiMaterial.id",
        lazy=True,
    )

