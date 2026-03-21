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
