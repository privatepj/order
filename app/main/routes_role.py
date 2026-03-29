import re
from typing import List, Optional

from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required

from app import db
from app.auth.capabilities import capability_groups_for_menus, sanitize_capability_keys_for_role
from app.auth.decorators import capability_required, menu_required
from app.auth.menus import get_menu_label_map, menu_keys_for_role_edit, sanitize_menu_keys_for_role
from app.auth.rbac_cache import invalidate_rbac_cache
from app.models import Role, User
from app.models.rbac import RoleAllowedCapability, RoleAllowedNav


def _code_ok(code: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9_]{0,29}", (code or "").strip()))


def _persist_nav(role_id: int, nav_codes: list) -> None:
    RoleAllowedNav.query.filter_by(role_id=role_id).delete()
    for c in nav_codes:
        db.session.add(RoleAllowedNav(role_id=role_id, nav_code=c))


def _persist_capabilities(role_id: int, cap_mode: str, clean_caps: Optional[List[str]]) -> None:
    RoleAllowedCapability.query.filter_by(role_id=role_id).delete()
    if cap_mode == "custom" and clean_caps:
        for c in clean_caps:
            db.session.add(RoleAllowedCapability(role_id=role_id, cap_code=c))


def _role_form_kwargs(role, selected_menu_keys, capability_use_default, selected_capability_keys):
    code = role.code if role else None
    return dict(
        role=role,
        menu_choices=menu_keys_for_role_edit(code),
        selected_keys=selected_menu_keys,
        capability_groups=capability_groups_for_menus(selected_menu_keys if selected_menu_keys else None),
        capability_use_default=capability_use_default,
        selected_capability_keys=selected_capability_keys,
    )


def _apply_capability_from_form(role_code: str, clean_menu_keys: list):
    cap_mode = (request.form.get("capability_mode") or "default").strip()
    menu_set = frozenset(clean_menu_keys)
    if cap_mode == "custom":
        raw_caps = request.form.getlist("capability_keys")
        clean_caps = sanitize_capability_keys_for_role(role_code, raw_caps, menu_set)
        if not clean_caps:
            return None, "自定义细项时请至少勾选一项，或改回「与菜单默认一致」。"
        return clean_caps, None
    return None, None


def register_role_routes(bp):
    @bp.route("/roles")
    @login_required
    @menu_required("role_mgmt")
    def role_list():
        roles = Role.query.order_by(Role.code).all()
        return render_template("role/list.html", roles=roles, menu_labels=get_menu_label_map())

    @bp.route("/roles/new", methods=["GET", "POST"])
    @login_required
    @menu_required("role_mgmt")
    @capability_required("role_mgmt.action.create")
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
                    **_role_form_kwargs(
                        None,
                        keys,
                        (request.form.get("capability_mode") or "default").strip() != "custom",
                        request.form.getlist("capability_keys"),
                    ),
                )
            if not _code_ok(code):
                flash("角色代码须为小写字母开头，仅含小写字母、数字、下划线，最长 30 字符。", "danger")
                return render_template(
                    "role/form.html",
                    **_role_form_kwargs(
                        None,
                        keys,
                        (request.form.get("capability_mode") or "default").strip() != "custom",
                        request.form.getlist("capability_keys"),
                    ),
                )
            if Role.query.filter_by(code=code).first():
                flash("该角色代码已存在。", "danger")
                return render_template(
                    "role/form.html",
                    **_role_form_kwargs(
                        None,
                        keys,
                        (request.form.get("capability_mode") or "default").strip() != "custom",
                        request.form.getlist("capability_keys"),
                    ),
                )
            if code in ("admin", "pending"):
                flash("不能使用保留角色代码 admin / pending。", "danger")
                return render_template(
                    "role/form.html",
                    **_role_form_kwargs(
                        None,
                        keys,
                        (request.form.get("capability_mode") or "default").strip() != "custom",
                        request.form.getlist("capability_keys"),
                    ),
                )
            clean_keys = sanitize_menu_keys_for_role(code, keys)
            cap_payload, cap_err = _apply_capability_from_form(code, clean_keys)
            if cap_err:
                flash(cap_err, "danger")
                return render_template(
                    "role/form.html",
                    **_role_form_kwargs(
                        None,
                        clean_keys,
                        (request.form.get("capability_mode") or "default").strip() == "custom",
                        request.form.getlist("capability_keys"),
                    ),
                )
            cap_mode = (request.form.get("capability_mode") or "default").strip()
            r = Role(
                name=name,
                code=code,
                description=description,
                allowed_menu_keys=None,
                allowed_capability_keys=None,
            )
            db.session.add(r)
            db.session.flush()
            _persist_nav(r.id, clean_keys)
            _persist_capabilities(r.id, cap_mode, cap_payload)
            db.session.commit()
            invalidate_rbac_cache()
            flash("角色已创建。", "success")
            return redirect(url_for("main.role_list"))

        invalidate_rbac_cache()
        return render_template(
            "role/form.html",
            **_role_form_kwargs(None, [], True, []),
        )

    @bp.route("/roles/<int:role_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("role_mgmt")
    @capability_required("role_mgmt.action.edit")
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
                    **_role_form_kwargs(
                        role,
                        keys,
                        (request.form.get("capability_mode") or "default").strip() != "custom",
                        request.form.getlist("capability_keys"),
                    ),
                )
            clean_keys = sanitize_menu_keys_for_role(role.code, keys)
            cap_payload, cap_err = _apply_capability_from_form(role.code, clean_keys)
            if cap_err:
                flash(cap_err, "danger")
                return render_template(
                    "role/form.html",
                    **_role_form_kwargs(
                        role,
                        clean_keys,
                        (request.form.get("capability_mode") or "default").strip() == "custom",
                        request.form.getlist("capability_keys"),
                    ),
                )
            cap_mode = (request.form.get("capability_mode") or "default").strip()
            role.name = name
            role.description = description
            role.allowed_menu_keys = None
            role.allowed_capability_keys = None
            _persist_nav(role.id, clean_keys)
            _persist_capabilities(role.id, cap_mode, cap_payload)
            db.session.add(role)
            db.session.commit()
            invalidate_rbac_cache()
            flash("角色已保存。", "success")
            return redirect(url_for("main.role_list"))

        invalidate_rbac_cache()
        selected = list(role.resolved_nav_codes()) if role.code != "admin" else []
        from app.auth.capabilities import role_capability_form_defaults

        cap_def, cap_sel = role_capability_form_defaults(role)
        return render_template(
            "role/form.html",
            **_role_form_kwargs(role, selected, cap_def, cap_sel),
        )

    @bp.route("/roles/<int:role_id>/delete", methods=["POST"])
    @login_required
    @menu_required("role_mgmt")
    @capability_required("role_mgmt.action.delete")
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
        RoleAllowedNav.query.filter_by(role_id=role.id).delete()
        RoleAllowedCapability.query.filter_by(role_id=role.id).delete()
        db.session.delete(role)
        db.session.commit()
        invalidate_rbac_cache()
        flash("角色已删除。", "success")
        return redirect(url_for("main.role_list"))
