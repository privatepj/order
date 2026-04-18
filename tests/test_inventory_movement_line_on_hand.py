"""库存录入行当前结存 API。"""

from decimal import Decimal

import pytest

from app import create_app, db
from app.auth.rbac_cache import invalidate_rbac_cache
from app.config import Config
from app.models import (
    InventoryOpeningBalance,
    Product,
    Role,
    RoleAllowedCapability,
    RoleAllowedNav,
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


def _seed_finished_nav():
    wh = SysNavItem(
        code="nav_wh",
        title="仓",
        endpoint=None,
        sort_order=1,
        is_active=True,
        admin_only=False,
        is_assignable=False,
        landing_priority=None,
    )
    db.session.add(wh)
    db.session.flush()
    inv = SysNavItem(
        parent_id=wh.id,
        code="inventory_ops",
        title="库存录入",
        endpoint=None,
        sort_order=2,
        is_active=True,
        admin_only=False,
        is_assignable=False,
        landing_priority=None,
    )
    db.session.add(inv)
    db.session.flush()
    db.session.add(
        SysNavItem(
            parent_id=inv.id,
            code="inventory_ops_finished",
            title="成品录入",
            endpoint="main.inventory_finished_entry",
            sort_order=1,
            is_active=True,
            admin_only=False,
            is_assignable=True,
            landing_priority=10,
        )
    )


def _user_with_caps(cap_codes):
    role = Role(name="InvOnHand", code="inv_onhand_t", allowed_menu_keys=None)
    db.session.add(role)
    db.session.flush()
    db.session.add(RoleAllowedNav(role_id=role.id, nav_code="inventory_ops_finished"))
    for c in cap_codes:
        db.session.add(RoleAllowedCapability(role_id=role.id, cap_code=c))
    u = User(username="inv_onhand_u", password_hash="x", role_id=role.id, is_active=True)
    db.session.add(u)
    db.session.commit()
    invalidate_rbac_cache()
    return u


def _seed_product_two_openings():
    p = Product(product_code="T-P1", name="测试成品", spec="S", base_unit="pcs")
    db.session.add(p)
    db.session.flush()
    db.session.add_all(
        [
            InventoryOpeningBalance(
                category=inventory_svc.INV_FINISHED,
                product_id=p.id,
                material_id=0,
                storage_area="BIN-A",
                opening_qty=Decimal("20"),
            ),
            InventoryOpeningBalance(
                category=inventory_svc.INV_FINISHED,
                product_id=p.id,
                material_id=0,
                storage_area="BIN-B",
                opening_qty=Decimal("30"),
            ),
        ]
    )
    db.session.commit()
    return p


def test_movement_line_on_hand_aggregate_and_bin(app):
    with app.app_context():
        _seed_finished_nav()
        p = _seed_product_two_openings()
        user = _user_with_caps(
            [
                "inventory_ops_finished.api.movement_line_on_hand",
                "inventory_ops_finished.movement.create",
            ]
        )
        uid = user.id
        pid = p.id

    client = _login_client(app, uid)

    r_all = client.get(f"/api/inventory/movement-line-on-hand?category=finished&item_id={pid}")
    assert r_all.status_code == 200
    j_all = r_all.get_json()
    assert j_all["on_hand"] == "50"
    assert Decimal(j_all["on_hand_value"]) == Decimal("50")

    r_bin = client.get(
        f"/api/inventory/movement-line-on-hand?category=finished&item_id={pid}&storage_area=BIN-A"
    )
    assert r_bin.status_code == 200
    j_bin = r_bin.get_json()
    assert j_bin["on_hand"] == "20"


def test_movement_line_on_hand_forbidden_without_cap(app):
    with app.app_context():
        _seed_finished_nav()
        p = _seed_product_two_openings()
        user = _user_with_caps(
            [
                "inventory_ops_finished.movement.create",
            ]
        )
        uid = user.id
        pid = p.id

    client = _login_client(app, uid)
    r = client.get(f"/api/inventory/movement-line-on-hand?category=finished&item_id={pid}")
    assert r.status_code == 403


def test_movement_line_on_hand_missing_item_returns_dash(app):
    with app.app_context():
        _seed_finished_nav()
        _seed_product_two_openings()
        user = _user_with_caps(
            [
                "inventory_ops_finished.api.movement_line_on_hand",
                "inventory_ops_finished.movement.create",
            ]
        )
        uid = user.id

    client = _login_client(app, uid)
    r = client.get("/api/inventory/movement-line-on-hand?category=finished")
    assert r.status_code == 200
    assert r.get_json() == {"on_hand": "-"}
