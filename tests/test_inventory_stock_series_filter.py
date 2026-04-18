"""库存结存查询：系列筛选与 distinct 选项。"""

from decimal import Decimal

import pytest

from app import create_app, db
from app.config import Config
from app.models import InventoryOpeningBalance, Product, SemiMaterial
from app.services import inventory_svc


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


def _seed_stock_rows(app):
    with app.app_context():
        fg_a = Product(
            product_code="P-SER-A",
            name="成品甲",
            spec="",
            series="Alpha",
            base_unit="pcs",
        )
        fg_b = Product(
            product_code="P-SER-B",
            name="成品乙",
            spec="",
            series="Beta",
            base_unit="pcs",
        )
        semi = SemiMaterial(
            kind="semi",
            code="S-SER-1",
            name="半成品丙",
            spec="",
            series="Alpha",
            base_unit="kg",
        )
        db.session.add_all([fg_a, fg_b, semi])
        db.session.flush()
        db.session.add_all(
            [
                InventoryOpeningBalance(
                    category=inventory_svc.INV_FINISHED,
                    product_id=fg_a.id,
                    material_id=0,
                    storage_area="A1",
                    opening_qty=Decimal("1"),
                ),
                InventoryOpeningBalance(
                    category=inventory_svc.INV_FINISHED,
                    product_id=fg_b.id,
                    material_id=0,
                    storage_area="A1",
                    opening_qty=Decimal("2"),
                ),
                InventoryOpeningBalance(
                    category=inventory_svc.INV_SEMI,
                    product_id=0,
                    material_id=semi.id,
                    storage_area="A1",
                    opening_qty=Decimal("3"),
                ),
            ]
        )
        db.session.commit()


def test_list_distinct_stock_series_options_sorted_unique(app):
    _seed_stock_rows(app)
    with app.app_context():
        opts = inventory_svc.list_distinct_stock_series_options()
    assert opts == ["Alpha", "Beta"]


def test_query_stock_aggregate_filter_series(app):
    _seed_stock_rows(app)
    with app.app_context():
        rows_all, total_all = inventory_svc.query_stock_aggregate()
        assert total_all == 3

        rows_alpha, total_alpha = inventory_svc.query_stock_aggregate(series="Alpha")
        assert total_alpha == 2
        cats = {r["category"] for r in rows_alpha}
        assert cats == {inventory_svc.INV_FINISHED, inventory_svc.INV_SEMI}
        codes = {r["product_code"] for r in rows_alpha}
        assert codes == {"P-SER-A", "S-SER-1"}

        rows_beta, total_beta = inventory_svc.query_stock_aggregate(series="Beta")
        assert total_beta == 1
        assert rows_beta[0]["product_code"] == "P-SER-B"

        rows_finished_alpha, _ = inventory_svc.query_stock_aggregate(
            category=inventory_svc.INV_FINISHED,
            series="Alpha",
        )
        assert len(rows_finished_alpha) == 1
        assert rows_finished_alpha[0]["product_code"] == "P-SER-A"
