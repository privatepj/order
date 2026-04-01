from __future__ import annotations

from app import db


class ProductionProductRoutingStep(db.Model):
    __tablename__ = "production_product_routing_step"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    routing_id = db.Column(db.Integer, nullable=False, index=True)

    # 覆写匹配模板 step_no（模板 step 的 step_no 不应在启用模板后随意变更）
    template_step_no = db.Column(db.Integer, nullable=False)

    # 覆写资源维度：允许不填写，表示继承模板步骤的资源维度与工时口径
    resource_kind_override = db.Column(db.String(16))
    machine_type_id_override = db.Column(db.Integer, nullable=False, default=0)
    hr_department_id_override = db.Column(db.Integer, nullable=False, default=0)

    setup_minutes_override = db.Column(db.Numeric(12, 2))
    run_minutes_per_unit_override = db.Column(db.Numeric(12, 4))

    step_name_override = db.Column(db.String(128))

    remark = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

