"""库存批次手工来源：normalize_manual_batch_source 与落库。"""

from datetime import date

import pytest

from app import create_app, db
from app.auth.rbac_cache import invalidate_rbac_cache
from app.config import Config
from app.models import InventoryMovementBatch
from app.services import inventory_svc


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


def test_normalize_manual_batch_source_empty_is_form():
    assert inventory_svc.normalize_manual_batch_source(None) == inventory_svc.BATCH_SOURCE_FORM
    assert inventory_svc.normalize_manual_batch_source("") == inventory_svc.BATCH_SOURCE_FORM
    assert inventory_svc.normalize_manual_batch_source("  ") == inventory_svc.BATCH_SOURCE_FORM


def test_normalize_manual_batch_source_custom():
    assert inventory_svc.normalize_manual_batch_source(" 客户退货 ") == "客户退货"


def test_normalize_manual_batch_source_reserved_raises():
    with pytest.raises(ValueError, match="保留字"):
        inventory_svc.normalize_manual_batch_source("excel")
    with pytest.raises(ValueError, match="保留字"):
        inventory_svc.normalize_manual_batch_source("delivery")


def test_normalize_manual_batch_source_too_long_raises():
    with pytest.raises(ValueError, match="最多"):
        inventory_svc.normalize_manual_batch_source("x" * 65)


def test_create_movement_batch_custom_source_persists(app):
    with app.app_context():
        b = inventory_svc.create_movement_batch(
            category=inventory_svc.INV_FINISHED,
            biz_date=date(2026, 1, 1),
            direction="in",
            source="盘盈调整",
            line_count=0,
            created_by=1,
        )
        db.session.commit()
        bid = b.id
        db.session.expunge_all()
        again = db.session.get(InventoryMovementBatch, bid)
        assert again is not None
        assert again.source == "盘盈调整"
