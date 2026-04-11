"""生产测算与库存预留：ATP 扣减、多预计划互斥。"""

from datetime import date
from decimal import Decimal

import pytest

from app import create_app, db
from app.config import Config
from app.models import (
    BomHeader,
    BomLine,
    InventoryOpeningBalance,
    InventoryReservation,
    MachineType,
    Product,
    ProductionComponentNeed,
    ProductionPreplan,
    ProductionPreplanLine,
    ProductionProcessTemplate,
    ProductionProcessTemplateStep,
    ProductionProductRouting,
    ProductionWorkOrder,
    SemiMaterial,
)
from app.services.inventory_svc import (
    RES_REF_PREPLAN,
    RES_STATUS_ACTIVE,
    atp_for_item_aggregate,
    ledger_qty_aggregate,
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


def test_reservation_reduces_atp_for_second_preplan(app_ctx):
    db.session.add(MachineType(code="MT-RES", name="机类型-预留测", is_active=True))
    product = Product(product_code="P-RES", name="成品R", base_unit="pcs")
    semi = SemiMaterial(kind="semi", code="S-RES", name="半成品R", base_unit="pcs")
    material = SemiMaterial(
        kind="material", code="M-RES", name="原料R", base_unit="pcs"
    )
    db.session.add_all([product, semi, material])
    db.session.flush()

    _seed_bom(product_id=product.id, semi_id=semi.id, material_id=material.id)
    _seed_template_and_routing(product_id=product.id, semi_id=semi.id)

    db.session.add(
        InventoryOpeningBalance(
            category="material",
            product_id=0,
            material_id=material.id,
            storage_area="",
            opening_qty=Decimal("10"),
            unit="pcs",
        )
    )
    db.session.commit()

    assert ledger_qty_aggregate("material", material.id) == Decimal("10")
    assert atp_for_item_aggregate("material", material.id) == Decimal("10")

    pre1 = ProductionPreplan(
        source_type="manual",
        plan_date=date(2026, 4, 10),
        customer_id=0,
        status="draft",
        created_by=1,
    )
    db.session.add(pre1)
    db.session.flush()
    db.session.add(
        ProductionPreplanLine(
            preplan_id=pre1.id,
            line_no=1,
            product_id=product.id,
            quantity=Decimal("6"),
            unit="pcs",
        )
    )
    db.session.commit()

    measure_production_for_preplan(preplan_id=pre1.id, created_by=1)

    rows = InventoryReservation.query.filter_by(
        ref_type=RES_REF_PREPLAN, ref_id=pre1.id, status=RES_STATUS_ACTIVE
    ).all()
    mat_reserved = sum(
        Decimal(str(r.reserved_qty))
        for r in rows
        if r.category == "material" and r.material_id == material.id
    )
    assert mat_reserved == Decimal("6")
    assert atp_for_item_aggregate("material", material.id) == Decimal("4")

    pre2 = ProductionPreplan(
        source_type="manual",
        plan_date=date(2026, 4, 11),
        customer_id=0,
        status="draft",
        created_by=1,
    )
    db.session.add(pre2)
    db.session.flush()
    db.session.add(
        ProductionPreplanLine(
            preplan_id=pre2.id,
            line_no=1,
            product_id=product.id,
            quantity=Decimal("5"),
            unit="pcs",
        )
    )
    db.session.commit()

    measure_production_for_preplan(preplan_id=pre2.id, created_by=1)

    cn = (
        ProductionComponentNeed.query.filter_by(
            preplan_id=pre2.id,
            child_kind="material",
            child_material_id=material.id,
        )
        .order_by(ProductionComponentNeed.id.asc())
        .first()
    )
    assert cn is not None
    assert cn.stock_covered_qty <= Decimal("4")
    assert cn.shortage_qty >= Decimal("1")

    # 重算 pre1 应释放旧预留并重建
    measure_production_for_preplan(preplan_id=pre1.id, created_by=1)
    rows_after = InventoryReservation.query.filter_by(
        ref_type=RES_REF_PREPLAN, ref_id=pre1.id
    ).all()
    mat_reserved_again = sum(
        Decimal(str(r.reserved_qty))
        for r in rows_after
        if r.category == "material" and r.material_id == material.id
    )
    assert mat_reserved_again == Decimal("6")

    assert ProductionWorkOrder.query.filter_by(preplan_id=pre2.id).first() is not None
