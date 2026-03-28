from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required

from app import db
from app.models import User, Role
from app.auth.decorators import capability_required, menu_required


def register_user_routes(bp):
    @bp.route("/users")
    @login_required
    @menu_required("user_mgmt")
    def user_list():
        users = User.query.join(Role, User.role_id == Role.id).order_by(User.id).all()
        return render_template("user/list.html", users=users)

    @bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("user_mgmt")
    @capability_required("user_mgmt.action.edit")
    def user_edit(user_id):
        user = User.query.get_or_404(user_id)
        roles = Role.query.order_by(Role.code).all()
        requested_role = None
        if getattr(user, "requested_role_id", None):
            requested_role = Role.query.get(user.requested_role_id)
        if request.method == "POST":
            action = request.form.get("action") or "save"
            is_active = request.form.get("is_active") == "1"
            name = (request.form.get("name") or "").strip()

            # 待审批用户的“审批通过/驳回”逻辑
            if action in {"approve", "reject"} and user.is_pending_approval:
                if action == "approve":
                    # 审批通过：将实际角色切换为申请角色
                    if requested_role is None:
                        flash("申请角色不存在或已被删除，请先为该用户手动分配角色。", "danger")
                        return render_template("user/edit.html", user=user, roles=roles, requested_role=requested_role)
                    user.role_id = requested_role.id
                    # 可按需要保留申请记录，这里清空以简化状态
                    user.requested_role_id = None
                    user.is_active = is_active
                    user.name = name or None
                    db.session.commit()
                    flash("审批通过，已为该用户分配角色。", "success")
                else:
                    # 驳回：保留 pending 角色，清空申请角色，可选地禁用账号
                    user.requested_role_id = None
                    user.is_active = is_active
                    user.name = name or None
                    db.session.commit()
                    flash("已驳回该用户的角色申请。", "info")
                return redirect(url_for("main.user_list"))

            # 普通编辑逻辑：修改角色与状态
            role_id = request.form.get("role_id", type=int)
            if role_id is None:
                flash("请选择角色。", "danger")
                return render_template("user/edit.html", user=user, roles=roles, requested_role=requested_role)
            role = Role.query.get(role_id)
            if not role:
                flash("所选角色无效。", "danger")
                return render_template("user/edit.html", user=user, roles=roles, requested_role=requested_role)
            user.role_id = role_id
            user.is_active = is_active
            user.name = name or None
            db.session.commit()
            flash("用户已更新。", "success")
            return redirect(url_for("main.user_list"))
        return render_template("user/edit.html", user=user, roles=roles, requested_role=requested_role)
