from __future__ import annotations

from app import db


class ProductionWorkOrderOperationPlan(db.Model):
    __tablename__ = "production_work_order_operation_plan"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    preplan_id = db.Column(db.Integer, nullable=False, index=True)
    work_order_id = db.Column(db.Integer, nullable=False, index=True)
    operation_id = db.Column(db.Integer, nullable=False, unique=True)

    process_node_id = db.Column(db.Integer)

    plan_date = db.Column(db.Date, nullable=False)

    es = db.Column(db.DateTime)
    ef = db.Column(db.DateTime)
    ls = db.Column(db.DateTime)
    lf = db.Column(db.DateTime)

    is_critical = db.Column(db.Boolean, nullable=False, default=False)

    resource_kind = db.Column(db.String(16))
    machine_type_id = db.Column(db.Integer, nullable=False, default=0)
    hr_department_id = db.Column(db.Integer, nullable=False, default=0)

    planned_minutes = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    remark = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

