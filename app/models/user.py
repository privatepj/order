import json

from app import db
from flask_login import UserMixin


class Role(db.Model):
    __tablename__ = "role"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64), nullable=False)
    code = db.Column(db.String(32), nullable=False, unique=True)
    description = db.Column(db.String(255))
    allowed_menu_keys = db.Column(db.JSON, nullable=True)
    allowed_capability_keys = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def parsed_menu_key_set(self):
        """非 admin：返回已允许的 menu key 集合；admin/pending 由调用方按 code 处理。"""
        raw = self.allowed_menu_keys
        if raw is None:
            return frozenset()
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                return frozenset()
        if not isinstance(raw, list):
            return frozenset()
        return frozenset(str(x) for x in raw if x is not None)

    def parsed_capability_key_set(self):
        """
        None：未配置细项，在已授权菜单内视为具备全部已注册能力。
        frozenset：显式白名单。
        空数组与 NULL 相同（菜单内默认全开），便于兼容旧数据。
        """
        raw = self.allowed_capability_keys
        if raw is None:
            return None
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                return None
        if not isinstance(raw, list):
            return None
        if len(raw) == 0:
            return None
        return frozenset(str(x) for x in raw if x is not None)

    def resolved_nav_codes(self):
        """优先 role_allowed_nav；无记录时从 allowed_menu_keys 兼容（含 inventory/report_export 展开）。"""
        from app.models.rbac import RoleAllowedNav

        rows = RoleAllowedNav.query.filter_by(role_id=self.id).all()
        if rows:
            codes = {r.nav_code for r in rows}
            # 迁移前仅有叶子 production；现为分组 + production_preplan / production_incident
            if "production" in codes:
                codes.discard("production")
                codes.add("production_preplan")
                codes.add("production_incident")
            return frozenset(codes)
        raw = self.parsed_menu_key_set()
        if not raw:
            return frozenset()
        out = set()
        for k in raw:
            if k == "inventory":
                out.add("inventory_query")
                out.add("inventory_ops_finished")
                out.add("inventory_ops_semi")
                out.add("inventory_ops_material")
            elif k == "report_export":
                out.add("report_notes")
                out.add("report_records")
            elif k == "production":
                out.add("production_preplan")
                out.add("production_incident")
            else:
                out.add(k)
        return frozenset(out)

    def resolved_capability_key_set(self):
        """优先 role_allowed_capability；无记录时用 allowed_capability_keys JSON。"""
        from app.models.rbac import RoleAllowedCapability

        rows = RoleAllowedCapability.query.filter_by(role_id=self.id).all()
        if rows:
            return frozenset(r.cap_code for r in rows)
        return self.parsed_capability_key_set()

    # 不使用数据库外键，用 primaryjoin + foreign() 标注引用列
    users = db.relationship(
        "User",
        primaryjoin="foreign(User.role_id) == Role.id",
        backref=db.backref("role", lazy=True),
        lazy=True,
    )


class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(64), nullable=False, unique=True)
    # 这里直接以明文方式存储密码（按你的要求，注意仅适合内部测试环境）
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(64))
    role_id = db.Column(db.Integer, nullable=False)  # 关联 role.id，不在库建外键
    # 用户在注册时申请的目标角色（例如销售、仓管、财务等），审批通过前处于 pending 角色
    requested_role_id = db.Column(db.Integer, nullable=True)  # 关联 role.id，不在库建外键
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    requested_role = db.relationship(
        "Role", primaryjoin="foreign(User.requested_role_id) == Role.id", lazy=True
    )

    def set_password(self, password: str) -> None:
        # 按要求：不加密，直接保存明文
        self.password_hash = password

    def check_password(self, password: str) -> bool:
        # 直接字符串比较
        return self.password_hash == password

    @property
    def role_code(self):
        return self.role.code if self.role else None

    @property
    def is_pending_approval(self) -> bool:
        """当前用户是否处于“待审批”状态：角色为 pending 且已选择申请角色。"""
        return self.role_code == "pending" and self.requested_role_id is not None
