"""主数据 nav_type（类型/内部分类）字段与导入相关回归。"""

import pytest

from app import create_app, db
from app.config import Config
from app.models import Product, SemiMaterial
from app.utils.form_display import clean_optional_text


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


def test_clean_optional_text_preserves_nav_type_label(app_ctx):
    assert clean_optional_text("  标准件  ", max_len=64) == "标准件"


def test_product_nav_type_roundtrip(app_ctx):
    p = Product(product_code="P0001", name="T", nav_type="电子类")
    db.session.add(p)
    db.session.commit()
    again = Product.query.filter_by(product_code="P0001").first()
    assert again is not None
    assert again.nav_type == "电子类"


def test_semi_material_nav_type_roundtrip(app_ctx):
    sm = SemiMaterial(
        kind="semi",
        code="SM0001",
        name="S",
        nav_type="机加件",
    )
    db.session.add(sm)
    db.session.commit()
    again = SemiMaterial.query.filter_by(code="SM0001").first()
    assert again.nav_type == "机加件"
