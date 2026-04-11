"""预计划人工排程校验与确认（SQLite 内存库）。"""
from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

import pytest

from app import create_app, db
from app.config import Config
from app.models import (
    Company,
    HrEmployee,
    HrEmployeeScheduleBooking,
    HrEmployeeScheduleTemplate,
    Machine,
    MachineOperatorAllowlist,
    MachineScheduleBooking,
    MachineScheduleTemplate,
    MachineType,
    ProductionPreplan,
    ProductionWorkOrder,
    ProductionWorkOrderOperation,
    ProductionWorkOrderOperationPlan,
    Role,
    User,
)
from app.services import production_preplan_schedule_manual_svc as sched_manual


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _seed_machine_calendar(*, machine_id: int, user_id: int, d: date) -> None:
    tpl = MachineScheduleTemplate(
        machine_id=machine_id,
        name="日班",
        repeat_kind="weekly",
        days_of_week="0,1,2,3,4,5,6",
        valid_from=d,
        valid_to=None,
        start_time=time(8, 0),
        end_time=time(18, 0),
        state="available",
        created_by=user_id,
    )
    db.session.add(tpl)
    db.session.flush()
    start_at = datetime.combine(d, time(8, 0))
    end_at = datetime.combine(d, time(18, 0))
    bk = MachineScheduleBooking(
        machine_id=machine_id,
        template_id=tpl.id,
        state="available",
        start_at=start_at,
        end_at=end_at,
        created_by=user_id,
    )
    db.session.add(bk)
    db.session.flush()


def _seed_employee_calendar(*, employee_id: int, user_id: int, d: date) -> None:
    tpl = HrEmployeeScheduleTemplate(
        employee_id=employee_id,
        name="白班",
        repeat_kind="weekly",
        days_of_week="0,1,2,3,4,5,6",
        valid_from=d,
        valid_to=None,
        start_time=time(8, 0),
        end_time=time(18, 0),
        state="available",
        created_by=user_id,
    )
    db.session.add(tpl)
    db.session.flush()
    start_at = datetime.combine(d, time(8, 0))
    end_at = datetime.combine(d, time(18, 0))
    db.session.add(
        HrEmployeeScheduleBooking(
            employee_id=employee_id,
            template_id=tpl.id,
            state="available",
            start_at=start_at,
            end_at=end_at,
            created_by=user_id,
        )
    )


def test_same_preplan_machine_overlap_fails(app):
    d = date(2026, 4, 11)
    with app.app_context():
        db.session.add(Role(id=1, name="管理员", code="admin", description=""))
        db.session.add(Company(id=1, name="C1", code="c1"))
        db.session.add(User(id=1, username="u1", password_hash="x", role_id=1, is_active=True))
        db.session.flush()
        db.session.add(MachineType(id=1, code="T1", name="MT"))
        db.session.add(Machine(id=1, machine_type_id=1, machine_no="M1", name="机1", status="enabled"))
        db.session.add(HrEmployee(id=1, company_id=1, employee_no="E1", name="张三", status="active"))
        db.session.flush()
        _seed_machine_calendar(machine_id=1, user_id=1, d=d)
        _seed_employee_calendar(employee_id=1, user_id=1, d=d)
        db.session.add(MachineOperatorAllowlist(machine_id=1, employee_id=1, is_active=True))
        db.session.add(ProductionPreplan(id=1, plan_date=d, status="planned", created_by=1))
        db.session.flush()
        db.session.add(
            ProductionWorkOrder(
                id=1,
                preplan_id=1,
                parent_kind="finished",
                parent_product_id=1,
                plan_date=d,
                status="planned",
                created_by=1,
            )
        )
        db.session.flush()
        db.session.add_all(
            [
                ProductionWorkOrderOperation(
                    id=1,
                    preplan_id=1,
                    work_order_id=1,
                    step_no=1,
                    step_code="S1",
                    step_name="工序1",
                    resource_kind="machine_type",
                    machine_type_id=1,
                    budget_machine_id=1,
                    budget_operator_employee_id=1,
                    plan_qty=Decimal(1),
                    estimated_total_minutes=Decimal(60),
                    created_by=1,
                ),
                ProductionWorkOrderOperation(
                    id=2,
                    preplan_id=1,
                    work_order_id=1,
                    step_no=2,
                    step_code="S2",
                    step_name="工序2",
                    resource_kind="machine_type",
                    machine_type_id=1,
                    budget_machine_id=1,
                    budget_operator_employee_id=1,
                    plan_qty=Decimal(1),
                    estimated_total_minutes=Decimal(60),
                    created_by=1,
                ),
            ]
        )
        db.session.flush()
        es1 = datetime.combine(d, time(9, 0))
        ef1 = datetime.combine(d, time(10, 0))
        es2 = datetime.combine(d, time(9, 30))
        ef2 = datetime.combine(d, time(10, 30))
        db.session.add_all(
            [
                ProductionWorkOrderOperationPlan(
                    preplan_id=1,
                    work_order_id=1,
                    operation_id=1,
                    plan_date=d,
                    es=es1,
                    ef=ef1,
                    is_critical=False,
                    resource_kind="machine_type",
                    machine_type_id=1,
                    planned_minutes=Decimal(60),
                ),
                ProductionWorkOrderOperationPlan(
                    preplan_id=1,
                    work_order_id=1,
                    operation_id=2,
                    plan_date=d,
                    es=es2,
                    ef=ef2,
                    is_critical=False,
                    resource_kind="machine_type",
                    machine_type_id=1,
                    planned_minutes=Decimal(60),
                ),
            ]
        )
        db.session.commit()

        errs = sched_manual.validate_preplan_schedule(1)
        assert any("本预计划内时段重叠" in e for e in errs)


def test_non_overlap_passes_validate(app):
    d = date(2026, 4, 11)
    with app.app_context():
        db.session.add(Role(id=1, name="管理员", code="admin", description=""))
        db.session.add(Company(id=1, name="C1", code="c1"))
        db.session.add(User(id=1, username="u1", password_hash="x", role_id=1, is_active=True))
        db.session.flush()
        db.session.add(MachineType(id=1, code="T1", name="MT"))
        db.session.add(Machine(id=1, machine_type_id=1, machine_no="M1", name="机1", status="enabled"))
        db.session.add(HrEmployee(id=1, company_id=1, employee_no="E1", name="张三", status="active"))
        db.session.flush()
        _seed_machine_calendar(machine_id=1, user_id=1, d=d)
        _seed_employee_calendar(employee_id=1, user_id=1, d=d)
        db.session.add(MachineOperatorAllowlist(machine_id=1, employee_id=1, is_active=True))
        db.session.add(ProductionPreplan(id=1, plan_date=d, status="planned", created_by=1))
        db.session.flush()
        db.session.add(
            ProductionWorkOrder(
                id=1,
                preplan_id=1,
                parent_kind="finished",
                parent_product_id=1,
                plan_date=d,
                status="planned",
                created_by=1,
            )
        )
        db.session.flush()
        db.session.add_all(
            [
                ProductionWorkOrderOperation(
                    id=1,
                    preplan_id=1,
                    work_order_id=1,
                    step_no=1,
                    step_code="S1",
                    step_name="工序1",
                    resource_kind="machine_type",
                    machine_type_id=1,
                    budget_machine_id=1,
                    budget_operator_employee_id=1,
                    plan_qty=Decimal(1),
                    estimated_total_minutes=Decimal(60),
                    created_by=1,
                ),
                ProductionWorkOrderOperation(
                    id=2,
                    preplan_id=1,
                    work_order_id=1,
                    step_no=2,
                    step_code="S2",
                    step_name="工序2",
                    resource_kind="machine_type",
                    machine_type_id=1,
                    budget_machine_id=1,
                    budget_operator_employee_id=1,
                    plan_qty=Decimal(1),
                    estimated_total_minutes=Decimal(60),
                    created_by=1,
                ),
            ]
        )
        db.session.flush()
        es1 = datetime.combine(d, time(9, 0))
        ef1 = datetime.combine(d, time(10, 0))
        es2 = datetime.combine(d, time(10, 0))
        ef2 = datetime.combine(d, time(11, 0))
        db.session.add_all(
            [
                ProductionWorkOrderOperationPlan(
                    preplan_id=1,
                    work_order_id=1,
                    operation_id=1,
                    plan_date=d,
                    es=es1,
                    ef=ef1,
                    is_critical=False,
                    resource_kind="machine_type",
                    machine_type_id=1,
                    planned_minutes=Decimal(60),
                ),
                ProductionWorkOrderOperationPlan(
                    preplan_id=1,
                    work_order_id=1,
                    operation_id=2,
                    plan_date=d,
                    es=es2,
                    ef=ef2,
                    is_critical=False,
                    resource_kind="machine_type",
                    machine_type_id=1,
                    planned_minutes=Decimal(60),
                ),
            ]
        )
        db.session.commit()

        errs = sched_manual.validate_preplan_schedule(1)
        assert errs == []


def test_confirm_creates_scheduled_dispatch(app):
    d = date(2026, 4, 11)
    with app.app_context():
        db.session.add(Role(id=1, name="管理员", code="admin", description=""))
        db.session.add(Company(id=1, name="C1", code="c1"))
        db.session.add(User(id=1, username="u1", password_hash="x", role_id=1, is_active=True))
        db.session.flush()
        db.session.add(MachineType(id=1, code="T1", name="MT"))
        db.session.add(Machine(id=1, machine_type_id=1, machine_no="M1", name="机1", status="enabled"))
        db.session.add(HrEmployee(id=1, company_id=1, employee_no="E1", name="张三", status="active"))
        db.session.flush()
        _seed_machine_calendar(machine_id=1, user_id=1, d=d)
        _seed_employee_calendar(employee_id=1, user_id=1, d=d)
        db.session.add(MachineOperatorAllowlist(machine_id=1, employee_id=1, is_active=True))
        db.session.add(ProductionPreplan(id=1, plan_date=d, status="planned", created_by=1))
        db.session.flush()
        db.session.add(
            ProductionWorkOrder(
                id=1,
                preplan_id=1,
                parent_kind="finished",
                parent_product_id=1,
                plan_date=d,
                status="planned",
                created_by=1,
            )
        )
        db.session.flush()
        db.session.add(
            ProductionWorkOrderOperation(
                id=1,
                preplan_id=1,
                work_order_id=1,
                step_no=1,
                step_code="S1",
                step_name="工序1",
                resource_kind="machine_type",
                machine_type_id=1,
                budget_machine_id=1,
                budget_operator_employee_id=1,
                plan_qty=Decimal(1),
                estimated_total_minutes=Decimal(60),
                created_by=1,
            )
        )
        db.session.flush()
        es = datetime.combine(d, time(9, 0))
        ef = datetime.combine(d, time(10, 0))
        db.session.add(
            ProductionWorkOrderOperationPlan(
                preplan_id=1,
                work_order_id=1,
                operation_id=1,
                plan_date=d,
                es=es,
                ef=ef,
                is_critical=False,
                resource_kind="machine_type",
                machine_type_id=1,
                planned_minutes=Decimal(60),
            )
        )
        db.session.commit()

        errs = sched_manual.confirm_preplan_schedule(preplan_id=1, user_id=1)
        assert errs == []

        from app.models import MachineScheduleDispatchLog

        log = MachineScheduleDispatchLog.query.filter_by(work_order_id=1).first()
        assert log is not None
        assert (log.state or "").strip() == "scheduled"
