from __future__ import annotations

from app import db


class HrDepartmentCapabilityMap(db.Model):
    """工序/路由上的部门 id 与能力表用工位 id 的映射（无 DB 外键）。"""

    __tablename__ = "hr_department_capability_map"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    process_hr_department_id = db.Column(db.Integer, nullable=False, index=True)
    capability_hr_department_id = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    remark = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
