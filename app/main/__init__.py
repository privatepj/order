from flask import Blueprint, redirect, url_for, render_template
from flask_login import current_user, login_required

from app.auth.menus import first_landing_url
from app.main.routes_customer import register_customer_routes
from app.main.routes_order import register_order_routes
from app.main.routes_delivery import register_delivery_routes
from app.main.routes_reconciliation import register_reconciliation_routes
from app.main.routes_customer_product import register_customer_product_routes
from app.main.routes_product import register_product_routes
from app.main.routes_company import register_company_routes
from app.main.routes_express import register_express_routes
from app.main.routes_user import register_user_routes
from app.main.routes_role import register_role_routes
from app.main.routes_audit import register_audit_routes
from app.main.routes_inventory import register_inventory_routes
from app.main.routes_rbac_admin import register_rbac_admin_routes

bp = Blueprint("main", __name__)
register_customer_routes(bp)
register_company_routes(bp)
register_user_routes(bp)
register_express_routes(bp)
register_order_routes(bp)
register_delivery_routes(bp)
register_reconciliation_routes(bp)
register_customer_product_routes(bp)
register_product_routes(bp)
register_role_routes(bp)
register_audit_routes(bp)
register_inventory_routes(bp)
register_rbac_admin_routes(bp)


@bp.route("/")
def index():
    if current_user.is_authenticated:
        if getattr(current_user, "role_code", None) == "pending":
            return redirect(url_for("main.wait_role"))
        return redirect(first_landing_url())
    return redirect(url_for("auth.login"))


@bp.route("/no-menu-access")
@login_required
def no_menu_access():
    if getattr(current_user, "role_code", None) == "pending":
        return redirect(url_for("main.wait_role"))
    from app.auth.menus import first_landing_url, user_has_any_menu

    if user_has_any_menu():
        return redirect(first_landing_url())
    return render_template("main/no_menu_access.html")


@bp.route("/wait-role")
@login_required
def wait_role():
    if getattr(current_user, "role_code", None) != "pending":
        return redirect(url_for("main.index"))
    return render_template("main/wait_role.html")
