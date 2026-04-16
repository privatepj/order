from datetime import date
from decimal import Decimal

import pytest

from app import create_app, db
from app.auth.rbac_cache import invalidate_rbac_cache
from app.config import Config
from app.models import (
    InventoryMovement,
    InventoryMovementBatch,
    Product,
    Role,
    RoleAllowedCapability,
    RoleAllowedNav,
    SemiMaterial,
    SysNavItem,
    User,
)
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


def _login_client(app, user_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return client


def _seed_inventory_nav_tree():
    warehouse = SysNavItem(
        code="nav_warehouse",
        title="仓管",
        endpoint=None,
        sort_order=20,
        is_active=True,
        admin_only=False,
        is_assignable=False,
        landing_priority=None,
    )
    db.session.add(warehouse)
    db.session.flush()

    inventory_ops = SysNavItem(
        parent_id=warehouse.id,
        code="inventory_ops",
        title="库存录入",
        endpoint=None,
        sort_order=40,
        is_active=True,
        admin_only=False,
        is_assignable=False,
        landing_priority=None,
    )
    db.session.add(inventory_ops)
    db.session.flush()

    db.session.add_all(
        [
            SysNavItem(
                parent_id=inventory_ops.id,
                code="inventory_ops_finished",
                title="成品录入",
                endpoint="main.inventory_finished_entry",
                sort_order=10,
                is_active=True,
                admin_only=False,
                is_assignable=True,
                landing_priority=50,
            ),
            SysNavItem(
                parent_id=inventory_ops.id,
                code="inventory_ops_material",
                title="材料录入",
                endpoint="main.inventory_material_entry",
                sort_order=30,
                is_active=True,
                admin_only=False,
                is_assignable=True,
                landing_priority=70,
            ),
        ]
    )


def _create_user_with_inventory_access(*, nav_codes, cap_codes):
    role = Role(name="InventoryQueryRole", code="inventory_query_role", allowed_menu_keys=None)
    db.session.add(role)
    db.session.flush()
    for nav_code in nav_codes:
        db.session.add(RoleAllowedNav(role_id=role.id, nav_code=nav_code))
    for cap_code in cap_codes:
        db.session.add(RoleAllowedCapability(role_id=role.id, cap_code=cap_code))
    user = User(username="inventory_user", password_hash="x", role_id=role.id, is_active=True)
    db.session.add(user)
    db.session.commit()
    invalidate_rbac_cache()
    return user


def _seed_inventory_movements():
    finished = Product(product_code="P-FG-001", name="成品A", spec="10kg", base_unit="kg")
    material = SemiMaterial(
        kind="material",
        code="M-RM-001",
        name="材料B",
        spec="卷材",
        base_unit="kg",
    )
    db.session.add_all([finished, material])
    db.session.flush()

    finished_batch = InventoryMovementBatch(
        category=inventory_svc.INV_FINISHED,
        biz_date=date(2026, 4, 14),
        direction="in",
        source="form",
        line_count=2,
        created_by=1,
    )
    material_batch = InventoryMovementBatch(
        category=inventory_svc.INV_MATERIAL,
        biz_date=date(2026, 4, 15),
        direction="out",
        source="form",
        line_count=1,
        created_by=1,
    )
    db.session.add_all([finished_batch, material_batch])
    db.session.flush()

    db.session.add_all(
        [
            InventoryMovement(
                category=inventory_svc.INV_FINISHED,
                direction="in",
                product_id=finished.id,
                material_id=0,
                storage_area="A1",
                quantity=Decimal("8"),
                unit="kg",
                biz_date=date(2026, 4, 14),
                source_type=inventory_svc.SOURCE_MANUAL,
                remark="首次入库",
                created_by=1,
                movement_batch_id=finished_batch.id,
            ),
            InventoryMovement(
                category=inventory_svc.INV_FINISHED,
                direction="out",
                product_id=finished.id,
                material_id=0,
                storage_area="A1",
                quantity=Decimal("3"),
                unit="kg",
                biz_date=date(2026, 4, 15),
                source_type=inventory_svc.SOURCE_MANUAL,
                remark="领料出库",
                created_by=1,
                movement_batch_id=finished_batch.id,
            ),
            InventoryMovement(
                category=inventory_svc.INV_MATERIAL,
                direction="out",
                product_id=0,
                material_id=material.id,
                storage_area="B2",
                quantity=Decimal("5"),
                unit="kg",
                biz_date=date(2026, 4, 15),
                source_type=inventory_svc.SOURCE_MANUAL,
                remark="材料出库",
                created_by=1,
                movement_batch_id=material_batch.id,
            ),
        ]
    )
    db.session.commit()
    return finished, material


def test_inventory_movement_query_requires_matching_list_cap(app):
    with app.app_context():
        _seed_inventory_nav_tree()
        _seed_inventory_movements()
        user = _create_user_with_inventory_access(
            nav_codes=["inventory_ops_finished", "inventory_ops_material"],
            cap_codes=["inventory_ops_finished.movement.list"],
        )
        user_id = user.id

    client = _login_client(app, user_id)

    allowed = client.get(
        "/inventory/movement/query?category=finished&preset=custom&start_date=2026-04-14&end_date=2026-04-15"
    )
    forbidden = client.get(
        "/inventory/movement/query?category=material&preset=custom&start_date=2026-04-14&end_date=2026-04-15"
    )

    assert allowed.status_code == 200
    assert forbidden.status_code == 403


def test_inventory_movement_query_page_shows_filtered_rows_and_entry_link(app):
    with app.app_context():
        _seed_inventory_nav_tree()
        _seed_inventory_movements()
        user = _create_user_with_inventory_access(
            nav_codes=["inventory_ops_finished"],
            cap_codes=[
                "inventory_ops_finished.movement.list",
                "inventory_ops_finished.movement.export",
            ],
        )
        user_id = user.id

    client = _login_client(app, user_id)

    list_page = client.get("/inventory/finished", follow_redirects=True)
    list_html = list_page.get_data(as_text=True)
    assert list_page.status_code == 200
    assert "在线查询明细" in list_html
    assert "导出进出明细" not in list_html

    query_page = client.get(
        "/inventory/movement/query?category=finished&preset=custom&start_date=2026-04-14&end_date=2026-04-15&name_spec=P-FG-001"
    )
    html = query_page.get_data(as_text=True)

    assert query_page.status_code == 200
    assert "成品A" in html
    assert "材料B" not in html
    assert "批次详情" in html
    assert "导出当前结果" in html


def test_inventory_movement_query_uses_same_filter_scope_as_export(app):
    with app.app_context():
        _seed_inventory_nav_tree()
        finished, _material = _seed_inventory_movements()

        paged_rows, total = inventory_svc.query_movement_rows_paginated(
            categories=[inventory_svc.INV_FINISHED],
            start_date=date(2026, 4, 14),
            end_date=date(2026, 4, 15),
            category=inventory_svc.INV_FINISHED,
            direction="out",
            storage_area_kw="A1",
            name_spec_kw=finished.product_code,
            page=1,
            per_page=30,
        )
        export_rows, exceeded = inventory_svc.query_movement_export_rows(
            categories=[inventory_svc.INV_FINISHED],
            start_date=date(2026, 4, 14),
            end_date=date(2026, 4, 15),
            category=inventory_svc.INV_FINISHED,
            direction="out",
            storage_area_kw="A1",
            name_spec_kw=finished.product_code,
            limit=50000,
        )

        assert exceeded is False
        assert total == 1
        assert len(paged_rows) == len(export_rows) == 1
        assert paged_rows[0]["movement_id"] == export_rows[0]["movement_id"]
        assert paged_rows[0]["item_name"] == export_rows[0]["item_name"] == "成品A"
