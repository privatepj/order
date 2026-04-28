import pytest

from app import create_app, db
from app.config import Config
from app.models import (
    Company,
    HrDepartment,
    HrEmployee,
    HrPayrollLine,
    ProductionProcessTemplate,
    Role,
    Supplier,
    User,
)


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def admin_client(app):
    with app.app_context():
        role = Role(name="Admin", code="admin")
        db.session.add(role)
        db.session.flush()
        user = User(username="admin", password_hash="pwd", role_id=role.id, is_active=True)
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return client


def _seed_company():
    co = Company(
        name="Co",
        code="CO",
        billing_cycle_day=1,
        is_default=True,
    )
    db.session.add(co)
    db.session.flush()
    return co


def test_supplier_edit_page_hides_none_literal(app, admin_client):
    with app.app_context():
        co = _seed_company()
        sp = Supplier(
            company_id=co.id,
            name="S1",
            contact_name="None",
            phone="None",
            address="None",
            remark="None",
            is_active=True,
        )
        db.session.add(sp)
        db.session.commit()
        sp_id = sp.id

    r = admin_client.get(f"/procurement/suppliers/{sp_id}/edit")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'name="contact_name" value=""' in html
    assert 'name="phone" value=""' in html
    assert 'name="address" value=""' in html
    assert '<textarea class="form-control" name="remark" rows="3" maxlength="500"></textarea>' in html


def test_hr_payroll_edit_page_hides_none_literal(app, admin_client):
    with app.app_context():
        co = _seed_company()
        dept = HrDepartment(company_id=co.id, name="D1")
        db.session.add(dept)
        db.session.flush()
        emp = HrEmployee(company_id=co.id, employee_no="E001", name="Emp", department_id=dept.id)
        db.session.add(emp)
        db.session.flush()
        line = HrPayrollLine(
            company_id=co.id,
            employee_id=emp.id,
            period="2026-04",
            wage_kind="monthly",
            work_hours=1,
            hourly_rate=0,
            base_salary=100,
            allowance=0,
            deduction=0,
            net_pay=100,
            remark="None",
            created_by=1,
        )
        db.session.add(line)
        db.session.commit()
        line_id = line.id

    r = admin_client.get(f"/hr-payroll/{line_id}/edit")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'name="remark" value=""' in html


def test_process_template_edit_page_hides_none_literal(app, admin_client):
    with app.app_context():
        tpl = ProductionProcessTemplate(
            name="T1",
            version="v1",
            is_active=True,
            remark="None",
            created_by=1,
        )
        db.session.add(tpl)
        db.session.commit()
        tpl_id = tpl.id

    r = admin_client.get(f"/production/process-templates/{tpl_id}/edit")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'name="remark" maxlength="255" value=""' in html
