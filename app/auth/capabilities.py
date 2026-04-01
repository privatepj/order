"""细项能力：优先 sys_capability 表，无数据时用 capability_data 兜底。"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from flask import request
from flask_login import current_user

from app.auth.capability_data import CAPABILITY_FALLBACK
from app.auth.menus import current_user_can_menu, user_can_menu
from app.auth.rbac_cache import get_all_cap_codes, get_capability_tuples, get_nav_snapshot

_ORDER_EDIT_DELETE_CAPS = frozenset({"order.action.edit", "order.action.delete"})


def _capability_rows() -> List[Tuple[str, str, str, str]]:
    t = get_capability_tuples()
    if t:
        return t
    return list(CAPABILITY_FALLBACK)


def _cap_maps():
    rows = _capability_rows()
    cap_label = {a: b for a, b, _, _ in rows}
    cap_to_nav = {a: c for a, b, c, _ in rows}
    all_keys = frozenset(cap_label.keys())
    return cap_label, cap_to_nav, all_keys


def capability_groups_for_menus(menu_keys: Optional[Sequence[str]]) -> List[Tuple[str, List[Tuple[str, str]]]]:
    from collections import OrderedDict

    items = capability_items_for_menus(menu_keys)
    od: "OrderedDict[str, List[Tuple[str, str]]]" = OrderedDict()
    for key, label, _nav, group in items:
        od.setdefault(group, []).append((key, label))
    return list(od.items())


def capability_groups_for_menus_from_rows(
    menu_keys: Optional[Sequence[str]], rows: List[Tuple[str, str, str, str]]
) -> List[Tuple[str, List[Tuple[str, str]]]]:
    from collections import OrderedDict

    items = _filter_cap_rows(rows, menu_keys)
    od: "OrderedDict[str, List[Tuple[str, str]]]" = OrderedDict()
    for key, label, _nav, group in items:
        od.setdefault(group, []).append((key, label))
    return list(od.items())


def _filter_cap_rows(rows, menu_keys: Optional[Sequence[str]]):
    if not menu_keys:
        return rows
    allowed = frozenset(str(x) for x in menu_keys if x)
    return [row for row in rows if row[2] in allowed]


def capability_items_for_menus(menu_keys: Optional[Sequence[str]]) -> List[Tuple[str, str, str, str]]:
    return _filter_cap_rows(_capability_rows(), menu_keys)


def sanitize_capability_keys_for_role(
    role_code: Optional[str],
    keys: List[str],
    menu_key_set: frozenset,
) -> List[str]:
    _, cap_to_nav, all_keys = _cap_maps()
    out: List[str] = []
    seen = set()
    for k in keys:
        if not k or k in seen:
            continue
        if k not in all_keys:
            continue
        if role_code != "admin":
            m = cap_to_nav.get(k)
            if m and m not in menu_key_set:
                continue
        seen.add(k)
        out.append(k)
    return out


def user_capability_key_set(user) -> Optional[frozenset]:
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
    return role.resolved_capability_key_set()


def user_can_cap(user, key: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    code = getattr(user, "role_code", None)
    # 管理员不受 sys_capability / 缓存是否已含某 key 影响，始终具备全部细项能力
    if code == "admin":
        return True
    _, _, all_keys = _cap_maps()
    if key not in all_keys:
        return False
    if code == "pending":
        return False
    _, cap_to_nav, _ = _cap_maps()
    menu = cap_to_nav.get(key)
    if menu and not user_can_menu(user, menu):
        return False
    allowed = user_capability_key_set(user)
    if allowed is None:
        if key in _ORDER_EDIT_DELETE_CAPS:
            return getattr(user, "role_code", None) == "admin"
        return True
    return key in allowed


def current_user_can_cap(key: str) -> bool:
    return user_can_cap(current_user, key)


def order_list_read_filters():
    page = request.args.get("page", 1, type=int)
    customer_id = request.args.get("customer_id", type=int)
    status = (request.args.get("status") or "").strip()
    payment_type = (request.args.get("payment_type") or "").strip()
    keyword = (request.args.get("keyword") or "").strip()
    if not current_user_can_cap("order.filter.customer"):
        customer_id = None
    if not current_user_can_cap("order.filter.status"):
        status = ""
    if not current_user_can_cap("order.filter.payment_type"):
        payment_type = ""
    if not current_user_can_cap("order.filter.keyword"):
        keyword = ""
    return page, customer_id, status, payment_type, keyword


def customer_product_list_read_filters():
    page = request.args.get("page", 1, type=int)
    customer_id = request.args.get("customer_id", type=int)
    keyword = (request.args.get("keyword") or "").strip()
    if not current_user_can_cap("customer_product.filter.customer"):
        customer_id = None
    if not current_user_can_cap("customer_product.filter.keyword"):
        keyword = ""
    return page, customer_id, keyword


def delivery_list_read_filters():
    page = request.args.get("page", 1, type=int)
    customer_id = request.args.get("customer_id", type=int)
    status = (request.args.get("status") or "").strip()
    keyword = (request.args.get("keyword") or "").strip()
    if not current_user_can_cap("delivery.filter.customer"):
        customer_id = None
    if not current_user_can_cap("delivery.filter.status"):
        status = ""
    if not current_user_can_cap("delivery.filter.keyword"):
        keyword = ""
    return page, customer_id, status, keyword


def customer_list_read_filters():
    """关键词始终从 querystring 读取；`customer.filter.keyword` 仅控制列表页是否展示搜索框（见模板）。"""
    return (request.args.get("keyword") or "").strip()


def product_list_read_filters():
    keyword = (request.args.get("keyword") or "").strip()
    if not current_user_can_cap("product.filter.keyword"):
        keyword = ""
    return keyword


def inventory_stock_query_read_filters():
    page = request.args.get("page", 1, type=int)
    category = (request.args.get("category") or "").strip()
    storage_area = (request.args.get("storage_area") or "").strip()
    spec_kw = (request.args.get("spec") or request.args.get("model") or "").strip()
    name_spec_kw = (request.args.get("name_spec") or "").strip()
    if not current_user_can_cap("inventory_query.filter.category"):
        category = ""
    if not current_user_can_cap("inventory_query.filter.storage_area"):
        storage_area = ""
    if not current_user_can_cap("inventory_query.filter.spec"):
        spec_kw = ""
    if not current_user_can_cap("inventory_query.filter.name_spec"):
        name_spec_kw = ""
    return page, category, storage_area, spec_kw, name_spec_kw


def role_capability_form_defaults(role) -> Tuple[bool, List[str]]:
    if role is None or getattr(role, "code", None) in ("admin", "pending"):
        return True, []
    fs = role.resolved_capability_key_set()
    if fs is None:
        return True, []
    return False, sorted(fs)


# 兼容：部分代码可能引用
CAP_LABEL = {a: b for a, b, _, _ in CAPABILITY_FALLBACK}
CAP_TO_MENU = {a: c for a, b, c, _ in CAPABILITY_FALLBACK}
ALL_CAP_KEYS = frozenset(CAP_LABEL.keys())
