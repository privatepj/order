"""预计划排程：BOM 子工单完工后再排父工单（方案 A）。"""
from datetime import date, datetime, timedelta
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
    ProductionWorkOrderOperationPlan,
    SemiMaterial,
)
from app.services.production_schedule_svc import list_bom_work_order_gate_errors
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


def test_measure_schedule_parent_after_semi(app_ctx):
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

    from app.models import ProductionWorkOrder

    finished_wo = ProductionWorkOrder.query.filter_by(
        preplan_id=preplan.id, parent_kind="finished", parent_product_id=product.id
    ).first()
    semi_wo = ProductionWorkOrder.query.filter_by(
        preplan_id=preplan.id, parent_kind="semi", parent_material_id=semi.id
    ).first()
    assert finished_wo is not None and semi_wo is not None

    semi_plans = ProductionWorkOrderOperationPlan.query.filter_by(
        work_order_id=semi_wo.id
    ).all()
    fin_plans = ProductionWorkOrderOperationPlan.query.filter_by(
        work_order_id=finished_wo.id
    ).all()
    assert semi_plans and fin_plans

    max_ef_semi = max(p.ef for p in semi_plans if p.ef)
    min_es_fin = min(p.es for p in fin_plans if p.es)
    assert min_es_fin >= max_ef_semi, (
        f"父工单最早 ES 应不早于子工单最晚 EF: min_es_fin={min_es_fin}, max_ef_semi={max_ef_semi}"
    )

    rows = []
    for plan in ProductionWorkOrderOperationPlan.query.filter_by(
        preplan_id=preplan.id
    ).all():
        rows.append(
            {
                "work_order_id": int(plan.work_order_id),
                "es": plan.es,
                "ef": plan.ef,
            }
        )
    assert list_bom_work_order_gate_errors(preplan_id=preplan.id, rows=rows) == []


def test_list_bom_gate_errors_when_parent_starts_before_child(app_ctx):
    """手工构造行：父 WO#2 早于子 WO#1 完工，应报错。"""
    product = Product(product_code="P-GATE", name="成品G", base_unit="pcs")
    semi = SemiMaterial(kind="semi", code="S-GATE", name="半成品G", base_unit="pcs")
    db.session.add_all([product, semi])
    db.session.flush()

    preplan = ProductionPreplan(
        source_type="manual",
        plan_date=date(2026, 4, 10),
        customer_id=0,
        status="draft",
        created_by=1,
    )
    db.session.add(preplan)
    db.session.flush()
    from app.models import ProductionWorkOrder

    wo_child = ProductionWorkOrder(
        preplan_id=preplan.id,
        root_preplan_line_id=None,
        parent_kind="semi",
        parent_product_id=0,
        parent_material_id=semi.id,
        plan_date=date(2026, 4, 10),
        status="planned",
        demand_qty=Decimal("1"),
        stock_covered_qty=Decimal("0"),
        to_produce_qty=Decimal("1"),
        created_by=1,
    )
    wo_parent = ProductionWorkOrder(
        preplan_id=preplan.id,
        root_preplan_line_id=None,
        parent_kind="finished",
        parent_product_id=product.id,
        parent_material_id=0,
        plan_date=date(2026, 4, 10),
        status="planned",
        demand_qty=Decimal("1"),
        stock_covered_qty=Decimal("0"),
        to_produce_qty=Decimal("1"),
        created_by=1,
    )
    db.session.add_all([wo_child, wo_parent])
    db.session.flush()
    from app.models import ProductionComponentNeed

    db.session.add(
        ProductionComponentNeed(
            preplan_id=preplan.id,
            work_order_id=wo_parent.id,
            root_preplan_line_id=None,
            bom_header_id=None,
            bom_line_id=None,
            child_kind="semi",
            child_material_id=semi.id,
            required_qty=Decimal("1"),
            stock_covered_qty=Decimal("0"),
            shortage_qty=Decimal("1"),
        )
    )
    db.session.commit()

    t0 = datetime(2026, 4, 10, 8, 0)
    rows = [
        {"work_order_id": wo_child.id, "es": t0, "ef": t0 + timedelta(hours=2)},
        {
            "work_order_id": wo_parent.id,
            "es": t0 + timedelta(hours=1),
            "ef": t0 + timedelta(hours=3),
        },
    ]
    errs = list_bom_work_order_gate_errors(preplan_id=preplan.id, rows=rows)
    assert len(errs) == 1
    assert "BOM 先后" in errs[0]
