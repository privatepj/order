from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, current_user

from app import db
from app.auth.menus import role_assignable_for_registration
from app.models import User, Role


def _registration_roles():
    return [
        r
        for r in Role.query.order_by(Role.code).all()
        if role_assignable_for_registration(r)
    ]

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or not password:
            flash("请输入用户名和密码。", "danger")
            return render_template("auth/login.html")
        user = User.query.filter_by(username=username, is_active=True).first()
        if user and user.check_password(password):
            login_user(user)
            next_url = request.args.get("next") or url_for("main.index")
            return redirect(next_url)
        flash("用户名或密码错误。", "danger")
    return render_template("auth/login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        name = (request.form.get("name") or "").strip()
        requested_role_id = request.form.get("requested_role_id", type=int)

        if not username or not password:
            flash("请输入用户名和密码。", "danger")
            roles = _registration_roles()
            return render_template("auth/register.html", roles=roles)
        if User.query.filter_by(username=username).first():
            flash("该用户名已被使用。", "danger")
            roles = _registration_roles()
            return render_template("auth/register.html", roles=roles)
        if requested_role_id is None:
            flash("请选择申请的角色。", "danger")
            roles = _registration_roles()
            return render_template("auth/register.html", roles=roles)

        requested_role = Role.query.get(requested_role_id)
        if not requested_role or not role_assignable_for_registration(requested_role):
            flash("所选角色无效，请重新选择。", "danger")
            roles = _registration_roles()
            return render_template("auth/register.html", roles=roles)

        pending_role = Role.query.filter_by(code="pending").first()
        if not pending_role:
            flash("系统未配置待分配角色，请联系管理员。", "danger")
            roles = _registration_roles()
            return render_template("auth/register.html", roles=roles)

        user = User(
            username=username,
            name=name or None,
            role_id=pending_role.id,
            requested_role_id=requested_role.id,
            is_active=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("注册成功，请登录。管理员审批通过后即可按申请角色使用系统。", "success")
        return redirect(url_for("auth.login"))

    roles = _registration_roles()
    return render_template("auth/register.html", roles=roles)


@bp.route("/logout")
def logout():
    logout_user()
    flash("已退出登录。", "info")
    return redirect(url_for("auth.login"))
