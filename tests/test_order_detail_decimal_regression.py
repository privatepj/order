from datetime import date
from decimal import Decimal

import pytest

from app import create_app, db
from app.config import Config
from app.models import Company, Customer, OrderItem, Role, SalesOrder, User


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


@pytest.fixture()
def app_ctx(app):
    with app.app_context():
        yield


@pytest.fixture()
def admin_client(app):
    with app.app_context():
        role = Role(name="Admin", code="admin")
        db.session.add(role)
        db.session.flush()
        user = User(
            username="admin_order_detail",
            password_hash="admin",
            role_id=role.id,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return client


def _seed_order_with_items() -> int:
    company = Company(
        name="Test Company",
        code="TST_COMPANY_ORDER_DETAIL",
        delivery_no_prefix="DL",
        billing_cycle_day=1,
        is_default=1,
    )
    customer = Customer(
        customer_code="TST_CUST_ORDER_DETAIL",
        short_code="TCOD",
        name="Test Customer",
        company=company,
    )
    order = SalesOrder(
        order_no="SO-DETAIL-DECIMAL-001",
        customer=customer,
        salesperson="tester",
        order_date=date(2026, 4, 28),
        payment_type="monthly",
    )
    item_1 = OrderItem(
        order=order,
        product_name="Product A",
        product_spec="Spec A",
        quantity=Decimal("10"),
        unit="PCS",
    )
    item_2 = OrderItem(
        order=order,
        product_name="Product B",
        product_spec="Spec B",
        quantity=Decimal("5"),
        unit="PCS",
    )
    db.session.add_all([company, customer, order, item_1, item_2])
    db.session.commit()
    return int(order.id)


def test_order_detail_decimal_maps_do_not_raise_type_error(app_ctx, admin_client, monkeypatch):
    order_id = _seed_order_with_items()

    def _fake_maps(order_item_ids):
        # Simulate Decimal payloads with partial missing keys to hit Decimal defaults.
        ids = list(order_item_ids)
        shipped_map = {ids[0]: Decimal("1.2500")} if ids else {}
        in_transit_map = {ids[1]: Decimal("0.5000")} if len(ids) > 1 else {}
        return shipped_map, in_transit_map

    monkeypatch.setattr("app.main.routes_order.order_item_shipped_and_in_transit_maps", _fake_maps)

    resp = admin_client.get(f"/orders/{order_id}")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "1.2500" in body
    assert "0.5000" in body
    assert "8.7500" in body
    assert "4.5000" in body
