"""菜单权限（sys_nav_item + role_allowed_nav；无种子时兼容 JSON）。"""

from __future__ import annotations

from typing import List, Optional, Tuple

from flask import url_for
from flask_login import current_user

from app.auth.rbac_cache import (
    get_admin_only_nav_codes,
    get_assignable_nav_codes,
    get_endpoint_for_nav_code,
    get_landing_nav_order,
)

NO_MENU_ACCESS_ENDPOINT = "main.no_menu_access"

# 库表无数据时的兜底（与 run_16 叶子一致）
_FALLBACK_ASSIGNABLE = frozenset(
    {
        "order",
        "delivery",
        "express",
        "inventory_query",
        "inventory_ops",
        "customer",
        "product",
        "customer_product",
        "company",
        "user_mgmt",
        "role_mgmt",
        "reconciliation",
        "report_notes",
        "report_records",
    }
)
_FALLBACK_ADMIN_ONLY = frozenset({"company", "user_mgmt", "role_mgmt"})
_FALLBACK_ENDPOINTS = {
    "order": "main.order_list",
    "delivery": "main.delivery_list",
    "customer": "main.customer_list",
    "product": "main.product_list",
    "customer_product": "main.customer_product_list",
    "reconciliation": "main.reconciliation_export",
    "report_notes": "main.report_export_delivery_notes",
    "report_records": "main.report_export_delivery_records",
    "company": "main.company_list",
    "express": "main.express_company_list",
    "inventory_query": "main.inventory_stock_query",
    "inventory_ops": "main.inventory_list",
    "user_mgmt": "main.user_list",
    "role_mgmt": "main.role_list",
}
_FALLBACK_LANDING = [
    "order",
    "delivery",
    "customer",
    "product",
    "customer_product",
    "reconciliation",
    "report_notes",
    "report_records",
    "company",
    "express",
    "inventory_query",
    "inventory_ops",
    "user_mgmt",
    "role_mgmt",
]
_FALLBACK_MENU_LABELS = {
    "order": "订单",
    "delivery": "送货",
    "express": "快递",
    "inventory_query": "库存查询",
    "inventory_ops": "库存录入",
    "customer": "客户",
    "product": "产品",
    "customer_product": "客户产品",
    "company": "公司主体",
    "user_mgmt": "用户管理",
    "role_mgmt": "角色管理",
    "reconciliation": "对账导出",
    "report_notes": "导出送货单Excel",
    "report_records": "导出送货记录Excel",
}


def get_menu_label_map() -> dict:
    """code -> 标题，供角色列表等使用。"""
    from app.models.rbac import SysNavItem

    rows = SysNavItem.query.filter_by(is_active=True, is_assignable=True).all()
    if rows:
        return {r.code: r.title for r in rows}
    return dict(_FALLBACK_MENU_LABELS)


def _assignable_codes():
    c = get_assignable_nav_codes()
    return c if c else _FALLBACK_ASSIGNABLE


def _admin_only_codes():
    c = get_admin_only_nav_codes()
    return c if c else _FALLBACK_ADMIN_ONLY


def _endpoint(code: str) -> Optional[str]:
    ep = get_endpoint_for_nav_code(code)
    if ep:
        return ep
    return _FALLBACK_ENDPOINTS.get(code)


def _landing_order():
    lo = get_landing_nav_order()
    return lo if lo else _FALLBACK_LANDING


def menu_keys_for_role_edit(role_code: Optional[str]):
    """编辑角色时可选菜单：(code, title) 扁平列表，来自库表。"""
    from app.models.rbac import SysNavItem

    rows = (
        SysNavItem.query.filter_by(is_active=True, is_assignable=True)
        .order_by(SysNavItem.sort_order.asc(), SysNavItem.id.asc())
        .all()
    )
    if not rows:
        labels = _FALLBACK_MENU_LABELS
        keys = sorted(_FALLBACK_ASSIGNABLE)
        if role_code != "admin":
            keys = [k for k in keys if k not in _FALLBACK_ADMIN_ONLY]
        return tuple((k, labels.get(k, k)) for k in keys)
    if role_code == "admin":
        return tuple((r.code, r.title) for r in rows)
    adm = _admin_only_codes()
    return tuple((r.code, r.title) for r in rows if r.code not in adm)


def sanitize_menu_keys_for_role(role_code: Optional[str], keys: list) -> list:
    pool = set(_assignable_codes())
    if role_code != "admin":
        pool -= _admin_only_codes()
    out = []
    seen = set()
    for k in keys:
        if not k or k in seen:
            continue
        if k not in pool:
            continue
        seen.add(k)
        out.append(k)
    return out


def user_menu_key_set(user):
    """None=管理员全菜单；frozenset=已授权 nav code。"""
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
    return role.resolved_nav_codes()


def current_user_can_menu(menu_key: str) -> bool:
    if menu_key not in _assignable_codes():
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
    return any(current_user_can_menu(k) for k in _landing_order())


def first_landing_url() -> str:
    for key in _landing_order():
        if current_user_can_menu(key):
            ep = _endpoint(key)
            if ep:
                return url_for(ep)
    return url_for(NO_MENU_ACCESS_ENDPOINT)


def role_assignable_for_registration(role) -> bool:
    if not role:
        return False
    if role.code in ("admin", "pending"):
        return False
    return len(role.resolved_nav_codes()) > 0


def _fallback_nav_specs():
    """库表无数据时的静态树（与 run_16 一致）。"""
    return [
        ("order", "订单", "main.order_list", None),
        ("nav_warehouse", "仓管", None, [
            ("delivery", "送货", "main.delivery_list", None),
            ("express", "快递", "main.express_company_list", None),
            ("inventory_query", "库存查询", "main.inventory_stock_query", None),
            ("inventory_ops", "库存录入", "main.inventory_list", None),
        ]),
        ("nav_base", "基础数据", None, [
            ("customer", "客户", "main.customer_list", None),
            ("product", "产品", "main.product_list", None),
            ("customer_product", "客户产品", "main.customer_product_list", None),
            ("company", "公司主体", "main.company_list", None),
            ("user_mgmt", "用户管理", "main.user_list", None),
            ("role_mgmt", "角色管理", "main.role_list", None),
        ]),
        ("nav_finance", "财务", None, [
            ("reconciliation", "对账导出", "main.reconciliation_export", None),
        ]),
        ("nav_report", "报表导出", None, [
            ("report_notes", "导出送货单Excel", "main.report_export_delivery_notes", None),
            ("report_records", "导出送货记录Excel", "main.report_export_delivery_records", None),
        ]),
    ]


def nav_tree_for_user() -> List[dict]:
    """供 base.html 渲染：已按权限过滤的树节点列表。"""
    from app.models.rbac import SysNavItem

    rows = SysNavItem.query.filter_by(is_active=True).all()
    if not rows:
        specs = _fallback_nav_specs()
        nodes = []
        for code, title, endpoint, children in specs:
            if children:
                ch_list = []
                for cc, ct, cep, _ in children:
                    if current_user_can_menu(cc):
                        ch_list.append(
                            {
                                "code": cc,
                                "title": ct,
                                "endpoint": cep,
                                "children": [],
                                "is_dropdown": False,
                            }
                        )
                if ch_list:
                    nodes.append(
                        {
                            "code": code,
                            "title": title,
                            "endpoint": None,
                            "children": ch_list,
                            "is_dropdown": True,
                        }
                    )
            elif endpoint and current_user_can_menu(code):
                nodes.append(
                    {
                        "code": code,
                        "title": title,
                        "endpoint": endpoint,
                        "children": [],
                        "is_dropdown": False,
                    }
                )
        return nodes
    by_id = {r.id: r for r in rows}
    children: dict = {}
    for r in rows:
        pid = r.parent_id
        if pid is None:
            continue
        children.setdefault(pid, []).append(r)
    for lst in children.values():
        lst.sort(key=lambda x: (x.sort_order, x.id))

    def filter_node(item: SysNavItem) -> Optional[dict]:
        subs_raw = children.get(item.id, [])
        subs = []
        for ch in subs_raw:
            built = filter_node(ch)
            if built:
                subs.append(built)
        if item.endpoint:
            if current_user_can_menu(item.code):
                return {
                    "code": item.code,
                    "title": item.title,
                    "endpoint": item.endpoint,
                    "children": subs,
                    "is_dropdown": len(subs) > 0,
                }
            return None
        if subs:
            return {
                "code": item.code,
                "title": item.title,
                "endpoint": None,
                "children": subs,
                "is_dropdown": True,
            }
        return None

    roots = [r for r in rows if r.parent_id is None]
    roots.sort(key=lambda x: (x.sort_order, x.id))
    out = []
    for r in roots:
        node = filter_node(r)
        if node:
            out.append(node)
    return out

