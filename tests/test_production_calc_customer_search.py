from __future__ import annotations

from datetime import date

import pytest

from app import create_app, db
from app.auth.rbac_cache import invalidate_rbac_cache
from app.config import Config
from app.models import (
    Company,
    Customer,
    CustomerProduct,
    OrderItem,
    Product,
    ProductionPreplan,
    ProductionPreplanLine,
    Role,
    RoleAllowedCapability,
    RoleAllowedNav,
    SalesOrder,
    SysNavItem,
    User,
)


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}


@pytest.fixture()
def app():
    invalidate_rbac_cache()
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
    invalidate_rbac_cache()


def _login_client(app, user_id: int):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return client


def _seed_role_and_user(*, with_calc_cap: bool) -> User:
    nav = SysNavItem(
        code="production_preplan",
        title="预生产计划",
        endpoint="main.production_preplan_list",
        sort_order=10,
        is_active=True,
        admin_only=False,
        is_assignable=True,
        landing_priority=10,
    )
    db.session.add(nav)
    db.session.flush()

    role = Role(name="ProdUser", code=f"prod_user_{1 if with_calc_cap else 0}", description="")
    db.session.add(role)
    db.session.flush()

    db.session.add(RoleAllowedNav(role_id=role.id, nav_code="production_preplan"))
    if with_calc_cap:
        db.session.add(RoleAllowedCapability(role_id=role.id, cap_code="production.calc.action.run"))
    else:
        db.session.add(RoleAllowedCapability(role_id=role.id, cap_code="production.preplan.action.create"))

    user = User(username=f"u_{1 if with_calc_cap else 0}", password_hash="x", role_id=role.id, is_active=True)
    db.session.add(user)
    db.session.commit()
    return user


def _seed_customer_with_company(*, cid: int, company_code: str, customer_code: str, name: str) -> Customer:
    company = Company(id=cid, name=f"Company-{company_code}", code=company_code)
    db.session.add(company)
    db.session.flush()
    customer = Customer(
        customer_code=customer_code,
        short_code=customer_code,
        name=name,
        company_id=company.id,
    )
    db.session.add(customer)
    db.session.commit()
    return customer


def test_production_customers_search_requires_calc_capability(app):
    with app.app_context():
        _seed_customer_with_company(cid=1, company_code="AC", customer_code="AC001", name="阿尔法客户")
        user = _seed_role_and_user(with_calc_cap=False)
        invalidate_rbac_cache()

        client = _login_client(app, user.id)
        rv = client.get("/api/production/customers-search?q=阿尔")

        assert rv.status_code == 403


def test_production_customers_search_returns_customer_name_label(app):
    with app.app_context():
        _seed_customer_with_company(cid=1, company_code="AC", customer_code="AC001", name="阿尔法客户")
        _seed_customer_with_company(cid=2, company_code="BX", customer_code="BX001", name="贝塔客户")
        user = _seed_role_and_user(with_calc_cap=True)
        invalidate_rbac_cache()

        client = _login_client(app, user.id)
        rv = client.get("/api/production/customers-search?q=AC")

        assert rv.status_code == 200
        data = rv.get_json() or {}
        items = data.get("items") or []
        assert len(items) >= 1
        assert items[0]["label"] == "阿尔法客户"


def test_production_calc_with_order_id_still_merges_all_pending_of_customer(app, monkeypatch):
    with app.app_context():
        customer = _seed_customer_with_company(
            cid=1,
            company_code="C1",
            customer_code="CUST001",
            name="客户A",
        )
        user = _seed_role_and_user(with_calc_cap=True)

        p1 = Product(product_code="P001", name="产品1", base_unit="pcs")
        p2 = Product(product_code="P002", name="产品2", base_unit="pcs")
        db.session.add_all([p1, p2])
        db.session.flush()

        cp1 = CustomerProduct(customer_id=customer.id, product_id=p1.id, customer_material_no="M1", unit="pcs")
        cp2 = CustomerProduct(customer_id=customer.id, product_id=p2.id, customer_material_no="M2", unit="pcs")
        db.session.add_all([cp1, cp2])
        db.session.flush()

        so1 = SalesOrder(customer_id=customer.id, order_no="SO-001", salesperson="S", status="pending")
        so2 = SalesOrder(customer_id=customer.id, order_no="SO-002", salesperson="S", status="partial")
        db.session.add_all([so1, so2])
        db.session.flush()

        oi1 = OrderItem(order_id=so1.id, customer_product_id=cp1.id, quantity=10, unit="pcs", product_name="产品1")
        oi2 = OrderItem(order_id=so2.id, customer_product_id=cp2.id, quantity=20, unit="pcs", product_name="产品2")
        db.session.add_all([oi1, oi2])
        db.session.commit()

        from app.main import routes_production as routes_production_module

        monkeypatch.setattr(routes_production_module.production_svc, "measure_production_for_preplan", lambda **kwargs: [])
        monkeypatch.setattr(routes_production_module.orchestrator_engine, "emit_event", lambda **kwargs: None)

        invalidate_rbac_cache()
        client = _login_client(app, user.id)

        rv = client.post(
            "/production/calc",
            data={
                "plan_date": date.today().isoformat(),
                "customer_id": str(customer.id),
                "order_id": str(so1.id),
                "remark": "test",
            },
            follow_redirects=False,
        )

        assert rv.status_code == 302

        preplan = ProductionPreplan.query.order_by(ProductionPreplan.id.desc()).first()
        assert preplan is not None
        order_item_lines = ProductionPreplanLine.query.filter_by(preplan_id=preplan.id, source_type="order_item").all()
        source_order_item_ids = {int(x.source_order_item_id) for x in order_item_lines if x.source_order_item_id}
        assert source_order_item_ids == {oi1.id, oi2.id}


def test_production_calc_rejects_order_id_not_belonging_customer(app):
    with app.app_context():
        customer_a = _seed_customer_with_company(
            cid=1,
            company_code="C1",
            customer_code="CUST001",
            name="客户A",
        )
        customer_b = _seed_customer_with_company(
            cid=2,
            company_code="C2",
            customer_code="CUST002",
            name="客户B",
        )
        user = _seed_role_and_user(with_calc_cap=True)

        so_b = SalesOrder(customer_id=customer_b.id, order_no="SO-B-001", salesperson="S", status="pending")
        db.session.add(so_b)
        db.session.commit()

        invalidate_rbac_cache()
        client = _login_client(app, user.id)

        before_count = ProductionPreplan.query.count()
        rv = client.post(
            "/production/calc",
            data={
                "plan_date": date.today().isoformat(),
                "customer_id": str(customer_a.id),
                "order_id": str(so_b.id),
            },
            follow_redirects=False,
        )

        assert rv.status_code == 200
        after_count = ProductionPreplan.query.count()
        assert after_count == before_count
