from __future__ import annotations

from app import db


class ProductionProcessNode(db.Model):
    __tablename__ = "production_process_node"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    template_id = db.Column(db.Integer, nullable=False, index=True)
    parent_node_id = db.Column(db.Integer, index=True)

    step_no = db.Column(db.Integer)
    node_type = db.Column(db.String(16), nullable=False, default="operation")
    code = db.Column(db.String(64))
    name = db.Column(db.String(128), nullable=False)

    resource_kind = db.Column(db.String(16))
    machine_type_id = db.Column(db.Integer, nullable=False, default=0)
    hr_department_id = db.Column(db.Integer, nullable=False, default=0)

    setup_minutes = db.Column(db.Numeric(12, 2))
    run_minutes_per_unit = db.Column(db.Numeric(12, 4))
    scrap_rate = db.Column(db.Numeric(8, 4))

    remark = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())


