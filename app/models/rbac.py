"""菜单与细项能力（库表维护）。"""

from app import db


class SysNavItem(db.Model):
    __tablename__ = "sys_nav_item"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    parent_id = db.Column(db.Integer, nullable=True)
    code = db.Column(db.String(64), nullable=False, unique=True)
    title = db.Column(db.String(128), nullable=False)
    endpoint = db.Column(db.String(128), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    admin_only = db.Column(db.Boolean, nullable=False, default=False)
    is_assignable = db.Column(db.Boolean, nullable=False, default=True)
    landing_priority = db.Column(db.Integer, nullable=True)

class SysCapability(db.Model):
    __tablename__ = "sys_capability"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(128), nullable=False, unique=True)
    title = db.Column(db.String(255), nullable=False)
    nav_item_code = db.Column(db.String(64), nullable=False)
    group_label = db.Column(db.String(128), nullable=False, server_default="")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class RoleAllowedNav(db.Model):
    __tablename__ = "role_allowed_nav"

    role_id = db.Column(db.Integer, primary_key=True)
    nav_code = db.Column(db.String(64), primary_key=True)


class RoleAllowedCapability(db.Model):
    __tablename__ = "role_allowed_capability"

    role_id = db.Column(db.Integer, primary_key=True)
    cap_code = db.Column(db.String(128), primary_key=True)
