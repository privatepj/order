import pytest

from app import create_app, db
from app.config import Config
from app.models import Role, User


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
def admin_client(app):
    with app.app_context():
        role = Role(name="Admin", code="admin")
        db.session.add(role)
        db.session.flush()
        user = User(username="admin", password_hash="pwd", role_id=role.id, is_active=True)
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return client


@pytest.mark.parametrize(
    "path",
    [
        "/crm/leads",
        "/crm/opportunities",
        "/crm/tickets",
    ],
)
def test_crm_list_pages_render_ok(app, admin_client, path):
    r = admin_client.get(path)
    assert r.status_code == 200

