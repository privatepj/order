"""菜单权限（sys_nav_item + role_allowed_nav；无种子时兼容 JSON）。"""

from __future__ import annotations

from typing import List, Optional

from flask import url_for
from flask_login import current_user

from app.auth.rbac_cache import (
    get_admin_only_nav_codes,
    get_assignable_nav_codes,
    get_endpoint_for_nav_code,
    get_landing_nav_order,
)

NO_MENU_ACCESS_ENDPOINT = "main.no_menu_access"

# 库表无数据时的兜底（与全量种子 / run_16 基线一致）
_FALLBACK_ASSIGNABLE = frozenset(
    {
        "order",
        "production_preplan",
        "production_department",
        "production_incident",
        "delivery",
        "express",
        "inventory_query",
        "inventory_ops_finished",
        "inventory_ops_semi",
        "inventory_ops_material",
        "customer",
        "product",
        "customer_product",
        "crm_lead",
        "crm_opportunity",
        "crm_ticket",
        "company",
        "user_mgmt",
        "role_mgmt",
        "reconciliation",
        "report_notes",
        "report_records",
        "hr_department",
        "hr_work_type",
        "hr_employee",
        "hr_employee_schedule",
        "hr_employee_capability",
        "hr_department_capability_map",
        "hr_payroll",
        "hr_performance",
        "dept_piece_rate",
        "machine_type",
        "machine_asset",
        "machine_runtime",
        "machine_schedule",
        "procurement_material",
        "procurement_requisition",
        "procurement_supplier",
        "procurement_order",
        "procurement_receipt",
        "procurement_stockin",
    }
)
_FALLBACK_ADMIN_ONLY = frozenset({"company", "user_mgmt", "role_mgmt"})
_FALLBACK_ENDPOINTS = {
    "order": "main.order_list",
    "production_preplan": "main.production_preplan_list",
    "production_department": "main.production_department_board",
    "production_incident": "main.production_incident_list",
    "delivery": "main.delivery_list",
    "customer": "main.customer_list",
    "product": "main.product_list",
    "customer_product": "main.customer_product_list",
    "crm_lead": "main.crm_lead_list",
    "crm_opportunity": "main.crm_opportunity_list",
    "crm_ticket": "main.crm_ticket_list",
    "reconciliation": "main.reconciliation_export",
    "report_notes": "main.report_export_delivery_notes",
    "report_records": "main.report_export_delivery_records",
    "company": "main.company_list",
    "express": "main.express_company_list",
    "inventory_query": "main.inventory_stock_query",
    "inventory_ops_finished": "main.inventory_finished_entry",
    "inventory_ops_semi": "main.inventory_semi_entry",
    "inventory_ops_material": "main.inventory_material_entry",
    "user_mgmt": "main.user_list",
    "role_mgmt": "main.role_list",
    "hr_department": "main.hr_department_list",
    "hr_work_type": "main.hr_work_type_list",
    "hr_employee": "main.hr_employee_list",
    "hr_employee_schedule": "main.hr_employee_schedule_template_list",
    "hr_employee_capability": "main.hr_employee_capability_list",
    "hr_department_capability_map": "main.hr_department_capability_map_list",
    "hr_payroll": "main.hr_payroll_list",
    "hr_performance": "main.hr_performance_list",
    "dept_piece_rate": "main.dept_piece_rate_list",
    "machine_type": "main.machine_type_list",
    "machine_asset": "main.machine_list",
    "machine_runtime": "main.machine_runtime_list",
    "machine_schedule": "main.machine_schedule_template_list",
    "procurement_material": "main.procurement_material_list",
    "procurement_requisition": "main.procurement_requisition_list",
    "procurement_supplier": "main.procurement_supplier_list",
    "procurement_order": "main.procurement_order_list",
    "procurement_receipt": "main.procurement_receipt_list",
    "procurement_stockin": "main.procurement_stockin_list",
}
_FALLBACK_LANDING = [
    "order",
    "production_preplan",
    "production_department",
    "production_incident",
    "delivery",
    "customer",
    "product",
    "customer_product",
    "crm_lead",
    "crm_opportunity",
    "crm_ticket",
    "reconciliation",
    "report_notes",
    "report_records",
    "company",
    "express",
    "inventory_query",
    "inventory_ops_finished",
    "inventory_ops_semi",
    "inventory_ops_material",
    "user_mgmt",
    "role_mgmt",
    "hr_department",
    "hr_work_type",
    "hr_employee",
    "hr_employee_schedule",
    "hr_employee_capability",
    "hr_department_capability_map",
    "hr_payroll",
    "hr_performance",
    "dept_piece_rate",
    "machine_type",
    "machine_asset",
    "machine_runtime",
    "machine_schedule",
    "procurement_material",
    "procurement_requisition",
    "procurement_supplier",
    "procurement_order",
    "procurement_receipt",
    "procurement_stockin",
]
_FALLBACK_MENU_LABELS = {
    "order": "订单",
    "production_preplan": "预生产计划",
    "production_department": "部门生产看板",
    "production_incident": "生产事故",
    "delivery": "送货",
    "express": "快递",
    "inventory_query": "库存查询",
    "inventory_ops_finished": "成品录入",
    "inventory_ops_semi": "半成品录入",
    "inventory_ops_material": "材料录入",
    "customer": "客户",
    "product": "产品",
    "customer_product": "客户产品",
    "crm_lead": "CRM 线索",
    "crm_opportunity": "CRM 机会",
    "crm_ticket": "CRM 工单",
    "company": "公司主体",
    "user_mgmt": "用户管理",
    "role_mgmt": "角色管理",
    "reconciliation": "对账导出",
    "report_notes": "导出送货单Excel",
    "report_records": "导出送货记录Excel",
    "hr_department": "部门",
    "hr_work_type": "工种管理",
    "hr_employee": "人员档案",
    "hr_employee_schedule": "人员排产",
    "hr_employee_capability": "人员能力表",
    "hr_department_capability_map": "部门-工种允许关系",
    "hr_payroll": "工资录入",
    "hr_performance": "绩效管理",
    "dept_piece_rate": "工种计件单价",
    "machine_type": "机台种类",
    "machine_asset": "机台台账",
    "machine_runtime": "运转情况",
    "machine_schedule": "机台排班",
    "procurement_requisition": "采购请购",
    "procurement_supplier": "供应商",
    "procurement_order": "采购单",
    "procurement_receipt": "采购收货",
    "procurement_stockin": "采购入库",
}

_FALLBACK_MENU_LABELS["procurement_material"] = "物料管理"


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


def user_can_menu(user, menu_key: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    code = getattr(user, "role_code", None)
    if code == "pending":
        return False
    if code == "admin":
        # 管理员也须对应有效菜单项；但须先于 assignable 快照判断。
        # 否则 RBAC 进程内缓存未刷新时，新写入 sys_nav_item 的菜单会对 admin 误返回 False。
        if menu_key in _assignable_codes():
            return True
        from app.models.rbac import SysNavItem

        return (
            SysNavItem.query.filter_by(
                code=menu_key, is_active=True, is_assignable=True
            ).first()
            is not None
        )
    if menu_key not in _assignable_codes():
        return False
    allowed = user_menu_key_set(user)
    if allowed is None:
        return True
    return menu_key in allowed


def current_user_can_menu(menu_key: str) -> bool:
    return user_can_menu(current_user, menu_key)


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
        (
            "production",
            "生产管理",
            None,
            [
                (
                    "production_preplan",
                    "预生产计划",
                    "main.production_preplan_list",
                    None,
                ),
                (
                    "production_department",
                    "部门生产看板",
                    "main.production_department_board",
                    None,
                ),
                (
                    "production_incident",
                    "生产事故",
                    "main.production_incident_list",
                    None,
                ),
                (
                    "machine_schedule",
                    "机台排班",
                    "main.machine_schedule_template_list",
                    None,
                ),
                (
                    "hr_employee_schedule",
                    "人员排产",
                    "main.hr_employee_schedule_template_list",
                    None,
                ),
            ],
        ),
        (
            "nav_hr",
            "人力资源",
            None,
            [
                ("hr_department", "部门", "main.hr_department_list", None),
                ("hr_work_type", "工种管理", "main.hr_work_type_list", None),
                ("hr_employee", "人员档案", "main.hr_employee_list", None),
                (
                    "hr_employee_capability",
                    "人员能力表",
                    "main.hr_employee_capability_list",
                    None,
                ),
                (
                    "hr_department_capability_map",
                    "部门-工种允许关系",
                    "main.hr_department_capability_map_list",
                    None,
                ),
                ("hr_payroll", "工资录入", "main.hr_payroll_list", None),
                ("hr_performance", "绩效管理", "main.hr_performance_list", None),
            ],
        ),
        (
            "nav_machine",
            "机台管理",
            None,
            [
                ("machine_type", "机台种类", "main.machine_type_list", None),
                ("machine_asset", "机台台账", "main.machine_list", None),
                ("machine_runtime", "运转情况", "main.machine_runtime_list", None),
            ],
        ),
        (
            "nav_procurement",
            "采购管理",
            None,
            [
                (
                    "procurement_material",
                    "物料管理",
                    "main.procurement_material_list",
                    None,
                ),
                (
                    "procurement_requisition",
                    "采购请购",
                    "main.procurement_requisition_list",
                    None,
                ),
                (
                    "procurement_supplier",
                    "供应商",
                    "main.procurement_supplier_list",
                    None,
                ),
                ("procurement_order", "采购单", "main.procurement_order_list", None),
                (
                    "procurement_receipt",
                    "采购收货",
                    "main.procurement_receipt_list",
                    None,
                ),
                (
                    "procurement_stockin",
                    "采购入库",
                    "main.procurement_stockin_list",
                    None,
                ),
            ],
        ),
        (
            "nav_warehouse",
            "仓管",
            None,
            [
                ("delivery", "送货", "main.delivery_list", None),
                ("express", "快递", "main.express_company_list", None),
                ("inventory_query", "库存查询", "main.inventory_stock_query", None),
                (
                    "inventory_ops_finished",
                    "成品录入",
                    "main.inventory_finished_entry",
                    None,
                ),
                ("inventory_ops_semi", "半成品录入", "main.inventory_semi_entry", None),
                (
                    "inventory_ops_material",
                    "材料录入",
                    "main.inventory_material_entry",
                    None,
                ),
            ],
        ),
        (
            "nav_crm",
            "CRM管理",
            None,
            [
                ("crm_lead", "CRM 线索", "main.crm_lead_list", None),
                ("crm_opportunity", "CRM 机会", "main.crm_opportunity_list", None),
                ("crm_ticket", "CRM 工单", "main.crm_ticket_list", None),
            ],
        ),
        (
            "nav_base",
            "基础数据",
            None,
            [
                ("customer", "客户", "main.customer_list", None),
                ("product", "产品", "main.product_list", None),
                ("customer_product", "客户产品", "main.customer_product_list", None),
                ("company", "公司主体", "main.company_list", None),
                ("user_mgmt", "用户管理", "main.user_list", None),
                ("role_mgmt", "角色管理", "main.role_list", None),
            ],
        ),
        (
            "nav_finance",
            "财务",
            None,
            [
                ("reconciliation", "对账导出", "main.reconciliation_export", None),
            ],
        ),
        (
            "nav_report",
            "报表导出",
            None,
            [
                (
                    "report_notes",
                    "导出送货单Excel",
                    "main.report_export_delivery_notes",
                    None,
                ),
                (
                    "report_records",
                    "导出送货记录Excel",
                    "main.report_export_delivery_records",
                    None,
                ),
            ],
        ),
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
                # base.html 仅渲染两级导航；若出现更深层分组，向上扁平化为可点击叶子，避免 endpoint=None 导致 url_for 报错
                if built.get("endpoint") is None and built.get("children"):
                    subs.extend(built.get("children", []))
                else:
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
