from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from io import BytesIO
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Set

from flask import flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app import db
from app.auth.capabilities import current_user_can_cap
from app.auth.decorators import capability_required, menu_required
from app.utils.decimal_scale import quantize_decimal
from app.utils.hr_user import resolve_user_hr_department_id
from app.utils.visibility import is_admin
from app.models import (
    Company,
    CustomerProduct,
    Customer,
    HrDepartment,
    HrEmployee,
    HrEmployeeCapability,
    HrWorkType,
    Machine,
    MachineOperatorAllowlist,
    MachineScheduleBooking,
    MachineScheduleDispatchLog,
    MachineType,
    Product,
    ProductionComponentNeed,
    ProductionIncident,
    ProductionPreplan,
    ProductionPreplanLine,
    ProductionProductRouting,
    ProductionProductRoutingStep,
    ProductionProcessTemplate,
    ProductionProcessTemplateStep,
    ProductionProcessNode,
    ProductionProcessEdge,
    ProductionWorkOrder,
    ProductionWorkOrderOperation,
    ProductionCostPlanDetail,
    OrderItem,
    SalesOrder,
    SemiMaterial,
    User,
)
from app.services import (
    bom_svc,
    delivery_svc,
    inventory_svc,
    production_cost_svc,
    production_dept_board_svc,
    production_preplan_schedule_manual_svc,
    production_svc,
)
from app.services.production_schedule_svc import (
    compute_preplan_schedule_dashboard,
    list_schedule_plan_rows_for_preplan,
)
from app.services import orchestrator_engine
from app.services.orchestrator_contracts import EVENT_PRODUCTION_MEASURED
from app.services.orchestrator_contracts import (
    EVENT_MACHINE_ABNORMAL,
    EVENT_MACHINE_RECOVERED,
    EVENT_PRODUCTION_OPERATION_REPORTED,
    EVENT_PRODUCTION_REPORTED,
    EVENT_QUALITY_INSPECTION_STARTED,
    EVENT_QUALITY_PASSED,
)


def _parse_decimal(val: Any, *, default: Optional[Decimal] = None) -> Optional[Decimal]:
    if val is None:
        return default
    s = str(val).strip()
    if not s:
        return default
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return default


def _parse_occurred_at(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        if "T" in s:
            return datetime.fromisoformat(s)
        return datetime.combine(date.fromisoformat(s), datetime.min.time())
    except ValueError:
        return None


def _text_or_none(raw: Any) -> Optional[str]:
    s = (raw or "").strip()
    return s if s else None


def _parse_plan_date(raw: Any) -> Optional[date]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _parse_int(raw: Any, *, default: Optional[int] = None) -> Optional[int]:
    if raw is None:
        return default
    s = str(raw).strip()
    if not s:
        return default
    try:
        return int(s)
    except (TypeError, ValueError):
        return default


def _parse_decimal_non_negative(raw: Any, *, default: Decimal = Decimal(0)) -> Decimal:
    v = _parse_decimal(raw, default=None)
    if v is None:
        return default
    if v < 0:
        raise ValueError("数值不能为负数。")
    return v


PROCESS_RESOURCE_KINDS = ("machine_type", "hr_department", "hr_work_type")
PROCESS_EDGE_TYPES = ("fs",)


def _production_work_types() -> list[HrWorkType]:
    return (
        HrWorkType.query.options(selectinload(HrWorkType.company))
        .order_by(HrWorkType.company_id.asc(), HrWorkType.sort_order.asc(), HrWorkType.id.asc())
        .all()
    )


def _topology_has_cycle(nodes: List[int], edges: List[tuple[int, int]]) -> bool:
    indeg: Dict[int, int] = {n: 0 for n in nodes}
    succ: Dict[int, List[int]] = {n: [] for n in nodes}
    for a, b in edges:
        if a not in indeg or b not in indeg:
            continue
        indeg[b] += 1
        succ[a].append(b)
    q = [n for n, d in indeg.items() if d == 0]
    visited = 0
    while q:
        cur = q.pop(0)
        visited += 1
        for nxt in succ.get(cur, []):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    return visited != len(nodes)


def _parse_process_edges_from_form(*, expected_step_nos: List[int]) -> List[Dict[str, Any]]:
    from_steps_raw = request.form.getlist("edge_from_step_no")
    to_steps_raw = request.form.getlist("edge_to_step_no")
    edge_types_raw = request.form.getlist("edge_type")
    lags_raw = request.form.getlist("edge_lag_minutes")
    remarks_raw = request.form.getlist("edge_remark")

    expected_set = {int(x) for x in expected_step_nos}
    out: List[Dict[str, Any]] = []
    dedup: Set[tuple[int, int, str]] = set()
    for i, raw_from in enumerate(from_steps_raw):
        from_step = _parse_int(raw_from)
        to_step = _parse_int(to_steps_raw[i] if i < len(to_steps_raw) else None)
        etype = ((edge_types_raw[i] if i < len(edge_types_raw) else "fs") or "fs").strip().lower()
        lag = _parse_int(lags_raw[i] if i < len(lags_raw) else None, default=0) or 0
        remark = _text_or_none(remarks_raw[i] if i < len(remarks_raw) else None)

        if from_step is None or to_step is None:
            continue
        if from_step == to_step:
            raise ValueError("依赖关系中前置与后置工序不能相同。")
        if from_step not in expected_set or to_step not in expected_set:
            raise ValueError("依赖关系的 step_no 不在工序步骤范围内。")
        if etype not in PROCESS_EDGE_TYPES:
            raise ValueError("依赖类型暂只支持 FS。")

        k = (int(from_step), int(to_step), etype)
        if k in dedup:
            continue
        dedup.add(k)
        out.append(
            {
                "from_step_no": int(from_step),
                "to_step_no": int(to_step),
                "edge_type": etype,
                "lag_minutes": int(lag),
                "remark": remark,
            }
        )

    if out:
        if _topology_has_cycle(expected_step_nos, [(x["from_step_no"], x["to_step_no"]) for x in out]):
            raise ValueError("依赖关系存在环，请检查前后置设置。")
    return out


def _sync_process_graph_from_steps(
    *,
    template_id: int,
    steps: List[Dict[str, Any]],
    edges: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    串行模板自动同步为 DAG：
    - 每个 step 生成一个 operation 节点；
    - 按 step_no 升序生成 FS 边（n -> n+1）。
    """
    ProductionProcessEdge.query.filter_by(template_id=template_id).delete(synchronize_session=False)
    ProductionProcessNode.query.filter_by(template_id=template_id).delete(synchronize_session=False)
    db.session.flush()

    sorted_steps = sorted(list(steps or []), key=lambda x: int(x.get("step_no") or 0))
    node_by_step_no: Dict[int, int] = {}
    for st in sorted_steps:
        node = ProductionProcessNode(
            template_id=template_id,
            parent_node_id=None,
            step_no=int(st["step_no"]),
            node_type="operation",
            code=st.get("step_code"),
            name=st.get("step_name"),
            resource_kind=st.get("resource_kind"),
            machine_type_id=int(st.get("machine_type_id") or 0),
            hr_department_id=int(st.get("hr_department_id") or 0),
            hr_work_type_id=int(st.get("hr_work_type_id") or st.get("hr_department_id") or 0),
            setup_minutes=st.get("setup_minutes"),
            run_minutes_per_unit=st.get("run_minutes_per_unit"),
            scrap_rate=None,
            remark=st.get("remark"),
            is_active=True,
        )
        db.session.add(node)
        db.session.flush()
        node_by_step_no[int(st["step_no"])] = int(node.id)

    edge_rows = list(edges or [])
    if not edge_rows:
        for i in range(len(sorted_steps) - 1):
            edge_rows.append(
                {
                    "from_step_no": int(sorted_steps[i]["step_no"]),
                    "to_step_no": int(sorted_steps[i + 1]["step_no"]),
                    "edge_type": "fs",
                    "lag_minutes": 0,
                    "remark": None,
                }
            )
    for e in edge_rows:
        from_node_id = node_by_step_no.get(int(e["from_step_no"]))
        to_node_id = node_by_step_no.get(int(e["to_step_no"]))
        if not from_node_id or not to_node_id:
            continue
        db.session.add(
            ProductionProcessEdge(
                template_id=template_id,
                from_node_id=from_node_id,
                to_node_id=to_node_id,
                edge_type=str(e.get("edge_type") or "fs"),
                lag_minutes=int(e.get("lag_minutes") or 0),
                remark=e.get("remark"),
            )
        )


def _parse_process_template_steps_from_form() -> List[Dict[str, Any]]:
    """
    工序模板步骤表单解析：
    - 允许末尾空行（step_name 为空的行忽略）
    - step_no 必须从 1 开始连续且唯一（首版串行策略）
    - resource_kind 决定资源字段必填：machine_type 或 hr_work_type
    """
    step_nos_raw = request.form.getlist("step_no")
    step_codes_raw = request.form.getlist("step_code")
    step_names_raw = request.form.getlist("step_name")
    resource_kinds_raw = request.form.getlist("resource_kind")
    machine_type_ids_raw = request.form.getlist("machine_type_id")
    work_type_ids_raw = request.form.getlist("work_type_id")
    legacy_department_ids_raw = request.form.getlist("hr_department_id")
    setup_minutes_raw = request.form.getlist("setup_minutes")
    run_minutes_raw = request.form.getlist("run_minutes_per_unit")
    step_remarks_raw = request.form.getlist("step_remark")

    rows: List[Dict[str, Any]] = []
    for i, step_no_raw in enumerate(step_nos_raw):
        step_no = _parse_int(step_no_raw)
        step_name = _text_or_none(step_names_raw[i] if i < len(step_names_raw) else None)
        if step_no is None or not step_name:
            continue

        step_code = _text_or_none(step_codes_raw[i] if i < len(step_codes_raw) else None)

        resource_kind = (resource_kinds_raw[i] if i < len(resource_kinds_raw) else None) or "machine_type"
        resource_kind = str(resource_kind).strip()
        if resource_kind not in PROCESS_RESOURCE_KINDS:
            raise ValueError("资源维度 resource_kind 不合法。")
        if resource_kind != "machine_type":
            resource_kind = "hr_work_type"

        machine_type_id = _parse_int(machine_type_ids_raw[i] if i < len(machine_type_ids_raw) else None) or 0
        work_type_id = _parse_int(
            work_type_ids_raw[i] if i < len(work_type_ids_raw) else None
        ) or _parse_int(
            legacy_department_ids_raw[i] if i < len(legacy_department_ids_raw) else None
        ) or 0

        setup_minutes = _parse_decimal_non_negative(
            setup_minutes_raw[i] if i < len(setup_minutes_raw) else None, default=Decimal(0)
        )
        run_minutes_per_unit = _parse_decimal_non_negative(
            run_minutes_raw[i] if i < len(run_minutes_raw) else None, default=Decimal(0)
        )

        step_remark = _text_or_none(step_remarks_raw[i] if i < len(step_remarks_raw) else None)

        if resource_kind == "machine_type":
            if machine_type_id <= 0:
                raise ValueError("选择 machine_type 时 machine_type_id 必填。")
            work_type_id = 0
        else:
            if work_type_id <= 0:
                raise ValueError("选择工种时 work_type_id 必填。")
            machine_type_id = 0

        rows.append(
            {
                "step_no": int(step_no),
                "step_code": step_code,
                "step_name": step_name,
                "resource_kind": resource_kind,
                "machine_type_id": int(machine_type_id),
                "hr_department_id": int(work_type_id),
                "hr_work_type_id": int(work_type_id),
                "setup_minutes": setup_minutes,
                "run_minutes_per_unit": run_minutes_per_unit,
                "remark": step_remark,
            }
        )

    if not rows:
        raise ValueError("请至少录入一条工序步骤。")

    step_no_set = [r["step_no"] for r in rows]
    if len(step_no_set) != len(set(step_no_set)):
        raise ValueError("工序 step_no 不能重复。")

    rows.sort(key=lambda x: x["step_no"])
    expected = list(range(1, len(rows) + 1))
    actual = [r["step_no"] for r in rows]
    if actual != expected:
        raise ValueError("工序 step_no 需要从 1 开始连续且无缺失。")

    return rows


def _parse_product_routing_step_overrides_from_form(
    *,
    expected_template_step_nos: List[int],
) -> List[Dict[str, Any]]:
    """
    产品路由步骤覆写解析：
    - 只要该行至少有一个覆写字段（资源维度/工序名/准备分钟/运行分钟）就创建 routing_step 记录
    - 资源维度为空表示继承模板步骤资源；此时 machine/hr id 输入不会生效
    """
    expected_set = {int(x) for x in expected_template_step_nos}

    template_step_nos_raw = request.form.getlist("template_step_no")
    resource_kind_overrides_raw = request.form.getlist("resource_kind_override")
    machine_type_ids_raw = request.form.getlist("machine_type_id_override")
    work_type_ids_raw = request.form.getlist("work_type_id_override")
    legacy_department_ids_raw = request.form.getlist("hr_department_id_override")
    setup_minutes_override_raw = request.form.getlist("setup_minutes_override")
    run_minutes_override_raw = request.form.getlist("run_minutes_per_unit_override")
    step_name_override_raw = request.form.getlist("step_name_override")
    step_remark_override_raw = request.form.getlist("step_remark_override")

    out: List[Dict[str, Any]] = []

    for i, raw_stno in enumerate(template_step_nos_raw):
        stno = _parse_int(raw_stno)
        if stno is None:
            continue
        if stno not in expected_set:
            raise ValueError("路由步骤参数不合法。")

        res_kind_override = (resource_kind_overrides_raw[i] if i < len(resource_kind_overrides_raw) else None) or ""
        res_kind_override = str(res_kind_override).strip()
        if res_kind_override == "":
            res_kind_override_val: Optional[str] = None
        else:
            if res_kind_override not in PROCESS_RESOURCE_KINDS:
                raise ValueError("资源维度 resource_kind_override 不合法。")
            res_kind_override_val = "hr_work_type" if res_kind_override != "machine_type" else res_kind_override

        machine_type_id_override = _parse_int(
            machine_type_ids_raw[i] if i < len(machine_type_ids_raw) else None
        ) or 0
        work_type_id_override = _parse_int(
            work_type_ids_raw[i] if i < len(work_type_ids_raw) else None
        ) or _parse_int(
            legacy_department_ids_raw[i] if i < len(legacy_department_ids_raw) else None
        ) or 0

        setup_override = _parse_decimal(setup_minutes_override_raw[i] if i < len(setup_minutes_override_raw) else None, default=None)
        run_override = _parse_decimal(run_minutes_override_raw[i] if i < len(run_minutes_override_raw) else None, default=None)
        if setup_override is not None and setup_override < 0:
            raise ValueError("准备时间不能为负数。")
        if run_override is not None and run_override < 0:
            raise ValueError("运行时间/单位不能为负数。")

        step_name_override = _text_or_none(step_name_override_raw[i] if i < len(step_name_override_raw) else None)
        step_remark_override = _text_or_none(
            step_remark_override_raw[i] if i < len(step_remark_override_raw) else None
        )

        override_exists = (
            res_kind_override_val is not None
            or setup_override is not None
            or run_override is not None
            or step_name_override is not None
            or step_remark_override is not None
        )
        if not override_exists:
            continue

        # 资源维度继承：忽略机台/班组 id 覆写
        if res_kind_override_val is None:
            machine_type_id_override = 0
            work_type_id_override = 0
        elif res_kind_override_val == "machine_type":
            if machine_type_id_override <= 0:
                raise ValueError("选择 machine_type 时 machine_type_id_override 必填。")
            work_type_id_override = 0
        else:
            if work_type_id_override <= 0:
                raise ValueError("选择工种时 work_type_id_override 必填。")
            machine_type_id_override = 0

        out.append(
            {
                "template_step_no": int(stno),
                "resource_kind_override": res_kind_override_val,
                "machine_type_id_override": int(machine_type_id_override),
                "hr_department_id_override": int(work_type_id_override),
                "hr_work_type_id_override": int(work_type_id_override),
                "setup_minutes_override": setup_override,
                "run_minutes_per_unit_override": run_override,
                "step_name_override": step_name_override,
                "remark": step_remark_override,
            }
        )

    return out


def _parse_preplan_lines_from_form() -> List[Dict[str, Any]]:
    """
    表单解析：line_product_id + line_quantity + 可选 line_remark。
    过滤非法/空行；quantity <= 0 的行忽略。
    """
    pids = request.form.getlist("line_product_id")
    qtys = request.form.getlist("line_quantity")
    remarks = request.form.getlist("line_remark")

    rows: List[Dict[str, Any]] = []
    for i, pid_raw in enumerate(pids):
        pid_s = (pid_raw or "").strip()
        if not pid_s:
            continue
        try:
            product_id = int(pid_s)
        except ValueError:
            continue

        qty = _parse_decimal(qtys[i] if i < len(qtys) else None, default=None)
        if not qty or qty <= 0:
            continue

        remark_raw = remarks[i] if i < len(remarks) else None
        remark = (remark_raw or "").strip() or None
        rows.append({"product_id": product_id, "quantity": qty, "remark": remark})
    return rows


def _raw_material_totals_from_work_orders(
    work_orders: List[ProductionWorkOrder],
) -> List[Dict[str, Any]]:
    """按原材料汇总全计划需求量（child_kind=material）。"""
    agg: Dict[int, Decimal] = defaultdict(lambda: Decimal(0))
    meta: Dict[int, Dict[str, Any]] = {}
    for wo in work_orders:
        for n in wo.component_needs:
            if n.child_kind != bom_svc.PARENT_MATERIAL:
                continue
            mid = int(n.child_material_id)
            agg[mid] += Decimal(str(n.required_qty))
            m = n.child_material
            if mid not in meta:
                meta[mid] = {
                    "material_id": mid,
                    "material": m,
                    "code": m.code if m else str(mid),
                    "name": m.name if m else "",
                    "spec": (m.spec or "") if m else "",
                    "unit": None,
                }
            row = meta[mid]
            if row["unit"] is None:
                if m and (m.base_unit or "").strip():
                    row["unit"] = m.base_unit.strip()
                elif n.unit and str(n.unit).strip():
                    row["unit"] = str(n.unit).strip()
    rows: List[Dict[str, Any]] = []
    for mid, total in agg.items():
        r = meta[mid]
        u = r["unit"] or "-"
        mr = r["material"]
        if mr and (mr.base_unit or "").strip():
            u = mr.base_unit.strip()
        rows.append(
            {
                "material_id": mid,
                "code": r["code"],
                "name": r["name"],
                "spec": r["spec"],
                "required_total": total,
                "unit": u,
            }
        )
    rows.sort(key=lambda x: x["code"])
    return rows


def _company_id_from_preplan(preplan: ProductionPreplan) -> int:
    cid = int(preplan.customer_id or 0)
    if cid <= 0:
        return 0
    cust = Customer.query.get(cid)
    return int(cust.company_id) if cust else 0


def _budget_options_for_operations(
    work_orders: List[ProductionWorkOrder],
    company_id: int,
    *,
    viewer_dept_id: Optional[int] = None,
) -> Dict[int, Dict[str, Any]]:
    """预生产详情页：指定资源下拉选项（机台+白名单操作员；或部门能力员工）。"""
    out: Dict[int, Dict[str, Any]] = {}
    for wo in work_orders:
        for op in wo.operations or []:
            oid = int(op.id)
            if op.resource_kind == "machine_type" and int(op.machine_type_id or 0) > 0:
                mq = Machine.query.filter_by(
                    machine_type_id=int(op.machine_type_id), status="enabled"
                )
                if viewer_dept_id is not None and int(viewer_dept_id) > 0:
                    vid = int(viewer_dept_id)
                    mq = mq.filter(
                        db.or_(
                            Machine.owning_hr_department_id == 0,
                            Machine.owning_hr_department_id == vid,
                        )
                    )
                machines = mq.order_by(Machine.machine_no.asc()).all()
                pairs = []
                for m in machines:
                    for al in MachineOperatorAllowlist.query.filter_by(machine_id=m.id, is_active=True).all():
                        emp = HrEmployee.query.get(int(al.employee_id))
                        pairs.append(
                            {
                                "machine_id": m.id,
                                "employee_id": int(al.employee_id),
                                "label": f"{m.machine_no} + {(emp.name if emp else al.employee_id)}",
                            }
                        )
                out[oid] = {"kind": "machine_type", "pairs": pairs, "machines": machines}
            elif op.resource_kind in ("hr_department", "hr_work_type") and int(op.effective_work_type_id or 0) > 0:
                cap_ids = production_cost_svc.resolve_capability_dept_ids(
                    company_id=company_id, process_hr_department_id=int(op.effective_work_type_id)
                )
                if not cap_ids:
                    out[oid] = {"kind": "hr_work_type", "employees": []}
                    continue
                emp_rows = (
                    db.session.query(HrEmployeeCapability.employee_id)
                    .filter(
                        HrEmployeeCapability.company_id == company_id,
                        (
                            HrEmployeeCapability.work_type_id.in_(cap_ids)
                            | HrEmployeeCapability.hr_department_id.in_(cap_ids)
                        ),
                    )
                    .distinct()
                    .all()
                )
                eids = [int(r[0]) for r in emp_rows if r[0] is not None]
                emps = (
                    HrEmployee.query.filter(HrEmployee.id.in_(eids)).order_by(HrEmployee.id.asc()).all()
                    if eids
                    else []
                )
                out[oid] = {
                    "kind": "hr_work_type",
                    "employees": [{"id": e.id, "label": f"{e.employee_no} {e.name}"} for e in emps],
                }
    return out


def _require_preplan_with_lines(preplan_id: int) -> ProductionPreplan:
    preplan = (
        ProductionPreplan.query.options(selectinload(ProductionPreplan.lines))
        .filter(ProductionPreplan.id == preplan_id)
        .first()
    )
    if not preplan:
        raise ValueError("预生产计划不存在。")
    return preplan


def _resolve_order_id_by_work_order(wo: ProductionWorkOrder) -> Optional[int]:
    if not wo:
        return None
    # 优先：根需求行直接回溯 source_order_item_id
    if wo.root_preplan_line_id:
        ln = db.session.get(ProductionPreplanLine, int(wo.root_preplan_line_id))
        if ln and ln.source_order_item_id:
            oi = db.session.get(OrderItem, int(ln.source_order_item_id))
            if oi and oi.order_id:
                orchestrator_engine.log_manual_audit(
                    level="info",
                    message="wo_order_mapping_hit_direct",
                    detail={
                        "work_order_id": int(wo.id),
                        "order_id": int(oi.order_id),
                        "mapping": "root_preplan_line->source_order_item",
                    },
                )
                return int(oi.order_id)

    # 兜底：按 preplan.customer_id + 工单成品 product_id 回推“最近待交付订单”
    preplan = db.session.get(ProductionPreplan, int(wo.preplan_id or 0))
    if not preplan or not preplan.customer_id or not wo.parent_product_id:
        return None
    row = (
        db.session.query(SalesOrder.id)
        .join(OrderItem, OrderItem.order_id == SalesOrder.id)
        .join(CustomerProduct, CustomerProduct.id == OrderItem.customer_product_id)
        .filter(
            SalesOrder.customer_id == int(preplan.customer_id),
            SalesOrder.status.in_(("pending", "partial")),
            CustomerProduct.product_id == int(wo.parent_product_id),
        )
        .order_by(SalesOrder.required_date.asc(), SalesOrder.id.asc())
        .first()
    )
    if not row:
        orchestrator_engine.log_manual_audit(
            level="warn",
            message="wo_order_mapping_miss",
            detail={
                "work_order_id": int(wo.id),
                "preplan_id": int(wo.preplan_id or 0),
                "customer_id": int(preplan.customer_id or 0) if preplan else 0,
                "parent_product_id": int(wo.parent_product_id or 0),
            },
        )
        return None
    orchestrator_engine.log_manual_audit(
        level="info",
        message="wo_order_mapping_hit_fallback",
        detail={
            "work_order_id": int(wo.id),
            "order_id": int(row[0]),
            "mapping": "customer+product+pending_order",
        },
    )
    return int(row[0])


def register_production_routes(bp):
    # ----------------------------
    # 列表
    # ----------------------------
    @bp.route("/production/preplans")
    @login_required
    @menu_required("production_preplan")
    def production_preplan_list():
        preplans = (
            ProductionPreplan.query.order_by(ProductionPreplan.id.desc()).limit(100).all()
        )
        return render_template("production/preplan_list.html", preplans=preplans)

    @bp.route("/production/department-board")
    @login_required
    @menu_required("production_department")
    def production_department_board():
        company_id = int(Company.get_default_id() or 0)
        can_filter = current_user_can_cap("production.department.board.filter_dept") or is_admin()
        default_dept_id = resolve_user_hr_department_id(current_user.id)
        view_dept_id = request.args.get("department_id", type=int)
        if not can_filter:
            view_dept_id = default_dept_id
        elif view_dept_id is None or view_dept_id <= 0:
            view_dept_id = default_dept_id

        departments: List[HrDepartment] = []
        if can_filter and company_id:
            departments = (
                HrDepartment.query.filter_by(company_id=company_id)
                .order_by(HrDepartment.sort_order.asc(), HrDepartment.id.asc())
                .all()
            )

        rows: List[Dict[str, Any]] = []
        if not view_dept_id:
            flash("未绑定行政部门人员档案，或请选择部门。", "warning")
        else:
            rows = production_dept_board_svc.list_board_rows(
                dept_id=int(view_dept_id), company_id=company_id
            )

        return render_template(
            "production/department_board.html",
            rows=rows,
            departments=departments,
            view_dept_id=view_dept_id,
            default_dept_id=default_dept_id,
            can_filter_dept=can_filter,
        )

    # ----------------------------
    # 新建（手工预生产计划）
    # ----------------------------
    @bp.route("/production/preplans/new", methods=["GET", "POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.preplan.action.create")
    def production_preplan_new():
        if request.method == "POST":
            try:
                plan_date = _parse_plan_date(request.form.get("plan_date"))
                if not plan_date:
                    raise ValueError("请选择计划日期。")

                customer_id = request.form.get("customer_id", type=int)
                if customer_id is None:
                    customer_id = 0

                remark = (request.form.get("remark") or "").strip() or None
                rows = _parse_preplan_lines_from_form()
                if not rows:
                    raise ValueError("请至少录入一条预生产计划明细（数量 > 0）。")

                # 校验产品存在性
                product_ids = [r["product_id"] for r in rows]
                cnt = Product.query.filter(Product.id.in_(product_ids)).count()
                if cnt != len(set(product_ids)):
                    raise ValueError("存在无效的产品。")

                preplan = ProductionPreplan(
                    source_type="manual",
                    plan_date=plan_date,
                    customer_id=int(customer_id or 0),
                    status="draft",
                    remark=remark,
                    created_by=current_user.id,
                )
                db.session.add(preplan)
                db.session.flush()

                # 使用从 Product 主数据带出单位（展示/可后续扩展）
                pmap = {p.id: p for p in Product.query.filter(Product.id.in_(set(product_ids))).all()}
                line_no = 1
                for r in rows:
                    p = pmap.get(r["product_id"])
                    db.session.add(
                        ProductionPreplanLine(
                            preplan_id=preplan.id,
                            line_no=line_no,
                            source_type="manual",
                            source_order_item_id=None,
                            product_id=r["product_id"],
                            quantity=r["quantity"],
                            unit=(p.base_unit if p else None),
                            remark=r.get("remark"),
                        )
                    )
                    line_no += 1

                db.session.commit()
                flash("预生产计划已保存。", "success")
                return redirect(url_for("main.production_preplan_detail", preplan_id=preplan.id))
            except ValueError as e:
                db.session.rollback()
                flash(str(e), "danger")
            except IntegrityError:
                db.session.rollback()
                flash("保存失败：数据冲突。", "danger")

        products = Product.query.order_by(Product.product_code).all()
        customers = Customer.query.order_by(Customer.customer_code).all()
        return render_template(
            "production/preplan_form.html",
            mode="new",
            preplan=None,
            lines=[],
            products=products,
            customers=customers,
        )

    # ----------------------------
    # 编辑（手工预生产计划明细）
    # ----------------------------
    @bp.route("/production/preplans/<int:preplan_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.preplan.action.edit")
    def production_preplan_edit(preplan_id: int):
        preplan = _require_preplan_with_lines(preplan_id)

        if request.method == "POST":
            try:
                plan_date = _parse_plan_date(request.form.get("plan_date"))
                if not plan_date:
                    raise ValueError("请选择计划日期。")

                customer_id = request.form.get("customer_id", type=int) or 0
                remark = (request.form.get("remark") or "").strip() or None

                rows = _parse_preplan_lines_from_form()
                if not rows:
                    raise ValueError("请至少录入一条预生产计划明细（数量 > 0）。")

                product_ids = [r["product_id"] for r in rows]
                cnt = Product.query.filter(Product.id.in_(product_ids)).count()
                if cnt != len(set(product_ids)):
                    raise ValueError("存在无效的产品。")

                # 更新头
                preplan.plan_date = plan_date
                preplan.customer_id = int(customer_id or 0)
                preplan.remark = remark
                preplan.status = "draft"

                # 删除旧测算结果
                db.session.query(ProductionComponentNeed).filter_by(
                    preplan_id=preplan_id
                ).delete(synchronize_session=False)
                db.session.query(ProductionWorkOrder).filter_by(
                    preplan_id=preplan_id
                ).delete(synchronize_session=False)
                inventory_svc.delete_reservations_for_preplan(preplan_id=preplan_id)
                db.session.flush()

                # 重建明细
                ProductionPreplanLine.query.filter_by(preplan_id=preplan_id).delete(
                    synchronize_session=False
                )
                db.session.flush()

                pmap = {p.id: p for p in Product.query.filter(Product.id.in_(set(product_ids))).all()}
                line_no = 1
                for r in rows:
                    p = pmap.get(r["product_id"])
                    db.session.add(
                        ProductionPreplanLine(
                            preplan_id=preplan_id,
                            line_no=line_no,
                            source_type="manual",
                            source_order_item_id=None,
                            product_id=r["product_id"],
                            quantity=r["quantity"],
                            unit=(p.base_unit if p else None),
                            remark=r.get("remark"),
                        )
                    )
                    line_no += 1

                db.session.commit()
                flash("预生产计划已更新。", "success")
                return redirect(url_for("main.production_preplan_detail", preplan_id=preplan_id))
            except ValueError as e:
                db.session.rollback()
                flash(str(e), "danger")
            except IntegrityError:
                db.session.rollback()
                flash("保存失败：数据冲突。", "danger")

        products = Product.query.order_by(Product.product_code).all()
        customers = Customer.query.order_by(Customer.customer_code).all()
        lines = list(preplan.lines or [])
        return render_template(
            "production/preplan_form.html",
            mode="edit",
            preplan=preplan,
            lines=lines,
            products=products,
            customers=customers,
        )

    # ----------------------------
    # 删除
    # ----------------------------
    @bp.route("/production/preplans/<int:preplan_id>/delete", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.preplan.action.delete")
    def production_preplan_delete(preplan_id: int):
        try:
            preplan = db.session.get(ProductionPreplan, preplan_id)
            if not preplan:
                flash("预生产计划不存在。", "warning")
                return redirect(url_for("main.production_preplan_list"))

            # 删除测算结果与明细
            inventory_svc.delete_reservations_for_preplan(preplan_id=preplan_id)
            db.session.query(ProductionComponentNeed).filter_by(preplan_id=preplan_id).delete(
                synchronize_session=False
            )
            db.session.query(ProductionWorkOrder).filter_by(preplan_id=preplan_id).delete(
                synchronize_session=False
            )
            ProductionPreplanLine.query.filter_by(preplan_id=preplan_id).delete(
                synchronize_session=False
            )
            db.session.delete(preplan)
            db.session.commit()
            flash("预生产计划已删除。", "success")
        except Exception:
            db.session.rollback()
            flash("删除失败，请重试。", "danger")
        return redirect(url_for("main.production_preplan_list"))

    # ----------------------------
    # 测算：合并预计划 + 订单缺货（生成新的测算预生产计划）
    # ----------------------------
    @bp.route("/production/calc", methods=["GET", "POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def production_calc():
        if request.method == "POST":
            try:
                plan_date = _parse_plan_date(request.form.get("plan_date"))
                if not plan_date:
                    raise ValueError("请选择计划日期。")

                customer_id = request.form.get("customer_id", type=int) or 0
                if not customer_id:
                    raise ValueError("请选择客户。")

                base_preplan_id = request.form.get("preplan_id", type=int)
                order_id = request.form.get("order_id", type=int)
                remark = (request.form.get("remark") or "").strip() or None

                new_preplan = ProductionPreplan(
                    source_type="combined",
                    plan_date=plan_date,
                    customer_id=int(customer_id),
                    status="draft",
                    remark=remark,
                    created_by=current_user.id,
                )
                db.session.add(new_preplan)
                db.session.flush()

                line_no = 1

                if base_preplan_id:
                    base_preplan = _require_preplan_with_lines(base_preplan_id)
                    for ln in sorted(list(base_preplan.lines or []), key=lambda x: x.line_no):
                        db.session.add(
                            ProductionPreplanLine(
                                preplan_id=new_preplan.id,
                                line_no=line_no,
                                source_type=ln.source_type or "manual",
                                source_order_item_id=ln.source_order_item_id,
                                product_id=ln.product_id,
                                quantity=ln.quantity,
                                unit=ln.unit,
                                remark=ln.remark,
                            )
                        )
                        line_no += 1

                # 订单缺货：remaining > 0 的行
                pending_items = delivery_svc.get_pending_order_items(
                    customer_id=customer_id, order_id=order_id
                )
                if not pending_items:
                    flash("未发现订单缺货（remaining <= 0）。", "warning")
                    db.session.rollback()
                    return redirect(url_for("main.production_preplan_list"))

                for x in pending_items:
                    oi = x.get("order_item")
                    rem = x.get("remaining_qty") or 0
                    if not oi or rem <= 0:
                        continue
                    if not getattr(oi, "customer_product", None) or not getattr(
                        oi.customer_product, "product_id", None
                    ):
                        continue
                    product_id = int(oi.customer_product.product_id)

                    db.session.add(
                        ProductionPreplanLine(
                            preplan_id=new_preplan.id,
                            line_no=line_no,
                            source_type="order_item",
                            source_order_item_id=oi.id,
                            product_id=product_id,
                            quantity=_parse_decimal(rem, default=Decimal(0)) or Decimal(0),
                            unit=(oi.unit or oi.customer_product.unit),
                            remark=None,
                        )
                    )
                    line_no += 1

                if line_no <= 1:
                    raise ValueError("合并后的预生产计划明细为空，无法测算。")

                db.session.commit()
                production_svc.measure_production_for_preplan(
                    preplan_id=new_preplan.id, created_by=current_user.id
                )
                orchestrator_engine.emit_event(
                    event_type=EVENT_PRODUCTION_MEASURED,
                    biz_key=f"preplan:{new_preplan.id}",
                    payload={
                        "preplan_id": int(new_preplan.id),
                        "source_id": int(new_preplan.id),
                        "version": int(datetime.now().timestamp()),
                        "source": "routes_production.production_calc",
                    },
                )
                db.session.commit()
                flash("生产测算已生成工作单与缺料明细。", "success")
                return redirect(
                    url_for("main.production_preplan_detail", preplan_id=new_preplan.id)
                )
            except ValueError as e:
                db.session.rollback()
                flash(str(e), "danger")
            except IntegrityError:
                db.session.rollback()
                flash("保存失败：数据冲突。", "danger")
        customers = Customer.query.order_by(Customer.customer_code).all()
        preplans = ProductionPreplan.query.order_by(ProductionPreplan.id.desc()).limit(50).all()
        return render_template(
            "production/calc.html",
            customers=customers,
            preplans=preplans,
            today=date.today().isoformat(),
        )

    # ----------------------------
    # 详情（测算结果）
    # ----------------------------
    @bp.route("/production/preplans/<int:preplan_id>")
    @login_required
    @menu_required("production_preplan")
    def production_preplan_detail(preplan_id: int):
        preplan = ProductionPreplan.query.options(selectinload(ProductionPreplan.lines)).get_or_404(preplan_id)
        work_orders = (
            ProductionWorkOrder.query.filter_by(preplan_id=preplan_id)
            .options(
                selectinload(ProductionWorkOrder.parent_product),
                selectinload(ProductionWorkOrder.parent_material),
                selectinload(ProductionWorkOrder.operations),
                selectinload(ProductionWorkOrder.component_needs).selectinload(
                    ProductionComponentNeed.child_material
                ),
            )
            .order_by(ProductionWorkOrder.id.asc())
            .all()
        )
        for wo in work_orders:
            ops = list(wo.operations or [])
            wo.estimated_total_minutes = sum((op.estimated_total_minutes or 0) for op in ops)
        preplan_estimated_total_minutes = sum((getattr(wo, "estimated_total_minutes", 0) or 0) for wo in work_orders)
        raw_material_totals = _raw_material_totals_from_work_orders(work_orders)

        sched_dash = compute_preplan_schedule_dashboard(preplan_id=preplan_id)
        schedule_plan_rows = list_schedule_plan_rows_for_preplan(preplan_id=preplan_id)
        total_planned_minutes = sched_dash.get("sum_planned_minutes") or 0
        preplan_planned_es = sched_dash.get("preplan_planned_es")
        preplan_planned_ef = sched_dash.get("preplan_planned_ef")
        preplan_wall_minutes = sched_dash.get("preplan_wall_minutes")
        wo_planned_span = sched_dash.get("wo_planned_span") or {}
        for wo in work_orders:
            sp = wo_planned_span.get(int(wo.id))
            if sp:
                wo.planned_es = sp.get("planned_es")
                wo.planned_ef = sp.get("planned_ef")
                wo.planned_wall_minutes = sp.get("wall_minutes")
            else:
                wo.planned_es = None
                wo.planned_ef = None
                wo.planned_wall_minutes = None

        if current_user_can_cap("production.preplan.cost.view"):
            total_cost_opt = (
                db.session.query(db.func.coalesce(db.func.sum(ProductionCostPlanDetail.amount), 0))
                .filter(
                    ProductionCostPlanDetail.preplan_id == preplan_id,
                    ProductionCostPlanDetail.scenario == "optimized",
                )
                .scalar()
            )
            total_cost_asg = (
                db.session.query(db.func.coalesce(db.func.sum(ProductionCostPlanDetail.amount), 0))
                .filter(
                    ProductionCostPlanDetail.preplan_id == preplan_id,
                    ProductionCostPlanDetail.scenario == "assigned",
                )
                .scalar()
            )
        else:
            total_cost_opt = None
            total_cost_asg = None

        company_id_ctx = _company_id_from_preplan(preplan)
        viewer_dept_id = resolve_user_hr_department_id(current_user.id)
        budget_options_by_op = _budget_options_for_operations(
            work_orders, company_id_ctx, viewer_dept_id=viewer_dept_id
        )

        # 机台排班时间窗（用于“报工”选择 booking）
        start_dt = datetime.combine(preplan.plan_date, time.min)
        end_dt = start_dt + timedelta(days=1)
        bookings_by_wo_id: Dict[int, List[MachineScheduleBooking]] = {}
        for wo in work_orders:
            machine_type_ids = {
                int(op.machine_type_id)
                for op in (wo.operations or [])
                if (getattr(op, "resource_kind", None) == "machine_type") and int(getattr(op, "machine_type_id", 0) or 0) > 0
            }
            if not machine_type_ids:
                bookings_by_wo_id[int(wo.id)] = []
                continue

            bq = (
                MachineScheduleBooking.query.options(selectinload(MachineScheduleBooking.machine))
                .join(Machine, Machine.id == MachineScheduleBooking.machine_id)
                .filter(
                    Machine.machine_type_id.in_(machine_type_ids),
                    Machine.status == "enabled",
                    MachineScheduleBooking.state == "available",
                    MachineScheduleBooking.start_at < end_dt,
                    MachineScheduleBooking.end_at > start_dt,
                )
            )
            if viewer_dept_id:
                vid = int(viewer_dept_id)
                bq = bq.filter(
                    db.or_(
                        Machine.owning_hr_department_id == 0,
                        Machine.owning_hr_department_id == vid,
                    )
                )
            bookings = (
                bq.order_by(MachineScheduleBooking.start_at.asc(), MachineScheduleBooking.id.asc())
                .limit(2000)
                .all()
            )
            bookings_by_wo_id[int(wo.id)] = bookings

        return render_template(
            "production/preplan_detail.html",
            preplan=preplan,
            work_orders=work_orders,
            raw_material_totals=raw_material_totals,
            preplan_estimated_total_minutes=preplan_estimated_total_minutes,
            preplan_planned_total_minutes=total_planned_minutes,
            preplan_planned_es=preplan_planned_es,
            preplan_planned_ef=preplan_planned_ef,
            preplan_wall_minutes=preplan_wall_minutes,
            schedule_plan_rows=schedule_plan_rows,
            preplan_total_cost=total_cost_opt,
            preplan_total_cost_optimized=total_cost_opt,
            preplan_total_cost_assigned=total_cost_asg,
            budget_options_by_op=budget_options_by_op,
            bookings_by_wo_id=bookings_by_wo_id,
        )

    # ----------------------------
    # 测算运行（已存在预生产计划）
    # ----------------------------
    @bp.route("/production/preplans/<int:preplan_id>/measure", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def production_preplan_measure(preplan_id: int):
        try:
            production_svc.measure_production_for_preplan(
                preplan_id=preplan_id, created_by=current_user.id
            )
            orchestrator_engine.emit_event(
                event_type=EVENT_PRODUCTION_MEASURED,
                biz_key=f"preplan:{preplan_id}",
                payload={
                    "preplan_id": int(preplan_id),
                    "source_id": int(preplan_id),
                    "version": int(datetime.now().timestamp()),
                    "source": "routes_production.production_preplan_measure",
                },
            )
            db.session.commit()
            flash("生产测算已完成。", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"测算失败：{e}", "danger")
        return redirect(
            url_for("main.production_preplan_detail", preplan_id=preplan_id)
        )

    @bp.route("/production/preplans/<int:preplan_id>/schedule-manual", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def production_preplan_schedule_manual(preplan_id: int):
        preplan = db.session.get(ProductionPreplan, preplan_id)
        if not preplan:
            flash("预生产计划不存在。", "warning")
            return redirect(url_for("main.production_preplan_list"))
        try:
            errs = production_preplan_schedule_manual_svc.apply_manual_plan_from_form(
                preplan_id=preplan_id,
                form_data=request.form,
                user_id=int(current_user.id),
            )
            if errs:
                db.session.rollback()
                for msg in errs[:20]:
                    flash(msg, "danger")
            else:
                flash("人工排程已保存。", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"保存失败：{e}", "danger")
        return redirect(url_for("main.production_preplan_detail", preplan_id=preplan_id))

    @bp.route("/production/preplans/<int:preplan_id>/schedule-confirm", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def production_preplan_schedule_confirm(preplan_id: int):
        preplan = db.session.get(ProductionPreplan, preplan_id)
        if not preplan:
            flash("预生产计划不存在。", "warning")
            return redirect(url_for("main.production_preplan_list"))
        try:
            errs = production_preplan_schedule_manual_svc.confirm_preplan_schedule(
                preplan_id=preplan_id,
                user_id=int(current_user.id),
            )
            if errs:
                db.session.rollback()
                for msg in errs[:20]:
                    flash(msg, "danger")
            else:
                flash("计划已确认并同步到机台/人员排班。", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"确认失败：{e}", "danger")
        return redirect(url_for("main.production_preplan_detail", preplan_id=preplan_id))

    @bp.route("/production/work-orders/<int:work_order_id>/report", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def production_work_order_report(work_order_id: int):
        wo = db.session.get(ProductionWorkOrder, work_order_id)
        if not wo:
            flash("工作单不存在。", "danger")
            return redirect(url_for("main.production_preplan_list"))
        if wo.status not in ("planned", "released", "in_progress"):
            flash("当前状态不允许报工。", "warning")
            return redirect(url_for("main.production_preplan_detail", preplan_id=wo.preplan_id))

        # 报工关联机台排产 booking 与实际产量
        booking_id = request.form.get("booking_id", type=int) or 0
        actual_produced_qty = _parse_decimal_non_negative(
            request.form.get("actual_produced_qty"), default=Decimal(0)
        )
        if booking_id <= 0:
            flash("请先选择机台排班时间窗。", "danger")
            return redirect(url_for("main.production_preplan_detail", preplan_id=wo.preplan_id))
        if actual_produced_qty is None or actual_produced_qty < 0:
            flash("本次实际产量填写不正确。", "danger")
            return redirect(url_for("main.production_preplan_detail", preplan_id=wo.preplan_id))

        booking = db.session.get(MachineScheduleBooking, booking_id)
        if not booking:
            flash("选择的时间窗不存在。", "danger")
            return redirect(url_for("main.production_preplan_detail", preplan_id=wo.preplan_id))
        if (booking.state or "").strip() != "available":
            flash("选择的时间窗不是可用状态。", "danger")
            return redirect(url_for("main.production_preplan_detail", preplan_id=wo.preplan_id))

        # 校验 booking 的机台类型是否包含在该工作单的机台资源类型中
        expected_machine_type_ids = {
            int(r.machine_type_id)
            for r in ProductionWorkOrderOperation.query.filter(
                ProductionWorkOrderOperation.work_order_id == wo.id,
                ProductionWorkOrderOperation.resource_kind == "machine_type",
                ProductionWorkOrderOperation.machine_type_id > 0,
            ).all()
        }
        machine = db.session.get(Machine, booking.machine_id)
        if not machine or machine.status != "enabled":
            flash("选择的机台不存在或不可用。", "danger")
            return redirect(url_for("main.production_preplan_detail", preplan_id=wo.preplan_id))
        if expected_machine_type_ids and int(machine.machine_type_id) not in expected_machine_type_ids:
            flash("所选时间窗的机台不匹配该工作单的机台资源类型。", "danger")
            return redirect(url_for("main.production_preplan_detail", preplan_id=wo.preplan_id))

        # dispatch log：幂等保护
        dispatch_log = MachineScheduleDispatchLog.query.filter_by(booking_id=booking_id).first()
        if dispatch_log and (dispatch_log.state or "").strip() == "reported":
            flash("该时间窗已报工，无法重复累计。", "warning")
            return redirect(url_for("main.production_preplan_detail", preplan_id=wo.preplan_id))

        duration_seconds = int((booking.end_at - booking.start_at).total_seconds())
        runtime_hours = quantize_decimal(Decimal(duration_seconds) / Decimal(3600))

        if not dispatch_log:
            dispatch_log = MachineScheduleDispatchLog(
                machine_id=booking.machine_id,
                booking_id=booking.id,
                dispatch_start_at=booking.start_at,
                dispatch_end_at=booking.end_at,
                planned_runtime_hours=runtime_hours,
                state="reported",
                actual_produced_qty=actual_produced_qty,
                actual_runtime_hours=runtime_hours,
                work_order_id=wo.id,
                reported_by=int(current_user.id),
                reported_at=datetime.now(),
            )
            db.session.add(dispatch_log)
        else:
            dispatch_log.state = "reported"
            dispatch_log.actual_produced_qty = actual_produced_qty
            dispatch_log.actual_runtime_hours = runtime_hours
            dispatch_log.work_order_id = wo.id
            dispatch_log.reported_by = int(current_user.id)
            dispatch_log.reported_at = datetime.now()

        # 累计写回（只在 dispatch_log 未报工时执行）
        machine.machine_accum_produced_qty = machine.machine_accum_produced_qty + actual_produced_qty
        machine.machine_accum_runtime_hours = machine.machine_accum_runtime_hours + runtime_hours
        db.session.add(machine)

        wo.status = "in_progress"
        db.session.add(wo)
        order_id = _resolve_order_id_by_work_order(wo)
        if order_id:
            orchestrator_engine.emit_event(
                event_type=EVENT_PRODUCTION_OPERATION_REPORTED,
                biz_key=f"order:{order_id}",
                payload={
                    "order_id": order_id,
                    "work_order_id": int(wo.id),
                    "source_id": int(wo.id),
                    "version": int(datetime.now().timestamp()),
                    "source": "routes_production.production_work_order_report.operation",
                },
            )
            evt = orchestrator_engine.emit_event(
                event_type=EVENT_PRODUCTION_REPORTED,
                biz_key=f"order:{order_id}",
                payload={
                    "order_id": order_id,
                    "source_id": int(wo.id),
                    "version": int(datetime.now().timestamp()),
                    "source": "routes_production.production_work_order_report",
                },
            )
            orchestrator_engine.process_event(int(evt.id), created_by=int(current_user.id))
        else:
            orchestrator_engine.log_manual_audit(
                level="warn",
                message="production_reported_without_order",
                detail={"work_order_id": int(wo.id), "preplan_id": int(wo.preplan_id)},
            )
        db.session.commit()
        flash("报工成功。", "success")
        return redirect(url_for("main.production_preplan_detail", preplan_id=wo.preplan_id))

    @bp.route("/production/work-orders/<int:work_order_id>/quality-pass", methods=["POST"])
    @login_required
    @menu_required("production_preplan")
    @capability_required("production.calc.action.run")
    def production_work_order_quality_pass(work_order_id: int):
        wo = db.session.get(ProductionWorkOrder, work_order_id)
        if not wo:
            flash("工作单不存在。", "danger")
            return redirect(url_for("main.production_preplan_list"))
        if wo.status not in ("in_progress", "released", "planned"):
            flash("当前状态不允许质检通过。", "warning")
            return redirect(url_for("main.production_preplan_detail", preplan_id=wo.preplan_id))
        wo.status = "closed"
        db.session.add(wo)
        order_id = _resolve_order_id_by_work_order(wo)
        if order_id:
            orchestrator_engine.emit_event(
                event_type=EVENT_QUALITY_INSPECTION_STARTED,
                biz_key=f"order:{int(order_id)}",
                payload={
                    "order_id": int(order_id),
                    "source_id": int(wo.id),
                    "version": int(datetime.now().timestamp()),
                    "source": "routes_production.production_work_order_quality_pass.started",
                },
            )
            evt = orchestrator_engine.emit_event(
                event_type=EVENT_QUALITY_PASSED,
                biz_key=f"order:{order_id}",
                payload={
                    "order_id": order_id,
                    "source_id": int(wo.id),
                    "version": int(datetime.now().timestamp()),
                    "source": "routes_production.production_work_order_quality_pass",
                },
            )
            orchestrator_engine.process_event(int(evt.id), created_by=int(current_user.id))
        else:
            orchestrator_engine.log_manual_audit(
                level="warn",
                message="quality_passed_without_order",
                detail={"work_order_id": int(wo.id), "preplan_id": int(wo.preplan_id)},
            )
        db.session.commit()
        flash("质检通过已记录。", "success")
        return redirect(url_for("main.production_preplan_detail", preplan_id=wo.preplan_id))

    # ----------------------------
    # 生产事故
    # ----------------------------
    @bp.route("/production/incidents")
    @login_required
    @menu_required("production_incident")
    def production_incident_list():
        q = (request.args.get("q") or "").strip()
        query = ProductionIncident.query
        if q:
            like = f"%{q}%"
            query = query.filter(
                db.or_(
                    ProductionIncident.title.like(like),
                    ProductionIncident.incident_no.like(like),
                    ProductionIncident.workshop.like(like),
                    ProductionIncident.d2_problem.like(like),
                )
            )
        incidents = query.order_by(ProductionIncident.occurred_at.desc()).limit(200).all()
        return render_template("production/incident_list.html", incidents=incidents, q=q)

    @bp.route("/production/incidents/new", methods=["GET", "POST"])
    @login_required
    @menu_required("production_incident")
    @capability_required("production_incident.action.create")
    def production_incident_new():
        if request.method == "POST":
            try:
                title = _text_or_none(request.form.get("title"))
                if not title:
                    raise ValueError("请填写标题。")
                occurred_at = _parse_occurred_at(request.form.get("occurred_at"))
                if not occurred_at:
                    raise ValueError("请填写发生时间。")
                incident_no = _text_or_none(request.form.get("incident_no"))
                inc = ProductionIncident(
                    incident_no=incident_no,
                    title=title,
                    occurred_at=occurred_at,
                    workshop=_text_or_none(request.form.get("workshop")),
                    severity=_text_or_none(request.form.get("severity")),
                    status=(request.form.get("status") or "open").strip() or "open",
                    remark=_text_or_none(request.form.get("remark")),
                    d1_team=_text_or_none(request.form.get("d1_team")),
                    d2_problem=_text_or_none(request.form.get("d2_problem")),
                    d3_containment=_text_or_none(request.form.get("d3_containment")),
                    d4_root_cause=_text_or_none(request.form.get("d4_root_cause")),
                    d5_corrective=_text_or_none(request.form.get("d5_corrective")),
                    d6_implementation=_text_or_none(request.form.get("d6_implementation")),
                    d7_prevention=_text_or_none(request.form.get("d7_prevention")),
                    d8_recognition=_text_or_none(request.form.get("d8_recognition")),
                    created_by=current_user.id,
                )
                db.session.add(inc)
                db.session.flush()
                if not inc.incident_no:
                    inc.incident_no = f"INC-{inc.id:05d}"
                orchestrator_engine.emit_event(
                    event_type=EVENT_MACHINE_ABNORMAL,
                    biz_key=f"incident:{int(inc.id)}",
                    payload={
                        "incident_id": int(inc.id),
                        "severity": (inc.severity or "M"),
                        "source_id": int(inc.id),
                        "version": int(datetime.now().timestamp()),
                        "source": "routes_production.production_incident_new",
                    },
                )
                db.session.commit()
                flash("生产事故已保存。", "success")
                return redirect(url_for("main.production_incident_detail", incident_id=inc.id))
            except ValueError as e:
                db.session.rollback()
                flash(str(e), "danger")
            except IntegrityError:
                db.session.rollback()
                flash("保存失败：事故编号重复或数据冲突。", "danger")

        return render_template("production/incident_form.html", mode="new", incident=None)

    @bp.route("/production/incidents/<int:incident_id>")
    @login_required
    @menu_required("production_incident")
    def production_incident_detail(incident_id: int):
        inc = db.session.get(ProductionIncident, incident_id)
        if not inc:
            flash("记录不存在。", "warning")
            return redirect(url_for("main.production_incident_list"))
        creator = db.session.get(User, inc.created_by)
        creator_name = (creator.name or creator.username) if creator else str(inc.created_by)
        return render_template(
            "production/incident_detail.html",
            incident=inc,
            creator_name=creator_name,
        )

    @bp.route("/production/incidents/<int:incident_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("production_incident")
    @capability_required("production_incident.action.edit")
    def production_incident_edit(incident_id: int):
        inc = db.session.get(ProductionIncident, incident_id)
        if not inc:
            flash("记录不存在。", "warning")
            return redirect(url_for("main.production_incident_list"))

        if request.method == "POST":
            try:
                title = _text_or_none(request.form.get("title"))
                if not title:
                    raise ValueError("请填写标题。")
                occurred_at = _parse_occurred_at(request.form.get("occurred_at"))
                if not occurred_at:
                    raise ValueError("请填写发生时间。")
                new_no = _text_or_none(request.form.get("incident_no"))
                inc.incident_no = new_no
                inc.title = title
                inc.occurred_at = occurred_at
                inc.workshop = _text_or_none(request.form.get("workshop"))
                inc.severity = _text_or_none(request.form.get("severity"))
                inc.status = (request.form.get("status") or "open").strip() or "open"
                inc.remark = _text_or_none(request.form.get("remark"))
                inc.d1_team = _text_or_none(request.form.get("d1_team"))
                inc.d2_problem = _text_or_none(request.form.get("d2_problem"))
                inc.d3_containment = _text_or_none(request.form.get("d3_containment"))
                inc.d4_root_cause = _text_or_none(request.form.get("d4_root_cause"))
                inc.d5_corrective = _text_or_none(request.form.get("d5_corrective"))
                inc.d6_implementation = _text_or_none(request.form.get("d6_implementation"))
                inc.d7_prevention = _text_or_none(request.form.get("d7_prevention"))
                inc.d8_recognition = _text_or_none(request.form.get("d8_recognition"))
                db.session.flush()
                if not inc.incident_no:
                    inc.incident_no = f"INC-{inc.id:05d}"
                if inc.status == "closed":
                    orchestrator_engine.emit_event(
                        event_type=EVENT_MACHINE_RECOVERED,
                        biz_key=f"incident:{int(inc.id)}",
                        payload={
                            "incident_id": int(inc.id),
                            "source_id": int(inc.id),
                            "version": int(datetime.now().timestamp()),
                            "source": "routes_production.production_incident_edit",
                        },
                    )
                elif inc.status in ("open", "in_progress"):
                    orchestrator_engine.emit_event(
                        event_type=EVENT_MACHINE_ABNORMAL,
                        biz_key=f"incident:{int(inc.id)}",
                        payload={
                            "incident_id": int(inc.id),
                            "severity": (inc.severity or "M"),
                            "source_id": int(inc.id),
                            "version": int(datetime.now().timestamp()),
                            "source": "routes_production.production_incident_edit",
                        },
                    )
                db.session.commit()
                flash("已更新。", "success")
                return redirect(url_for("main.production_incident_detail", incident_id=incident_id))
            except ValueError as e:
                db.session.rollback()
                flash(str(e), "danger")
            except IntegrityError:
                db.session.rollback()
                flash("保存失败：事故编号重复或数据冲突。", "danger")

        return render_template("production/incident_form.html", mode="edit", incident=inc)

    @bp.route("/production/incidents/<int:incident_id>/delete", methods=["POST"])
    @login_required
    @menu_required("production_incident")
    @capability_required("production_incident.action.delete")
    def production_incident_delete(incident_id: int):
        inc = db.session.get(ProductionIncident, incident_id)
        if not inc:
            flash("记录不存在。", "warning")
        else:
            try:
                db.session.delete(inc)
                db.session.commit()
                flash("已删除。", "success")
            except Exception:
                db.session.rollback()
                flash("删除失败。", "danger")
        return redirect(url_for("main.production_incident_list"))

    @bp.route("/production/incidents/<int:incident_id>/8d-print")
    @login_required
    @menu_required("production_incident")
    @capability_required("production_incident.report.8d")
    def production_incident_8d_print(incident_id: int):
        inc = db.session.get(ProductionIncident, incident_id)
        if not inc:
            flash("记录不存在。", "warning")
            return redirect(url_for("main.production_incident_list"))
        creator = db.session.get(User, inc.created_by)
        creator_name = (creator.name or creator.username) if creator else str(inc.created_by)
        return render_template(
            "production/incident_8d_print.html",
            incident=inc,
            creator_name=creator_name,
        )

    @bp.route("/production/incidents/<int:incident_id>/8d-export.xlsx")
    @login_required
    @menu_required("production_incident")
    @capability_required("production_incident.report.8d")
    def production_incident_8d_export(incident_id: int):
        from openpyxl import Workbook

        inc = db.session.get(ProductionIncident, incident_id)
        if not inc:
            flash("记录不存在。", "warning")
            return redirect(url_for("main.production_incident_list"))
        wb = Workbook()
        ws = wb.active
        ws.title = "8D"
        no = inc.incident_no or f"#{inc.id}"
        rows = [
            ("8D 报告", no),
            ("标题", inc.title),
            ("发生时间", inc.occurred_at.strftime("%Y-%m-%d %H:%M") if inc.occurred_at else ""),
            ("车间/地点", inc.workshop or ""),
            ("严重程度", inc.severity or ""),
            ("状态", inc.status or ""),
            ("备注/D0", inc.remark or ""),
            ("D1 小组", inc.d1_team or ""),
            ("D2 问题描述", inc.d2_problem or ""),
            ("D3 临时措施", inc.d3_containment or ""),
            ("D4 根本原因", inc.d4_root_cause or ""),
            ("D5 永久纠正措施", inc.d5_corrective or ""),
            ("D6 实施与验证", inc.d6_implementation or ""),
            ("D7 预防再发", inc.d7_prevention or ""),
            ("D8 总结与表彰", inc.d8_recognition or ""),
        ]
        for r in rows:
            ws.append(list(r))
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        fname = f"8D_{no}.xlsx".replace("/", "-")
        return send_file(
            buf,
            as_attachment=True,
            download_name=fname,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # ----------------------------
    # 工序管理（模板 + 产品路由覆写）
    # ----------------------------

    @bp.route("/production/process-templates")
    @login_required
    @menu_required("production_process")
    def production_process_template_list():
        keyword = (request.args.get("keyword") or "").strip()
        q = ProductionProcessTemplate.query
        if keyword:
            q = q.filter(
                db.or_(
                    ProductionProcessTemplate.name.contains(keyword),
                    ProductionProcessTemplate.version.contains(keyword),
                    ProductionProcessTemplate.remark.contains(keyword),
                )
            )
        rows = q.order_by(ProductionProcessTemplate.id.desc()).limit(200).all()
        return render_template("production/process_template_list.html", rows=rows, keyword=keyword)

    @bp.route("/production/process-templates/new", methods=["GET", "POST"])
    @login_required
    @menu_required("production_process")
    @capability_required("production.process_template.action.create")
    def production_process_template_new():
        machine_types = MachineType.query.order_by(MachineType.name.asc()).all()
        work_types = _production_work_types()
        if request.method == "POST":
            try:
                name = (request.form.get("name") or "").strip()
                if not name:
                    raise ValueError("请填写模板名称。")
                version = (request.form.get("version") or "").strip() or "v1"
                is_active = (request.form.get("is_active") or "1") == "1"
                remark = (request.form.get("remark") or "").strip() or None

                steps = _parse_process_template_steps_from_form()
                edges = _parse_process_edges_from_form(
                    expected_step_nos=[x["step_no"] for x in steps]
                )

                tpl = ProductionProcessTemplate(
                    name=name,
                    version=version,
                    is_active=is_active,
                    remark=remark,
                    created_by=current_user.id,
                )
                db.session.add(tpl)
                db.session.flush()

                for st in steps:
                    db.session.add(
                        ProductionProcessTemplateStep(
                            template_id=tpl.id,
                            step_no=st["step_no"],
                            step_code=st["step_code"],
                            step_name=st["step_name"],
                            resource_kind=st["resource_kind"],
                            machine_type_id=st["machine_type_id"],
                            hr_department_id=st["hr_department_id"],
                            hr_work_type_id=st["hr_work_type_id"],
                            setup_minutes=st["setup_minutes"],
                            run_minutes_per_unit=st["run_minutes_per_unit"],
                            remark=st["remark"],
                        )
                    )
                _sync_process_graph_from_steps(template_id=tpl.id, steps=steps, edges=edges)
                db.session.commit()
                flash("工序模板已新增。", "success")
                return redirect(url_for("main.production_process_template_list"))
            except ValueError as e:
                db.session.rollback()
                flash(str(e), "danger")

        return render_template(
            "production/process_template_form.html",
            mode="new",
            row=None,
            steps=[],
            edge_rows=[],
            machine_types=machine_types,
            work_types=work_types,
        )

    @bp.route("/production/process-templates/<int:template_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("production_process")
    @capability_required("production.process_template.action.edit")
    def production_process_template_edit(template_id: int):
        tpl = db.session.get(ProductionProcessTemplate, template_id)
        if not tpl:
            flash("模板不存在。", "warning")
            return redirect(url_for("main.production_process_template_list"))

        machine_types = MachineType.query.order_by(MachineType.name.asc()).all()
        work_types = _production_work_types()

        if request.method == "POST":
            try:
                name = (request.form.get("name") or "").strip()
                if not name:
                    raise ValueError("请填写模板名称。")
                version = (request.form.get("version") or "").strip() or "v1"
                is_active = (request.form.get("is_active") or "1") == "1"
                remark = (request.form.get("remark") or "").strip() or None

                steps = _parse_process_template_steps_from_form()
                edges = _parse_process_edges_from_form(
                    expected_step_nos=[x["step_no"] for x in steps]
                )

                tpl.name = name
                tpl.version = version
                tpl.is_active = is_active
                tpl.remark = remark
                db.session.flush()

                ProductionProcessTemplateStep.query.filter_by(template_id=tpl.id).delete(synchronize_session=False)
                db.session.flush()

                for st in steps:
                    db.session.add(
                        ProductionProcessTemplateStep(
                            template_id=tpl.id,
                            step_no=st["step_no"],
                            step_code=st["step_code"],
                            step_name=st["step_name"],
                            resource_kind=st["resource_kind"],
                            machine_type_id=st["machine_type_id"],
                            hr_department_id=st["hr_department_id"],
                            hr_work_type_id=st["hr_work_type_id"],
                            setup_minutes=st["setup_minutes"],
                            run_minutes_per_unit=st["run_minutes_per_unit"],
                            remark=st["remark"],
                        )
                    )
                _sync_process_graph_from_steps(template_id=tpl.id, steps=steps, edges=edges)
                db.session.commit()
                flash("工序模板已更新。", "success")
                return redirect(url_for("main.production_process_template_list"))
            except ValueError as e:
                db.session.rollback()
                flash(str(e), "danger")

        steps_db = (
            ProductionProcessTemplateStep.query.filter_by(template_id=tpl.id)
            .order_by(ProductionProcessTemplateStep.step_no.asc(), ProductionProcessTemplateStep.id.asc())
            .all()
        )
        steps = [
            {
                "id": st.id,
                "step_no": st.step_no,
                "step_code": st.step_code,
                "step_name": st.step_name,
                "resource_kind": st.resource_kind,
                "machine_type_id": st.machine_type_id,
                "work_type_id": st.effective_work_type_id,
                "setup_minutes": st.setup_minutes,
                "run_minutes_per_unit": st.run_minutes_per_unit,
                "remark": st.remark,
            }
            for st in steps_db
        ]
        node_rows = ProductionProcessNode.query.filter_by(template_id=tpl.id).all()
        node_step_map = {
            int(n.id): int(n.step_no) for n in node_rows if n.step_no is not None
        }
        edge_rows_db = ProductionProcessEdge.query.filter_by(template_id=tpl.id).all()
        edge_rows = []
        for e in edge_rows_db:
            from_step = node_step_map.get(int(e.from_node_id))
            to_step = node_step_map.get(int(e.to_node_id))
            if from_step is None or to_step is None:
                continue
            edge_rows.append(
                {
                    "from_step_no": int(from_step),
                    "to_step_no": int(to_step),
                    "edge_type": str(e.edge_type or "fs").lower(),
                    "lag_minutes": int(e.lag_minutes or 0),
                    "remark": e.remark or "",
                }
            )

        return render_template(
            "production/process_template_form.html",
            mode="edit",
            row=tpl,
            steps=steps,
            edge_rows=edge_rows,
            machine_types=machine_types,
            work_types=work_types,
        )

    @bp.route("/production/process-templates/<int:template_id>/delete", methods=["POST"])
    @login_required
    @menu_required("production_process")
    @capability_required("production.process_template.action.delete")
    def production_process_template_delete(template_id: int):
        tpl = db.session.get(ProductionProcessTemplate, template_id)
        if not tpl:
            flash("模板不存在。", "warning")
            return redirect(url_for("main.production_process_template_list"))

        used = ProductionProductRouting.query.filter_by(template_id=tpl.id, is_active=True).first()
        if used:
            flash("该模板已被产品路由启用，无法删除。", "danger")
            return redirect(url_for("main.production_process_template_list"))

        ProductionProcessEdge.query.filter_by(template_id=tpl.id).delete(synchronize_session=False)
        ProductionProcessNode.query.filter_by(template_id=tpl.id).delete(synchronize_session=False)
        ProductionProcessTemplateStep.query.filter_by(template_id=tpl.id).delete(synchronize_session=False)
        db.session.delete(tpl)
        db.session.commit()
        flash("工序模板已删除。", "success")
        return redirect(url_for("main.production_process_template_list"))

    @bp.route("/production/product-routings")
    @login_required
    @menu_required("production_process")
    def production_product_routing_list():
        target_kind = (request.args.get("target_kind") or "finished").strip().lower()
        if target_kind not in ("finished", "semi"):
            target_kind = "finished"
        keyword = (request.args.get("keyword") or "").strip()
        if target_kind == "finished":
            q = Product.query
            if keyword:
                q = q.filter(
                    db.or_(Product.product_code.contains(keyword), Product.name.contains(keyword))
                )
            items = q.order_by(Product.product_code.asc()).limit(500).all()
        else:
            q = SemiMaterial.query.filter_by(kind="semi")
            if keyword:
                q = q.filter(
                    db.or_(SemiMaterial.code.contains(keyword), SemiMaterial.name.contains(keyword))
                )
            items = q.order_by(SemiMaterial.code.asc(), SemiMaterial.id.asc()).limit(500).all()

        routings = ProductionProductRouting.query.filter_by(
            target_kind=target_kind, is_active=True
        ).all()
        routing_map: Dict[int, ProductionProductRouting] = {
            r.effective_target_id: r for r in routings if r.effective_target_id > 0
        }
        template_ids = sorted({r.template_id for r in routings})
        templates = ProductionProcessTemplate.query.filter(ProductionProcessTemplate.id.in_(template_ids)).all() if template_ids else []
        template_map: Dict[int, ProductionProcessTemplate] = {t.id: t for t in templates}

        return render_template(
            "production/product_routing_list.html",
            target_kind=target_kind,
            items=items,
            routing_map=routing_map,
            template_map=template_map,
            keyword=keyword,
        )

    @bp.route("/production/product-routings/<int:product_id>/edit", methods=["GET"])
    @login_required
    @menu_required("production_process")
    @capability_required("production.process_routing.action.edit")
    def production_product_routing_edit_legacy(product_id: int):
        return redirect(
            url_for(
                "main.production_product_routing_edit",
                target_kind="finished",
                target_id=product_id,
            )
        )

    @bp.route("/production/product-routings/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("production_process")
    @capability_required("production.process_routing.action.edit")
    def production_product_routing_edit():
        target_kind = (request.values.get("target_kind") or "finished").strip().lower()
        if target_kind not in ("finished", "semi"):
            target_kind = "finished"
        target_id = request.values.get("target_id", type=int) or 0
        if target_id <= 0:
            flash("请选择需要配置路由的对象。", "warning")
            return redirect(url_for("main.production_product_routing_list"))

        if target_kind == "finished":
            target_obj = db.session.get(Product, target_id)
            target_label = "成品"
            target_code = target_obj.product_code if target_obj else ""
            target_name = target_obj.name if target_obj else ""
            target_spec = target_obj.spec if target_obj else ""
        else:
            target_obj = SemiMaterial.query.filter_by(id=target_id, kind="semi").first()
            target_label = "半成品"
            target_code = target_obj.code if target_obj else ""
            target_name = target_obj.name if target_obj else ""
            target_spec = target_obj.spec if target_obj else ""
        if not target_obj:
            flash("对象不存在或类型不匹配。", "warning")
            return redirect(url_for("main.production_product_routing_list", target_kind=target_kind))

        machine_types = MachineType.query.order_by(MachineType.name.asc()).all()
        work_types = _production_work_types()
        templates = ProductionProcessTemplate.query.filter_by(is_active=True).order_by(ProductionProcessTemplate.id.desc()).all()
        if not templates:
            flash("请先维护工序模板。", "warning")
            return redirect(url_for("main.production_process_template_list"))

        routing = ProductionProductRouting.query.filter_by(
            target_kind=target_kind,
            target_id=target_id,
        ).first()
        selected_template_id = (
            request.form.get("template_id", type=int)
            or request.args.get("template_id", type=int)
            or (routing.template_id if routing else templates[0].id)
        )

        tpl = db.session.get(ProductionProcessTemplate, selected_template_id)
        if not tpl:
            flash("请选择有效的工序模板。", "danger")
            return redirect(url_for("main.production_process_template_list"))

        steps_db = (
            ProductionProcessTemplateStep.query.filter_by(template_id=tpl.id)
            .order_by(ProductionProcessTemplateStep.step_no.asc(), ProductionProcessTemplateStep.id.asc())
            .all()
        )
        step_nos = [st.step_no for st in steps_db]

        overrides_db: List[ProductionProductRoutingStep] = []
        overrides_map: Dict[int, ProductionProductRoutingStep] = {}
        if routing:
            overrides_db = ProductionProductRoutingStep.query.filter_by(routing_id=routing.id).all()
            overrides_map = {x.template_step_no: x for x in overrides_db}

        if request.method == "POST":
            try:
                if not selected_template_id:
                    raise ValueError("请选择工序模板。")

                if not steps_db:
                    raise ValueError("所选模板没有可用工序步骤。")

                override_rows = _parse_product_routing_step_overrides_from_form(
                    expected_template_step_nos=step_nos
                )

                if routing is None:
                    routing = ProductionProductRouting(
                        target_kind=target_kind,
                        target_id=target_id,
                        product_id=target_id if target_kind == "finished" else 0,
                        template_id=selected_template_id,
                        override_mode="inherit",
                        is_active=True,
                        remark=None,
                        created_by=current_user.id,
                    )
                    db.session.add(routing)
                    db.session.flush()
                else:
                    routing.target_kind = target_kind
                    routing.target_id = target_id
                    routing.product_id = target_id if target_kind == "finished" else 0
                    routing.template_id = selected_template_id
                    routing.is_active = True
                    db.session.flush()

                ProductionProductRoutingStep.query.filter_by(routing_id=routing.id).delete(synchronize_session=False)

                for ov in override_rows:
                    db.session.add(
                        ProductionProductRoutingStep(
                            routing_id=routing.id,
                            template_step_no=ov["template_step_no"],
                            resource_kind_override=ov["resource_kind_override"],
                            machine_type_id_override=ov["machine_type_id_override"],
                            hr_department_id_override=ov["hr_department_id_override"],
                            hr_work_type_id_override=ov["hr_work_type_id_override"],
                            setup_minutes_override=ov["setup_minutes_override"],
                            run_minutes_per_unit_override=ov["run_minutes_per_unit_override"],
                            step_name_override=ov["step_name_override"],
                            remark=ov["remark"],
                        )
                    )

                db.session.commit()
                flash(f"{target_label}路由覆写已保存。", "success")
                return redirect(
                    url_for(
                        "main.production_product_routing_edit",
                        target_kind=target_kind,
                        target_id=target_id,
                    )
                )
            except ValueError as e:
                db.session.rollback()
                flash(str(e), "danger")

        return render_template(
            "production/product_routing_form.html",
            target_kind=target_kind,
            target_id=target_id,
            target_label=target_label,
            target_code=target_code,
            target_name=target_name,
            target_spec=target_spec,
            templates=templates,
            selected_template_id=selected_template_id,
            steps=steps_db,
            overrides_map=overrides_map,
            machine_types=machine_types,
            work_types=work_types,
            routing=routing,
        )

