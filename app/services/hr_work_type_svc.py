from __future__ import annotations

from typing import Iterable, List, Sequence

from app import db
from app.models import (
    HrDepartmentWorkTypeMap,
    HrEmployee,
    HrEmployeeWorkType,
    HrWorkType,
)


def _unique_positive_ints(values: Iterable[int | str | None]) -> List[int]:
    out: List[int] = []
    seen: set[int] = set()
    for raw in values:
        if raw in (None, ""):
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def list_work_types(
    *,
    company_id: int,
    department_id: int | None = None,
    active_only: bool = True,
) -> List[HrWorkType]:
    q = HrWorkType.query.filter_by(company_id=int(company_id))
    if active_only:
        q = q.filter(HrWorkType.is_active.is_(True))
    if department_id:
        mapped_ids = [
            int(row.work_type_id)
            for row in HrDepartmentWorkTypeMap.query.filter_by(
                company_id=int(company_id),
                department_id=int(department_id),
                is_active=True,
            ).all()
            if int(row.work_type_id or 0) > 0
        ]
        if mapped_ids:
            q = q.filter(HrWorkType.id.in_(mapped_ids))
    return q.order_by(HrWorkType.sort_order.asc(), HrWorkType.id.asc()).all()


def allowed_work_type_ids_for_department(*, company_id: int, department_id: int | None) -> List[int]:
    if not department_id:
        return []
    return [
        int(row.work_type_id)
        for row in HrDepartmentWorkTypeMap.query.filter_by(
            company_id=int(company_id),
            department_id=int(department_id),
            is_active=True,
        ).all()
        if int(row.work_type_id or 0) > 0
    ]


def employee_work_type_ids(employee: HrEmployee | None) -> List[int]:
    if not employee:
        return []
    ids = [int(link.work_type_id) for link in (employee.work_type_links or []) if int(link.work_type_id or 0) > 0]
    if int(employee.main_work_type_id or 0) > 0 and int(employee.main_work_type_id) not in ids:
        ids.insert(0, int(employee.main_work_type_id))
    return _unique_positive_ints(ids)


def secondary_work_type_ids(employee: HrEmployee | None) -> List[int]:
    if not employee:
        return []
    main_id = int(employee.main_work_type_id or 0)
    return [wid for wid in employee_work_type_ids(employee) if wid != main_id]


def sync_employee_work_types(
    *,
    employee: HrEmployee,
    main_work_type_id: int | None,
    secondary_work_type_ids: Sequence[int | str | None],
) -> List[int]:
    main_id = int(main_work_type_id or 0) or None
    final_ids = _unique_positive_ints(([main_id] if main_id else []) + list(secondary_work_type_ids))

    existing = {int(link.work_type_id): link for link in (employee.work_type_links or []) if int(link.work_type_id or 0) > 0}

    for work_type_id, link in list(existing.items()):
        if work_type_id not in final_ids:
            db.session.delete(link)

    for work_type_id in final_ids:
        link = existing.get(work_type_id)
        if link is None:
            link = HrEmployeeWorkType(employee_id=int(employee.id), work_type_id=int(work_type_id))
            db.session.add(link)
        link.is_primary = bool(main_id and work_type_id == main_id)

    employee.main_work_type_id = main_id
    return final_ids


def find_work_type_by_name(*, company_id: int, name: str | None) -> HrWorkType | None:
    normalized = (name or "").strip()
    if not normalized:
        return None
    return HrWorkType.query.filter_by(company_id=int(company_id), name=normalized).first()


def ensure_work_type(*, company_id: int, name: str | None) -> HrWorkType | None:
    normalized = (name or "").strip()
    if not normalized:
        return None
    row = find_work_type_by_name(company_id=company_id, name=normalized)
    if row:
        return row
    row = HrWorkType(company_id=int(company_id), name=normalized, is_active=True)
    db.session.add(row)
    db.session.flush()
    return row


def resolve_work_type_id(
    *,
    explicit_work_type_id: int | None = None,
    legacy_department_id: int | None = None,
) -> int:
    return int(explicit_work_type_id or legacy_department_id or 0)


def resolve_work_type_name(row) -> str | None:
    work_type = getattr(row, "work_type", None)
    if work_type and getattr(work_type, "name", None):
        return work_type.name

    main_work_type = getattr(row, "main_work_type", None)
    if main_work_type and getattr(main_work_type, "name", None):
        return main_work_type.name

    department = getattr(row, "department", None)
    if department and getattr(department, "name", None):
        return department.name

    if getattr(row, "primary_work_type_name", None):
        return row.primary_work_type_name

    return None
