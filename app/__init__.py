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

    from app.models import User

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

    @app.context_processor
    def inject_menu_permissions():
        from app.auth.menus import current_user_can_menu

        return dict(user_can_menu=current_user_can_menu)

    return app
