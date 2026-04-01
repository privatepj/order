from __future__ import annotations

from app import db


class ProductionProductRouting(db.Model):
    __tablename__ = "production_product_routing"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.Integer, nullable=False, unique=True, index=True)
    template_id = db.Column(db.Integer, nullable=False, index=True)

    # 是否启用这条产品路由
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # 首版策略：模板继承 + 可选覆写字段
    override_mode = db.Column(db.String(16), nullable=False, default="inherit")

    remark = db.Column(db.String(255))

    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

