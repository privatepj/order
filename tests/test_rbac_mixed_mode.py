import pytest

from app import create_app, db
from app.auth.capabilities import user_can_cap
from app.auth.rbac_cache import invalidate_rbac_cache
from app.config import Config
from app.models import Role, RoleAllowedCapability, RoleAllowedNav, SysNavItem, User


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


@pytest.fixture()
def app_ctx(app):
    with app.app_context():
        yield


def _create_role(
    *,
    code="warehouse",
    name="Warehouse",
    allowed_menu_keys=None,
    allowed_capability_keys=None,
):
    role = Role(
        name=name,
        code=code,
        allowed_menu_keys=allowed_menu_keys,
        allowed_capability_keys=allowed_capability_keys,
    )
    db.session.add(role)
    db.session.flush()
    return role


def _create_user(role, *, username="warehouse_user"):
    user = User(
        username=username,
        password_hash="pwd",
        role_id=role.id,
        is_active=True,
    )
    db.session.add(user)
    db.session.flush()
    return user


def _login_client(app, user_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return client


def _seed_nav_tree():
    order = SysNavItem(
        code="order",
        title="订单",
        endpoint="main.order_list",
        sort_order=10,
        is_active=True,
        admin_only=False,
        is_assignable=True,
        landing_priority=10,
    )
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
    db.session.add_all([order, warehouse])
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
    db.session.add_all(
        [
            SysNavItem(
                parent_id=warehouse.id,
                code="delivery",
                title="送货",
                endpoint="main.delivery_list",
                sort_order=10,
                is_active=True,
                admin_only=False,
                is_assignable=True,
                landing_priority=20,
            ),
            SysNavItem(
                parent_id=warehouse.id,
                code="express",
                title="快递",
                endpoint="main.express_company_list",
                sort_order=20,
                is_active=True,
                admin_only=False,
                is_assignable=True,
                landing_priority=30,
            ),
            SysNavItem(
                parent_id=warehouse.id,
                code="inventory_query",
                title="库存查询",
                endpoint="main.inventory_stock_query",
                sort_order=30,
                is_active=True,
                admin_only=False,
                is_assignable=True,
                landing_priority=40,
            ),
            inventory_ops,
        ]
    )
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
                code="inventory_ops_semi",
                title="半成品录入",
                endpoint="main.inventory_semi_entry",
                sort_order=20,
                is_active=True,
                admin_only=False,
                is_assignable=True,
                landing_priority=60,
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


def test_legacy_role_expands_inventory_alias_to_material_entry(app_ctx):
    role = _create_role(
        allowed_menu_keys=["order", "inventory"],
        allowed_capability_keys=None,
    )
    db.session.commit()

    assert role.resolved_nav_codes() >= {
        "order",
        "inventory_query",
        "inventory_ops_finished",
        "inventory_ops_semi",
        "inventory_ops_material",
    }


def test_mixed_role_unions_legacy_json_and_new_nav_rows(app_ctx):
    role = _create_role(
        allowed_menu_keys=["order", "inventory_ops_material"],
        allowed_capability_keys=None,
    )
    db.session.add(RoleAllowedNav(role_id=role.id, nav_code="production_preplan"))
    db.session.commit()

    assert role.resolved_nav_codes() == {
        "order",
        "inventory_ops_material",
        "production_preplan",
    }


def test_legacy_default_capabilities_are_not_narrowed_by_partial_new_rows(app_ctx):
    role = _create_role(
        allowed_menu_keys=["inventory_ops_material"],
        allowed_capability_keys=None,
    )
    user = _create_user(role)
    db.session.add(RoleAllowedCapability(role_id=role.id, cap_code="orchestrator.metric.write"))
    db.session.commit()

    assert role.resolved_capability_key_set() is None
    assert user_can_cap(user, "inventory_ops_material.api.products_search") is True
    assert user_can_cap(user, "inventory_ops_material.movement.create") is True


def test_new_style_role_still_uses_new_capability_rows_only(app_ctx):
    role = _create_role(
        code="ops_material",
        name="Ops Material",
        allowed_menu_keys=None,
        allowed_capability_keys=None,
    )
    user = _create_user(role, username="ops_material_user")
    db.session.add(RoleAllowedNav(role_id=role.id, nav_code="inventory_ops_material"))
    db.session.add(
        RoleAllowedCapability(
            role_id=role.id,
            cap_code="inventory_ops_material.movement.list",
        )
    )
    db.session.commit()

    assert role.resolved_capability_key_set() == frozenset(
        {"inventory_ops_material.movement.list"}
    )
    assert user_can_cap(user, "inventory_ops_material.movement.list") is True
    assert user_can_cap(user, "inventory_ops_material.movement.create") is False


def test_warehouse_nav_and_material_entry_survive_mixed_mode_rbac(app):
    with app.app_context():
        _seed_nav_tree()
        role = _create_role(
            allowed_menu_keys=[
                "order",
                "delivery",
                "express",
                "inventory_query",
                "inventory_ops_finished",
                "inventory_ops_semi",
                "inventory_ops_material",
            ],
            allowed_capability_keys=None,
        )
        user = _create_user(role)
        db.session.add(RoleAllowedNav(role_id=role.id, nav_code="semi_material"))
        db.session.add(
            RoleAllowedCapability(role_id=role.id, cap_code="orchestrator.metric.write")
        )
        db.session.commit()
        user_id = user.id
        invalidate_rbac_cache()

    client = _login_client(app, user_id)

    order_page = client.get("/orders")
    order_html = order_page.get_data(as_text=True)

    assert order_page.status_code == 200
    assert "成品录入" in order_html
    assert "半成品录入" in order_html
    assert "材料录入" in order_html

    material_page = client.get("/inventory/material", follow_redirects=True)
    material_html = material_page.get_data(as_text=True)

    assert material_page.status_code == 200
    assert material_page.request.path == "/inventory/movement/new"
    assert "库存录入" in material_html
