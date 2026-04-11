from __future__ import annotations

from app import db


class ProductionScheduleCommitRow(db.Model):
    """预计划「确认计划」写回机台/人员排班后的撤销元数据（重新测算前清理）。"""

    __tablename__ = "production_schedule_commit_row"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    preplan_id = db.Column(db.Integer, nullable=False, index=True)
    operation_id = db.Column(db.Integer, nullable=False, unique=True, index=True)

    machine_dispatch_log_id = db.Column(db.Integer, nullable=False, default=0)
    dispatch_booking_id = db.Column(db.Integer, nullable=False, default=0)
    restore_parent_booking_id = db.Column(db.Integer, nullable=False, default=0)
    restore_parent_end_at = db.Column(db.DateTime)
    delete_middle_booking_id = db.Column(db.Integer, nullable=False, default=0)
    delete_tail_booking_id = db.Column(db.Integer, nullable=False, default=0)
    employee_booking_id = db.Column(db.Integer, nullable=False, default=0)
    emp_restore_parent_booking_id = db.Column(db.Integer, nullable=False, default=0)
    emp_restore_parent_end_at = db.Column(db.DateTime)
    emp_delete_middle_booking_id = db.Column(db.Integer, nullable=False, default=0)
    emp_delete_tail_booking_id = db.Column(db.Integer, nullable=False, default=0)
    emp_booking_mode = db.Column(db.String(16), nullable=False, default="split")

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
