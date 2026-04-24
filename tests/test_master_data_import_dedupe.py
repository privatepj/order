"""主数据导入：按 品名+规格+类别 去重。"""

from io import BytesIO

import pytest
from openpyxl import Workbook

from app import create_app, db
from app.config import Config
from app.models import Product, Role, SemiMaterial, User


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
        role = Role(name="Admin", code="admin")
        db.session.add(role)
        db.session.flush()
        user = User(username="admin", password_hash="x", role_id=role.id, is_active=True)
        db.session.add(user)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


def _login_client(app):
    client = app.test_client()
    with app.app_context():
        user = User.query.filter_by(username="admin").first()
        assert user is not None
        uid = user.id
    with client.session_transaction() as session:
        session["_user_id"] = str(uid)
        session["_fresh"] = True
    return client


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for ridx, row in enumerate(rows, start=1):
        for cidx, val in enumerate(row, start=1):
            ws.cell(ridx, cidx, val)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_product_import_dedupe_by_name_spec(app):
    with app.app_context():
        db.session.add(
            Product(
                product_code="P0001",
                name="成品A",
                spec="S1",
                base_unit="pcs",
            )
        )
        db.session.commit()

    client = _login_client(app)
    file_data = _xlsx(
        [
            ["产品编号", "产品名称", "规格", "基础单位", "备注", "系列"],
            ["", "成品A", "S1", "箱", "更新备注", "Alpha"],
        ]
    )
    resp = client.post(
        "/products/import",
        data={"file": (file_data, "products.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        rows = Product.query.filter(Product.name == "成品A", Product.spec == "S1").all()
        assert len(rows) == 1
        assert rows[0].product_code == "P0001"
        assert rows[0].base_unit == "箱"


def test_semi_material_import_dedupe_by_name_spec_and_kind(app):
    with app.app_context():
        db.session.add(
            SemiMaterial(
                kind="semi",
                code="SM0001",
                name="半成品A",
                spec="M1",
                base_unit="kg",
            )
        )
        db.session.commit()

    client = _login_client(app)
    file_data = _xlsx(
        [
            ["物料编号（可留空）", "名称", "规格", "基础单位", "备注", "系列"],
            ["", "半成品A", "M1", "包", "更新备注", "Beta"],
        ]
    )
    resp = client.post(
        "/semi-materials/import?kind=semi",
        data={"file": (file_data, "semi.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        rows = (
            SemiMaterial.query.filter(
                SemiMaterial.kind == "semi",
                SemiMaterial.name == "半成品A",
                SemiMaterial.spec == "M1",
            ).all()
        )
        assert len(rows) == 1
        assert rows[0].code == "SM0001"
        assert rows[0].base_unit == "包"


def test_procurement_material_import_dedupe_by_name_spec(app):
    with app.app_context():
        db.session.add(
            SemiMaterial(
                kind="material",
                code="MT0001",
                name="原材料A",
                spec="R1",
                base_unit="kg",
            )
        )
        db.session.commit()

    client = _login_client(app)
    file_data = _xlsx(
        [
            ["物料编号（可留空）", "名称", "规格", "基础单位", "备注", "系列"],
            ["", "原材料A", "R1", "袋", "更新备注", "Gamma"],
        ]
    )
    resp = client.post(
        "/procurement/materials/import",
        data={"file": (file_data, "material.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        rows = (
            SemiMaterial.query.filter(
                SemiMaterial.kind == "material",
                SemiMaterial.name == "原材料A",
                SemiMaterial.spec == "R1",
            ).all()
        )
        assert len(rows) == 1
        assert rows[0].code == "MT0001"
        assert rows[0].base_unit == "袋"
