import re

from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required

from app import db
from app.auth.decorators import menu_required
from app.auth.menus import MENU_LABEL, menu_keys_for_role_edit, sanitize_menu_keys_for_role
from app.models import Role, User


def _code_ok(code: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9_]{0,29}", (code or "").strip()))


def register_role_routes(bp):
    @bp.route("/roles")
    @login_required
    @menu_required("user_mgmt")
    def role_list():
        roles = Role.query.order_by(Role.code).all()
        return render_template("role/list.html", roles=roles, menu_labels=MENU_LABEL)

    @bp.route("/roles/new", methods=["GET", "POST"])
    @login_required
    @menu_required("user_mgmt")
    def role_new():
        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            code = (request.form.get("code") or "").strip().lower()
            description = (request.form.get("description") or "").strip() or None
            keys = request.form.getlist("menu_keys")
            if not name:
                flash("角色名称为必填。", "danger")
                return render_template(
                    "role/form.html",
                    role=None,
                    menu_choices=menu_keys_for_role_edit(None),
                    selected_keys=keys,
                )
            if not _code_ok(code):
                flash("角色代码须为小写字母开头，仅含小写字母、数字、下划线，最长 30 字符。", "danger")
                return render_template(
                    "role/form.html",
                    role=None,
                    menu_choices=menu_keys_for_role_edit(None),
                    selected_keys=keys,
                )
            if Role.query.filter_by(code=code).first():
                flash("该角色代码已存在。", "danger")
                return render_template(
                    "role/form.html",
                    role=None,
                    menu_choices=menu_keys_for_role_edit(None),
                    selected_keys=keys,
                )
            if code in ("admin", "pending"):
                flash("不能使用保留角色代码 admin / pending。", "danger")
                return render_template(
                    "role/form.html",
                    role=None,
                    menu_choices=menu_keys_for_role_edit(None),
                    selected_keys=keys,
                )
            clean_keys = sanitize_menu_keys_for_role(code, keys)
            r = Role(
                name=name,
                code=code,
                description=description,
                allowed_menu_keys=clean_keys,
            )
            db.session.add(r)
            db.session.commit()
            flash("角色已创建。", "success")
            return redirect(url_for("main.role_list"))

        return render_template(
            "role/form.html",
            role=None,
            menu_choices=menu_keys_for_role_edit(None),
            selected_keys=[],
        )

    @bp.route("/roles/<int:role_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("user_mgmt")
    def role_edit(role_id):
        role = Role.query.get_or_404(role_id)
        if request.method == "POST":
            if role.code in ("admin", "pending"):
                flash("系统内置角色不可在此修改。", "danger")
                return redirect(url_for("main.role_list"))
            name = (request.form.get("name") or "").strip()
            description = (request.form.get("description") or "").strip() or None
            keys = request.form.getlist("menu_keys")
            if not name:
                flash("角色名称为必填。", "danger")
                return render_template(
                    "role/form.html",
                    role=role,
                    menu_choices=menu_keys_for_role_edit(role.code),
                    selected_keys=keys,
                )
            clean_keys = sanitize_menu_keys_for_role(role.code, keys)
            role.name = name
            role.description = description
            role.allowed_menu_keys = clean_keys
            db.session.add(role)
            db.session.commit()
            flash("角色已保存。", "success")
            return redirect(url_for("main.role_list"))

        selected = list(role.parsed_menu_key_set()) if role.code != "admin" else []
        return render_template(
            "role/form.html",
            role=role,
            menu_choices=menu_keys_for_role_edit(role.code),
            selected_keys=selected,
        )

    @bp.route("/roles/<int:role_id>/delete", methods=["POST"])
    @login_required
    @menu_required("user_mgmt")
    def role_delete(role_id):
        role = Role.query.get_or_404(role_id)
        if role.code in ("admin", "pending"):
            flash("系统内置角色不可删除。", "danger")
            return redirect(url_for("main.role_list"))
        n = User.query.filter(
            (User.role_id == role.id) | (User.requested_role_id == role.id)
        ).count()
        if n:
            flash("仍有用户关联该角色，无法删除。", "danger")
            return redirect(url_for("main.role_list"))
        db.session.delete(role)
        db.session.commit()
        flash("角色已删除。", "success")
        return redirect(url_for("main.role_list"))
