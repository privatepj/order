"""HR 与用户账号的关联辅助（无 DB 外键，仅查询）。"""

from __future__ import annotations

from typing import Optional


def resolve_user_hr_department_id(user_id: int) -> Optional[int]:
    """当前登录用户若绑定在职员工档案，返回其行政部门 hr_department.id，否则 None。"""
    if not user_id:
        return None
    from app.models import HrEmployee

    emp = (
        HrEmployee.query.filter_by(user_id=int(user_id), status="active")
        .order_by(HrEmployee.id.asc())
        .first()
    )
    if not emp or not emp.department_id:
        return None
    return int(emp.department_id)
