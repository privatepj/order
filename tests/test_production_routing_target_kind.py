from datetime import date
from decimal import Decimal

import pytest

from app import create_app, db
from app.config import Config
from app.models import (
    BomHeader,
    BomLine,
    Product,
    ProductionPreplan,
    ProductionPreplanLine,
    ProductionProcessTemplate,
    ProductionProcessTemplateStep,
    ProductionProductRouting,
    ProductionWorkOrder,
    ProductionWorkOrderOperation,
    SemiMaterial,
)
from app.services.production_svc import measure_production_for_preplan


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


def _seed_template_and_routing(*, product_id: int, semi_id: int) -> None:
    tpl = ProductionProcessTemplate(
        name="通用模板",
        version="v1",
        is_active=True,
        created_by=1,
    )
    db.session.add(tpl)
    db.session.flush()
    db.session.add(
        ProductionProcessTemplateStep(
            template_id=tpl.id,
            step_no=1,
            step_code="S1",
            step_name="下料",
            resource_kind="machine_type",
            machine_type_id=1,
            setup_minutes=Decimal("10"),
            run_minutes_per_unit=Decimal("1.5"),
            is_active=True,
        )
    )
    db.session.add_all(
        [
            ProductionProductRouting(
                target_kind="finished",
                target_id=product_id,
                product_id=product_id,
                template_id=tpl.id,
                is_active=True,
                created_by=1,
            ),
            ProductionProductRouting(
                target_kind="semi",
                target_id=semi_id,
                product_id=0,
                template_id=tpl.id,
                is_active=True,
                created_by=1,
            ),
        ]
    )


def _seed_bom(*, product_id: int, semi_id: int, material_id: int) -> None:
    finished_header = BomHeader(
        parent_kind="finished",
        parent_product_id=product_id,
        version_no=1,
        is_active=True,
    )
    db.session.add(finished_header)
    db.session.flush()
    db.session.add(
        BomLine(
            bom_header_id=finished_header.id,
            line_no=1,
            child_kind="semi",
            child_material_id=semi_id,
            quantity=Decimal("1"),
            unit="pcs",
        )
    )

    semi_header = BomHeader(
        parent_kind="semi",
        parent_material_id=semi_id,
        version_no=1,
        is_active=True,
    )
    db.session.add(semi_header)
    db.session.flush()
    db.session.add(
        BomLine(
            bom_header_id=semi_header.id,
            line_no=1,
            child_kind="material",
            child_material_id=material_id,
            quantity=Decimal("1"),
            unit="pcs",
        )
    )


def test_measure_generates_operations_for_finished_and_semi(app_ctx):
    product = Product(product_code="P-001", name="成品A", base_unit="pcs")
    semi = SemiMaterial(kind="semi", code="S-001", name="半成品A", base_unit="pcs")
    material = SemiMaterial(kind="material", code="M-001", name="原料A", base_unit="pcs")
    db.session.add_all([product, semi, material])
    db.session.flush()

    _seed_bom(product_id=product.id, semi_id=semi.id, material_id=material.id)
    _seed_template_and_routing(product_id=product.id, semi_id=semi.id)

    preplan = ProductionPreplan(
        source_type="manual",
        plan_date=date(2026, 4, 10),
        customer_id=0,
        status="draft",
        created_by=1,
    )
    db.session.add(preplan)
    db.session.flush()
    db.session.add(
        ProductionPreplanLine(
            preplan_id=preplan.id,
            line_no=1,
            product_id=product.id,
            quantity=Decimal("5"),
            unit="pcs",
        )
    )
    db.session.commit()

    measure_production_for_preplan(preplan_id=preplan.id, created_by=1)

    finished_wo = ProductionWorkOrder.query.filter_by(
        preplan_id=preplan.id, parent_kind="finished", parent_product_id=product.id
    ).first()
    semi_wo = ProductionWorkOrder.query.filter_by(
        preplan_id=preplan.id, parent_kind="semi", parent_material_id=semi.id
    ).first()
    assert finished_wo is not None
    assert semi_wo is not None

    finished_ops = ProductionWorkOrderOperation.query.filter_by(work_order_id=finished_wo.id).all()
    semi_ops = ProductionWorkOrderOperation.query.filter_by(work_order_id=semi_wo.id).all()
    assert len(finished_ops) == 1
    assert len(semi_ops) == 1
    assert finished_ops[0].step_name == "下料"
    assert semi_ops[0].step_name == "下料"
