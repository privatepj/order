from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

from app.config import Config

db = SQLAlchemy()
login_manager = LoginManager()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "请先登录。"

    from app.models import User, UserApiToken  # noqa: F401 — 注册 ORM 映射
    from app.models import rbac  # noqa: F401 — sys_nav_item 等表
    from app.models import hr  # noqa: F401 — HR 表
    from app.models import machine  # noqa: F401 — 机台管理表

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.auth.routes import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.openclaw import bp as openclaw_bp
    app.register_blueprint(openclaw_bp)

    from app.audit import register_audit_hooks

    register_audit_hooks(app)

    from app.cli_commands import register_cli

    register_cli(app)

    from app.utils.qty_display import format_qty_plain

    app.jinja_env.filters["qty_plain"] = format_qty_plain

    @app.context_processor
    def inject_menu_permissions():
        from flask_login import current_user

        from app.auth.capabilities import current_user_can_cap
        from app.auth.menus import current_user_can_menu, nav_tree_for_user

        nav = []
        if current_user.is_authenticated and getattr(current_user, "role_code", None) not in (
            None,
            "pending",
        ):
            try:
                nav = nav_tree_for_user()
            except Exception:
                nav = []
        return dict(
            user_can_menu=current_user_can_menu,
            user_can_cap=current_user_can_cap,
            nav_tree=nav,
        )

    return app
