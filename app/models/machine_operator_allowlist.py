from __future__ import annotations

from app import db


class MachineOperatorAllowlist(db.Model):
    """机台可操作员工白名单（无 DB 外键约束）。"""

    __tablename__ = "machine_operator_allowlist"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    machine_id = db.Column(db.Integer, nullable=False, index=True)
    employee_id = db.Column(db.Integer, nullable=False, index=True)
    capability_hr_department_id = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    remark = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    machine = db.relationship(
        "Machine",
        primaryjoin="foreign(MachineOperatorAllowlist.machine_id) == Machine.id",
        lazy=True,
    )
    employee = db.relationship(
        "HrEmployee",
        primaryjoin="foreign(MachineOperatorAllowlist.employee_id) == HrEmployee.id",
        lazy=True,
    )
