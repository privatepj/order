from __future__ import annotations

from app import db


class ProductionWorkOrderOperation(db.Model):
    __tablename__ = "production_work_order_operation"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    preplan_id = db.Column(db.Integer, nullable=False, index=True)
    work_order_id = db.Column(db.Integer, nullable=False, index=True)

    # 来源：模板 step_no（快照固化）
    step_no = db.Column(db.Integer, nullable=False)
    step_code = db.Column(db.String(64))
    step_name = db.Column(db.String(128), nullable=False)

    resource_kind = db.Column(db.String(16))
    machine_type_id = db.Column(db.Integer, nullable=False, default=0)
    hr_department_id = db.Column(db.Integer, nullable=False, default=0)

    plan_qty = db.Column(db.Numeric(18, 4), nullable=False, default=0)

    setup_minutes = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    run_minutes_per_unit = db.Column(db.Numeric(12, 4), nullable=False, default=0)

    estimated_setup_minutes = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    estimated_run_minutes = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    estimated_total_minutes = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    budget_machine_id = db.Column(db.Integer, nullable=False, default=0)
    budget_operator_employee_id = db.Column(db.Integer, nullable=False, default=0)

    remark = db.Column(db.String(255))

    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    work_order = db.relationship(
        "ProductionWorkOrder",
        back_populates="operations",
        primaryjoin="foreign(ProductionWorkOrderOperation.work_order_id) == ProductionWorkOrder.id",
        lazy=True,
        viewonly=True,
    )

