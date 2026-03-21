from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user

from app.auth.menus import current_user_can_menu, first_landing_url


def role_required(*role_codes):
    """要求用户已登录且角色在 role_codes 中。"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role_code not in role_codes:
                flash("您没有权限访问该页面。", "danger")
                return redirect(url_for("main.index"))
            return f(*args, **kwargs)
        return wrapped
    return decorator


def menu_required(*menu_keys):
    """已登录；pending 仅可去等待页；admin 全放行；其余角色需具备任一 menu key。"""
    if not menu_keys:
        raise ValueError("menu_required 至少需要一个 menu key")

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            code = getattr(current_user, "role_code", None)
            if code == "pending":
                flash("请等待管理员分配角色后再访问。", "warning")
                return redirect(url_for("main.wait_role"))
            if code == "admin":
                return f(*args, **kwargs)
            if any(current_user_can_menu(k) for k in menu_keys):
                return f(*args, **kwargs)
            flash("您没有权限访问该页面。", "danger")
            return redirect(first_landing_url())
        return wrapped
    return decorator
