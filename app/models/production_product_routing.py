from __future__ import annotations

from app import db


class ProductionProductRouting(db.Model):
    __tablename__ = "production_product_routing"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    target_kind = db.Column(db.String(16), nullable=False, default="finished", index=True)
    target_id = db.Column(db.Integer, nullable=False, default=0, index=True)
    product_id = db.Column(db.Integer, nullable=False, default=0, index=True)
    template_id = db.Column(db.Integer, nullable=False, index=True)

    # 是否启用这条产品路由
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # 首版策略：模板继承 + 可选覆写字段
    override_mode = db.Column(db.String(16), nullable=False, default="inherit")

    remark = db.Column(db.String(255))

    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    @property
    def effective_target_kind(self) -> str:
        kind = (self.target_kind or "").strip()
        if kind:
            return kind
        return "finished"

    @property
    def effective_target_id(self) -> int:
        if int(self.target_id or 0) > 0:
            return int(self.target_id)
        # 兼容历史数据：target_id 为空时回退 product_id
        return int(self.product_id or 0)

