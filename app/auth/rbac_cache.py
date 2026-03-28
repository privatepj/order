"""RBAC 库表缓存；管理端保存后须调用 invalidate_rbac_cache()。"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Tuple

_lock = threading.Lock()
_version = 0
_snapshot: Optional[Dict[str, Any]] = None


def invalidate_rbac_cache() -> None:
    global _snapshot
    with _lock:
        _snapshot = None


def _ensure_snapshot():
    global _snapshot, _version
    with _lock:
        if _snapshot is not None:
            return
        from app.models.rbac import SysCapability, SysNavItem

        nav_rows = SysNavItem.query.filter_by(is_active=True).all()
        nav_rows.sort(key=lambda x: (x.parent_id is not None, x.parent_id or 0, x.sort_order, x.id))
        cap_rows = (
            SysCapability.query.filter_by(is_active=True)
            .order_by(SysCapability.nav_item_code.asc(), SysCapability.sort_order.asc(), SysCapability.id.asc())
            .all()
        )
        nav_by_id = {r.id: r for r in nav_rows}
        children: Dict[int, List[SysNavItem]] = {}
        roots: List[SysNavItem] = []
        for r in nav_rows:
            pid = r.parent_id
            if pid is None:
                roots.append(r)
            else:
                children.setdefault(pid, []).append(r)
        assignable_codes = frozenset(x.code for x in nav_rows if x.is_assignable)
        endpoint_by_code = {x.code: x.endpoint for x in nav_rows if x.endpoint}
        landing_leaves = sorted(
            (x for x in nav_rows if x.is_assignable and x.landing_priority is not None),
            key=lambda x: (x.landing_priority or 9999, x.id),
        )
        landing_order = [x.code for x in landing_leaves]
        admin_only_codes = frozenset(x.code for x in nav_rows if x.admin_only and x.is_assignable)
        if cap_rows:
            caps = [
                (c.code, c.title, c.nav_item_code, c.group_label or c.nav_item_code)
                for c in cap_rows
            ]
            cap_to_nav = {c.code: c.nav_item_code for c in cap_rows}
            all_cap_codes = frozenset(c.code for c in cap_rows)
        else:
            from app.auth.capability_data import CAPABILITY_FALLBACK

            caps = [
                (a, b, c, d or c)
                for a, b, c, d in CAPABILITY_FALLBACK
            ]
            cap_to_nav = {a: c for a, b, c, d in CAPABILITY_FALLBACK}
            all_cap_codes = frozenset(cap_to_nav.keys())
        _snapshot = {
            "nav_rows": nav_rows,
            "nav_by_id": nav_by_id,
            "children": children,
            "roots": sorted(roots, key=lambda x: (x.sort_order, x.id)),
            "assignable_codes": assignable_codes,
            "endpoint_by_code": endpoint_by_code,
            "landing_order": landing_order,
            "admin_only_codes": admin_only_codes,
            "capability_tuples": caps,
            "cap_to_nav": cap_to_nav,
            "all_cap_codes": all_cap_codes,
        }


def get_nav_snapshot() -> Dict[str, Any]:
    _ensure_snapshot()
    return _snapshot or {}


def get_assignable_nav_codes() -> frozenset:
    return get_nav_snapshot().get("assignable_codes", frozenset())


def get_all_cap_codes() -> frozenset:
    return get_nav_snapshot().get("all_cap_codes", frozenset())


def get_capability_tuples() -> List[Tuple[str, str, str, str]]:
    return list(get_nav_snapshot().get("capability_tuples", []))


def get_endpoint_for_nav_code(code: str) -> Optional[str]:
    return get_nav_snapshot().get("endpoint_by_code", {}).get(code)


def get_landing_nav_order() -> List[str]:
    return list(get_nav_snapshot().get("landing_order", []))


def get_admin_only_nav_codes() -> frozenset:
    return get_nav_snapshot().get("admin_only_codes", frozenset())


def get_nav_children_map() -> Tuple[List[Any], Dict[int, List[Any]]]:
    s = get_nav_snapshot()
    return s.get("roots", []), s.get("children", {})
