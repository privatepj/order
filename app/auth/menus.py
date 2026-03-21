"""菜单 key 注册表与权限判断（与 role.allowed_menu_keys 对应）。"""

from __future__ import annotations

from typing import Optional

from flask import url_for
from flask_login import current_user

# (key, 展示名称)
MENU_ITEMS = (
    ("order", "订单"),
    ("delivery", "送货"),
    ("customer", "客户"),
    ("product", "产品"),
    ("customer_product", "客户产品"),
    ("reconciliation", "对账导出"),
    ("report_export", "报表导出"),
    ("company", "公司主体"),
    ("express", "快递"),
    ("inventory", "库存录入"),
    ("user_mgmt", "用户管理"),
)

MENU_LABEL = {k: v for k, v in MENU_ITEMS}
ALL_MENU_KEYS = frozenset(MENU_LABEL.keys())
ADMIN_ONLY_MENU_KEYS = frozenset({"company", "user_mgmt"})

# 登录后默认落地页：按顺序取第一个有权限的菜单
LANDING_MENU_ORDER = (
    "order",
    "delivery",
    "customer",
    "product",
    "customer_product",
    "reconciliation",
    "report_export",
    "company",
    "express",
    "inventory",
    "user_mgmt",
)

_MENU_ENDPOINT = {
    "order": "main.order_list",
    "delivery": "main.delivery_list",
    "customer": "main.customer_list",
    "product": "main.product_list",
    "customer_product": "main.customer_product_list",
    "reconciliation": "main.reconciliation_export",
    "report_export": "main.report_export_delivery_notes",
    "company": "main.company_list",
    "express": "main.express_company_list",
    "inventory": "main.inventory_list",
    "user_mgmt": "main.user_list",
}

NO_MENU_ACCESS_ENDPOINT = "main.no_menu_access"


def menu_keys_for_role_edit(role_code: Optional[str]):
    """编辑角色时可选的菜单项：(key, label) 列表。非 admin 角色不展示仅管理员菜单。"""
    if role_code == "admin":
        return MENU_ITEMS
    return tuple((k, v) for k, v in MENU_ITEMS if k not in ADMIN_ONLY_MENU_KEYS)


def sanitize_menu_keys_for_role(role_code: Optional[str], keys: list) -> list:
    """保存角色时过滤非法 key；非 admin 角色剔除仅管理员菜单。"""
    out = []
    seen = set()
    allowed_pool = ALL_MENU_KEYS
    if role_code != "admin":
        allowed_pool = ALL_MENU_KEYS - ADMIN_ONLY_MENU_KEYS
    for k in keys:
        if not k or k in seen:
            continue
        if k not in allowed_pool:
            continue
        seen.add(k)
        out.append(k)
    return out


def user_menu_key_set(user):
    """
    当前用户允许的菜单 key 集合。
    None 表示拥有全部菜单（管理员）；否则为 frozenset。
    """
    if not user or not getattr(user, "is_authenticated", False):
        return frozenset()
    code = getattr(user, "role_code", None)
    if code == "admin":
        return None
    if code == "pending":
        return frozenset()
    role = getattr(user, "role", None)
    if not role:
        return frozenset()
    return role.parsed_menu_key_set()


def current_user_can_menu(menu_key: str) -> bool:
    if menu_key not in ALL_MENU_KEYS:
        return False
    if not current_user.is_authenticated:
        return False
    code = getattr(current_user, "role_code", None)
    if code == "admin":
        return True
    if code == "pending":
        return False
    allowed = user_menu_key_set(current_user)
    if allowed is None:
        return True
    return menu_key in allowed


def user_has_any_menu() -> bool:
    if not current_user.is_authenticated:
        return False
    code = getattr(current_user, "role_code", None)
    if code == "admin":
        return True
    if code == "pending":
        return False
    return any(current_user_can_menu(k) for k in LANDING_MENU_ORDER)


def first_landing_url() -> str:
    """已登录、非 pending 用户的首页跳转地址。"""
    for key in LANDING_MENU_ORDER:
        if current_user_can_menu(key):
            ep = _MENU_ENDPOINT.get(key)
            if ep:
                return url_for(ep)
    return url_for(NO_MENU_ACCESS_ENDPOINT)


def role_assignable_for_registration(role) -> bool:
    """注册时可申请的角色：非 admin/pending，且至少配置了一项业务菜单。"""
    if not role:
        return False
    if role.code in ("admin", "pending"):
        return False
    keys = role.parsed_menu_key_set()
    return len(keys) > 0
