from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.auth.decorators import capability_required, menu_required
from app.auth.rbac_cache import invalidate_rbac_cache
from app.models.rbac import SysCapability, SysNavItem


def register_rbac_admin_routes(bp):
    @bp.route("/system/nav-items")
    @login_required
    @menu_required("role_mgmt")
    @capability_required("role_mgmt.action.edit")
    def sys_nav_list():
        rows = SysNavItem.query.order_by(
            SysNavItem.parent_id.asc(),
            SysNavItem.sort_order.asc(),
            SysNavItem.id.asc(),
        ).all()
        return render_template("rbac/nav_list.html", rows=rows)

    @bp.route("/system/nav-items/<int:item_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("role_mgmt")
    @capability_required("role_mgmt.action.edit")
    def sys_nav_edit(item_id):
        row = SysNavItem.query.get_or_404(item_id)
        if request.method == "POST":
            row.title = (request.form.get("title") or "").strip() or row.title
            row.sort_order = request.form.get("sort_order", type=int) or 0
            row.is_active = request.form.get("is_active") == "1"
            row.admin_only = request.form.get("admin_only") == "1"
            db.session.add(row)
            db.session.commit()
            invalidate_rbac_cache()
            flash("菜单项已保存。", "success")
            return redirect(url_for("main.sys_nav_list"))
        return render_template("rbac/nav_edit.html", row=row)

    @bp.route("/system/capabilities")
    @login_required
    @menu_required("role_mgmt")
    @capability_required("role_mgmt.action.edit")
    def sys_cap_list():
        # 库表若被 SQL 直接变更，须刷新进程内缓存，否则角色页细项列表仍为旧数据
        invalidate_rbac_cache()
        rows = SysCapability.query.order_by(
            SysCapability.nav_item_code.asc(),
            SysCapability.sort_order.asc(),
            SysCapability.id.asc(),
        ).all()
        return render_template("rbac/cap_list.html", rows=rows)

    @bp.route("/system/capabilities/<int:cap_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("role_mgmt")
    @capability_required("role_mgmt.action.edit")
    def sys_cap_edit(cap_id):
        row = SysCapability.query.get_or_404(cap_id)
        nav_leaves = (
            SysNavItem.query.filter_by(is_active=True, is_assignable=True)
            .order_by(SysNavItem.sort_order.asc(), SysNavItem.id.asc())
            .all()
        )
        if request.method == "POST":
            row.title = (request.form.get("title") or "").strip() or row.title
            row.group_label = (request.form.get("group_label") or "").strip()
            row.sort_order = request.form.get("sort_order", type=int) or 0
            row.is_active = request.form.get("is_active") == "1"
            nc = (request.form.get("nav_item_code") or "").strip()
            if nc and SysNavItem.query.filter_by(code=nc, is_assignable=True).first():
                row.nav_item_code = nc
            db.session.add(row)
            db.session.commit()
            invalidate_rbac_cache()
            flash("能力项已保存。", "success")
            return redirect(url_for("main.sys_cap_list"))
        return render_template("rbac/cap_edit.html", row=row, nav_leaves=nav_leaves)
