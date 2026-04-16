from datetime import date
from decimal import Decimal

import pytest

from app import create_app, db
from app.config import Config
from app.models import Company, Customer, Product, CustomerProduct
from app.services.crm_opportunity_svc import (
    add_opportunity_line,
    create_opportunity_from_data,
    generate_order_from_opportunity,
    set_opportunity_stage,
)


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
def base_data(app):
    with app.app_context():
        company = Company(
            name="测试主体",
            code="TST",
            billing_cycle_day=1,
            is_default=1,
            order_no_prefix="SO",
        )
        customer = Customer(
            customer_code="C001",
            short_code="客户A",
            name="客户A",
            company=company,
        )
        product = Product(product_code="P001", name="产品A", spec="10*10", base_unit="PCS")
        db.session.add_all([company, customer, product])
        db.session.flush()

        cp = CustomerProduct(
            customer_id=customer.id,
            product_id=product.id,
            customer_material_no="MAT-001",
            unit="PCS",
            price=Decimal("10.5"),
            currency="CNY",
        )
        db.session.add(cp)
        db.session.commit()

        # 返回纯 id，避免 fixture 退出后 ORM 实例进入 detached 状态
        return {
            "company_id": company.id,
            "customer_id": customer.id,
            "product_id": product.id,
            "cp_id": cp.id,
        }


def test_set_opportunity_won_without_lines_fails(app, base_data):
    with app.app_context():
        opp, err = create_opportunity_from_data(
            {"customer_id": base_data["customer_id"], "stage": "draft"}
        )
        assert err is None

        # draft -> qualified
        err = set_opportunity_stage(opp, "qualified")
        assert err is None

        # qualified -> won（但目前没有机会产品行）
        err = set_opportunity_stage(opp, "won")
        assert err is not None
        assert "请先维护机会产品行" in err


def test_generate_order_from_opportunity_sets_won_and_creates_items(app, base_data):
    with app.app_context():
        opp, err = create_opportunity_from_data(
            {"customer_id": base_data["customer_id"], "stage": "qualified"}
        )
        assert err is None

        # 添加一行：样板 -> 应用 price=0
        line, err = add_opportunity_line(
            opp,
            customer_product_id=base_data["cp_id"],
            quantity=Decimal("2"),
            is_sample=True,
            is_spare=False,
        )
        assert err is None
        assert line.id is not None

        order, err = generate_order_from_opportunity(
            opp.id,
            generation_data={
                "customer_order_no": "CUST-ORD-001",
                "salesperson": "tester",
                "order_date": date.today().isoformat(),
                "required_date": date.today().isoformat(),
                "payment_type": "monthly",
                "remark": "crm测试",
            },
        )
        assert err is None
        assert order is not None

        # 机会应已被标记为 won
        db.session.refresh(opp)
        assert opp.stage == "won"
        assert opp.won_order_id == order.id

        # 订单明细：样板/备品行 price 应为 0，amount 应为 0
        assert len(order.items) >= 1
        for oi in order.items:
            if bool(oi.is_sample) or bool(oi.is_spare):
                assert oi.customer_product_id == base_data["cp_id"]
                assert oi.price == Decimal("0")
                assert oi.amount == Decimal("0")

