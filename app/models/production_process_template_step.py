from __future__ import annotations

from app import db


class ProductionProcessTemplateStep(db.Model):
    __tablename__ = "production_process_template_step"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    template_id = db.Column(db.Integer, nullable=False, index=True)

    step_no = db.Column(db.Integer, nullable=False, default=1)
    step_code = db.Column(db.String(64))
    step_name = db.Column(db.String(128), nullable=False)

    # 资源维度：machine_type 或 hr_department（应用层保证互斥与合法值）
    resource_kind = db.Column(db.String(16), nullable=False, default="machine_type")
    machine_type_id = db.Column(db.Integer, nullable=False, default=0)
    hr_department_id = db.Column(db.Integer, nullable=False, default=0)
    hr_work_type_id = db.Column(db.Integer, nullable=False, default=0)

    # 工时口径（单位：分钟）
    setup_minutes = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    run_minutes_per_unit = db.Column(db.Numeric(26, 8), nullable=False, default=0)

    remark = db.Column(db.String(255))

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    template = db.relationship(
        "ProductionProcessTemplate",
        back_populates="steps",
        primaryjoin="foreign(ProductionProcessTemplateStep.template_id) == ProductionProcessTemplate.id",
        lazy=True,
        viewonly=True,
    )

    @property
    def effective_work_type_id(self) -> int:
        return int(self.hr_work_type_id or self.hr_department_id or 0)

