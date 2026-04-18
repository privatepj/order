"""部门生产看板与机台归属（SQLite 内存库）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app import create_app, db
from app.config import Config
from app.models import (
    Company,
    Customer,
    HrDepartment,
    HrDepartmentWorkTypeMap,
    HrWorkType,
    Machine,
    MachineType,
    Product,
    ProductionPreplan,
    ProductionWorkOrder,
    ProductionWorkOrderOperation,
    Role,
    User,
)
from app.services import production_dept_board_svc


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


def _base_seed(d: date):
    db.session.add(Role(id=1, name="管理员", code="admin", description=""))
    db.session.add(Company(id=1, name="C1", code="c1", is_default=1))
    db.session.add(User(id=1, username="u1", password_hash="x", role_id=1, is_active=True))
    db.session.add(HrDepartment(id=1, company_id=1, name="车间甲", sort_order=0))
    db.session.add(HrDepartment(id=2, company_id=1, name="车间乙", sort_order=1))
    db.session.add(Customer(id=1, customer_code="CUST1", name="客户1", company_id=1))
    db.session.add(MachineType(id=1, code="T1", name="机种1"))
    db.session.add(
        Product(id=1, product_code="P1", name="成品1", spec="", base_unit="pcs")
    )
    db.session.flush()


def test_board_filters_by_machine_owning_dept(app):
    d = date(2026, 4, 18)
    with app.app_context():
        _base_seed(d)
        db.session.add(
            Machine(
                id=1,
                machine_type_id=1,
                machine_no="M1",
                name="机1",
                status="enabled",
                owning_hr_department_id=1,
            )
        )
        db.session.add(
            ProductionPreplan(
                id=1,
                plan_date=d,
                customer_id=1,
                status="planned",
                created_by=1,
            )
        )
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
                step_name="车削",
                resource_kind="machine_type",
                machine_type_id=1,
                budget_machine_id=1,
                plan_qty=Decimal(1),
                estimated_total_minutes=Decimal(60),
                created_by=1,
            )
        )
        db.session.commit()

        rows_ok = production_dept_board_svc.list_board_rows(dept_id=1, company_id=1)
        assert len(rows_ok) == 1
        assert rows_ok[0]["work_order_id"] == 1

        rows_other = production_dept_board_svc.list_board_rows(dept_id=2, company_id=1)
        assert len(rows_other) == 0


def test_board_hr_work_type_department_map(app):
    d = date(2026, 4, 18)
    with app.app_context():
        _base_seed(d)
        db.session.add(
            HrWorkType(id=10, company_id=1, name="工种X", sort_order=0, is_active=True)
        )
        db.session.add(
            HrDepartmentWorkTypeMap(
                company_id=1,
                department_id=1,
                work_type_id=10,
                is_active=True,
            )
        )
        db.session.add(
            ProductionPreplan(
                id=1,
                plan_date=d,
                customer_id=1,
                status="planned",
                created_by=1,
            )
        )
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
                step_name="手工",
                resource_kind="hr_work_type",
                hr_work_type_id=10,
                plan_qty=Decimal(1),
                estimated_total_minutes=Decimal(30),
                created_by=1,
            )
        )
        db.session.commit()

        rows = production_dept_board_svc.list_board_rows(dept_id=1, company_id=1)
        assert len(rows) == 1

        rows_b = production_dept_board_svc.list_board_rows(dept_id=2, company_id=1)
        assert len(rows_b) == 0
