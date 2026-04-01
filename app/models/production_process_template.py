from __future__ import annotations

from app import db


class ProductionProcessTemplate(db.Model):
    __tablename__ = "production_process_template"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False)
    version = db.Column(db.String(32), nullable=False, default="v1")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    remark = db.Column(db.String(255))

    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    steps = db.relationship(
        "ProductionProcessTemplateStep",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="ProductionProcessTemplateStep.step_no",
        primaryjoin="ProductionProcessTemplate.id == foreign(ProductionProcessTemplateStep.template_id)",
        lazy="select",
    )

