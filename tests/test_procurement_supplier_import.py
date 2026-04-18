from decimal import Decimal

import pytest

from openpyxl import Workbook

from app import create_app, db
from app.config import Config
from app.main.routes_procurement import (
    _parse_supplier_import_excel_ws,
    _upsert_supplier_material_maps_no_delete,
)
from app.models import Company, SemiMaterial, Supplier, SupplierMaterialMap


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


def test_supplier_import_upsert_only_does_not_delete_other_mappings(app_ctx):
    company = Company(name="Test Co", code="C0001", is_default=1)
    m1 = SemiMaterial(kind="material", code="M001", name="物料A", base_unit="KG")
    m2 = SemiMaterial(kind="material", code="M002", name="物料B", base_unit="KG")
    supplier = Supplier(company_id=0, name="供应商A", is_active=True)

    db.session.add_all([company, m1, m2, supplier])
    db.session.flush()
    supplier.company_id = company.id

    # 先创建一条其它物料映射，导入时不应被删除
    db.session.add_all(
        [
            SupplierMaterialMap(
                company_id=company.id,
                supplier_id=supplier.id,
                material_id=m1.id,
                is_active=True,
                is_preferred=False,
                last_unit_price=Decimal("9.9"),
            ),
            SupplierMaterialMap(
                company_id=company.id,
                supplier_id=supplier.id,
                material_id=m2.id,
                is_active=True,
                is_preferred=False,
                last_unit_price=Decimal("1.1"),
            ),
        ]
    )
    db.session.commit()

    _upsert_supplier_material_maps_no_delete(
        supplier,
        [
            {
                "material_id": m1.id,
                "is_preferred": None,  # 不修改默认标记
                "remark": None,
                "last_unit_price": Decimal("10.0"),
            }
        ],
    )
    db.session.commit()

    assert SupplierMaterialMap.query.filter_by(
        supplier_id=supplier.id, material_id=m2.id
    ).first() is not None


def test_supplier_import_preferred_clears_other_defaults(app_ctx):
    company = Company(name="Test Co", code="C0001", is_default=1)
    m1 = SemiMaterial(kind="material", code="M001", name="物料A", base_unit="KG")
    supplier1 = Supplier(company_id=0, name="供应商A", is_active=True)
    supplier2 = Supplier(company_id=0, name="供应商B", is_active=True)

    db.session.add_all([company, m1, supplier1, supplier2])
    db.session.flush()
    supplier1.company_id = company.id
    supplier2.company_id = company.id

    db.session.add_all(
        [
            SupplierMaterialMap(
                company_id=company.id,
                supplier_id=supplier1.id,
                material_id=m1.id,
                is_active=True,
                is_preferred=True,  # 当前默认
                last_unit_price=Decimal("9.9"),
            ),
            SupplierMaterialMap(
                company_id=company.id,
                supplier_id=supplier2.id,
                material_id=m1.id,
                is_active=True,
                is_preferred=False,
                last_unit_price=Decimal("1.1"),
            ),
        ]
    )
    db.session.commit()

    _upsert_supplier_material_maps_no_delete(
        supplier2,
        [
            {
                "material_id": m1.id,
                "is_preferred": True,  # 切换默认
                "remark": None,
                "last_unit_price": Decimal("2.2"),
            }
        ],
    )
    db.session.commit()

    mapping1 = SupplierMaterialMap.query.filter_by(
        supplier_id=supplier1.id, material_id=m1.id
    ).first()
    mapping2 = SupplierMaterialMap.query.filter_by(
        supplier_id=supplier2.id, material_id=m1.id
    ).first()

    assert mapping2.is_preferred is True
    assert mapping1.is_preferred is False


def test_supplier_import_excel_parser_resolves_material_by_name_and_spec(app_ctx):
    company = Company(name="Test Co", code="C0001", is_default=1)
    m = SemiMaterial(
        kind="material",
        code="X001",
        name="不锈钢板",
        spec="304 2mm",
        base_unit="张",
    )
    db.session.add_all([company, m])
    db.session.commit()

    wb = Workbook()
    ws = wb.active
    ws.append(["供应商名称"] + [""] * 10)
    ws.append(
        [
            "供应商甲",
            "",
            "",
            "",
            "",
            "",
            "不锈钢板",
            "304 2mm",
            "12.5",
            "",
            "",
        ]
    )

    data, errors = _parse_supplier_import_excel_ws(ws, company.id)
    assert errors == []
    assert "供应商甲" in data
    assert len(data["供应商甲"]["maps"]) == 1
    assert data["供应商甲"]["maps"][0]["material_id"] == m.id
    assert data["供应商甲"]["maps"][0]["last_unit_price"] == Decimal("12.5")


def test_supplier_import_excel_parser_errors_on_ambiguous_name_spec(app_ctx):
    company = Company(name="Test Co", code="C0001", is_default=1)
    m1 = SemiMaterial(
        kind="material", code="A1", name="同名", spec="", base_unit="个"
    )
    m2 = SemiMaterial(
        kind="material", code="A2", name="同名", spec="", base_unit="个"
    )
    db.session.add_all([company, m1, m2])
    db.session.commit()

    wb = Workbook()
    ws = wb.active
    ws.append(["供应商名称"] + [""] * 10)
    ws.append(["乙供应商", "", "", "", "", "", "同名", "", "", "", ""])

    _data, errors = _parse_supplier_import_excel_ws(ws, company.id)
    assert any("多条" in e for e in errors)

