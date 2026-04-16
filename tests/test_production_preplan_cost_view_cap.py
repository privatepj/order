"""预生产详情：测算成本展示依赖 production.preplan.cost.view。"""

from datetime import date

import pytest

from app import create_app, db
from app.auth.rbac_cache import invalidate_rbac_cache
from app.config import Config
from app.models import (
    ProductionPreplan,
    Role,
    RoleAllowedCapability,
    RoleAllowedNav,
    SysNavItem,
    User,
)


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


def _seed_preplan_rbac_and_user(*, with_cost_cap: bool):
    nav = SysNavItem(
        code="production_preplan",
        title="预生产计划",
        endpoint="main.production_preplan_list",
        sort_order=10,
        is_active=True,
        admin_only=False,
        is_assignable=True,
        landing_priority=10,
    )
    db.session.add(nav)
    db.session.flush()

    role = Role(name="ProdNoCost", code="prod_no_cost", allowed_menu_keys=None)
    db.session.add(role)
    db.session.flush()
    db.session.add(RoleAllowedNav(role_id=role.id, nav_code="production_preplan"))
    caps = ["production.calc.action.run"]
    if with_cost_cap:
        caps.append("production.preplan.cost.view")
    for c in caps:
        db.session.add(RoleAllowedCapability(role_id=role.id, cap_code=c))

    user = User(username="u1", password_hash="x", role_id=role.id, is_active=True)
    db.session.add(user)
    db.session.flush()

    pre = ProductionPreplan(
        plan_date=date.today(),
        customer_id=0,
        status="draft",
        created_by=int(user.id),
    )
    db.session.add(pre)
    db.session.commit()
    return user, pre


def test_preplan_detail_hides_cost_without_cap(app):
    with app.app_context():
        user, pre = _seed_preplan_rbac_and_user(with_cost_cap=False)
        invalidate_rbac_cache()
        client = _login_client(app, user.id)
        rv = client.get(f"/production/preplans/{pre.id}")
        assert rv.status_code == 200
        html = rv.get_data(as_text=True)
        assert "production.preplan.cost.view" in html
        assert "优化（最小期望）" not in html


def test_preplan_detail_shows_cost_with_cap(app):
    with app.app_context():
        user, pre = _seed_preplan_rbac_and_user(with_cost_cap=True)
        invalidate_rbac_cache()
        client = _login_client(app, user.id)
        rv = client.get(f"/production/preplans/{pre.id}")
        assert rv.status_code == 200
        html = rv.get_data(as_text=True)
        assert "优化（最小期望）" in html
