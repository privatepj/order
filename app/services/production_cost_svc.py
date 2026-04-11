from __future__ import annotations

from decimal import Decimal
from typing import Iterable, List, Optional, Tuple

from sqlalchemy import or_

from app import db
from app.models import (
    Customer,
    HrEmployeeCapability,
    HrPayrollLine,
    HrWorkTypePieceRate,
    Machine,
    MachineType,
    MachineOperatorAllowlist,
    ProductionCostPlanDetail,
    ProductionMaterialPlanDetail,
    ProductionPreplan,
    ProductionWorkOrder,
    ProductionWorkOrderOperation,
    SemiMaterial,
    Supplier,
    SupplierMaterialMap,
)
from app.services.hr_employee_capability_svc import hourly_wage_for_employee_period

DEFAULT_YIELD = Decimal("0.95")
MIN_YIELD = Decimal("0.01")
FALLBACK_DEPT_HOURLY = Decimal("80")
FALLBACK_MACHINE_HOURLY = Decimal("100")
OVERHEAD_RATE = Decimal("0.20")


def _d(val) -> Decimal:
    if val is None:
        return Decimal(0)
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def _piece_rate_for_employee(
    *, company_id: int, employee_id: int, period: str, hr_department_id: int
) -> Optional[Decimal]:
    """若该员工该账期为计件，返回对应工种单价；否则 None。"""
    payroll = HrPayrollLine.query.filter_by(
        company_id=company_id, employee_id=employee_id, period=period
    ).first()
    if not payroll or payroll.wage_kind != "piece_rate":
        return None
    pr_row = HrWorkTypePieceRate.query.filter_by(
        company_id=company_id, work_type_id=hr_department_id, period=period
    ).first()
    return Decimal(pr_row.rate_per_unit) if pr_row else Decimal(0)


def _company_id_for_preplan(preplan: ProductionPreplan) -> int:
    cid = int(preplan.customer_id or 0)
    if cid <= 0:
        return 0
    cust = db.session.get(Customer, cid)
    return int(cust.company_id) if cust else 0


def company_id_for_preplan(preplan: ProductionPreplan) -> int:
    return _company_id_for_preplan(preplan)


def resolve_capability_dept_ids(*, company_id: int, process_hr_department_id: int) -> List[int]:
    pid = int(process_hr_department_id)
    return [pid]


def _recommend_employee_for_hr_op(
    *,
    op: ProductionWorkOrderOperation,
    company_id: int,
    period: str,
    cap_dept_ids: List[int],
) -> Tuple[int, str]:
    if not cap_dept_ids:
        return 0, "工序部门未配置或映射为空"
    caps = HrEmployeeCapability.query.filter(
        HrEmployeeCapability.company_id == company_id,
        or_(
            HrEmployeeCapability.work_type_id.in_(cap_dept_ids),
            HrEmployeeCapability.hr_department_id.in_(cap_dept_ids),
        ),
    ).all()
    if not caps:
        return 0, "无能力表候选人"
    hours = _d(op.estimated_total_minutes) / Decimal(60)
    best_amt: Optional[Decimal] = None
    best_eid = 0
    best_note = ""
    for cap in caps:
        amt, note = _labor_cost_expectation(
            hours=hours,
            cap=cap,
            company_id=company_id,
            employee_id=int(cap.employee_id),
            period=period,
            planned_qty=_d(op.plan_qty),
            hr_department_id=int(op.effective_work_type_id or 0),
        )
        if best_amt is None or amt < best_amt:
            best_amt = amt
            best_eid = int(cap.employee_id)
            best_note = note
    return best_eid, f"optimized {best_note}" if best_note else "optimized"


def _recommend_machine_pair_for_op(
    *,
    op: ProductionWorkOrderOperation,
    company_id: int,
    period: str,
) -> Tuple[int, int, str]:
    mtid = int(op.machine_type_id or 0)
    machines = (
        Machine.query.filter_by(machine_type_id=mtid, status="enabled")
        .order_by(Machine.id.asc())
        .all()
    )
    if not machines:
        return 0, 0, "无可用机台"
    pairs: List[Tuple[Machine, MachineOperatorAllowlist]] = []
    for m in machines:
        als = MachineOperatorAllowlist.query.filter_by(machine_id=m.id, is_active=True).all()
        for al in als:
            pairs.append((m, al))
    if not pairs:
        return int(machines[0].id), 0, f"无白名单，仅推荐机台 machine={machines[0].id}"
    hours = _d(op.estimated_total_minutes) / Decimal(60)
    best_total: Optional[Decimal] = None
    best_mid = 0
    best_eid = 0
    best_note = ""
    for m, al in pairs:
        cap = _pick_capability_row(
            company_id=company_id,
            employee_id=int(al.employee_id),
            capability_hr_department_id=int(al.effective_capability_work_type_id or 0),
            machine=m,
        )
        lab, n1 = _labor_cost_expectation(
            hours=hours,
            cap=cap,
            company_id=company_id,
            employee_id=int(al.employee_id),
            period=period,
            planned_qty=_d(op.plan_qty),
            hr_department_id=int(al.effective_capability_work_type_id or 0),
        )
        mc = hours * _machine_hourly_rate(m)
        tot = lab + mc
        if best_total is None or tot < best_total:
            best_total = tot
            best_mid = int(m.id)
            best_eid = int(al.employee_id)
            best_note = f"optimized m={m.id} emp={al.employee_id} {n1} mac_rate={_machine_hourly_rate(m)}"
    return best_mid, best_eid, best_note


def recommend_budget_assignment_for_operation(
    *,
    op: ProductionWorkOrderOperation,
    company_id: int,
    period: str,
) -> Tuple[int, int, str]:
    rk = (op.resource_kind or "").strip()
    if rk == "machine_type" and int(op.machine_type_id or 0) > 0:
        return _recommend_machine_pair_for_op(op=op, company_id=company_id, period=period)
    if rk in ("hr_department", "hr_work_type") and int(op.effective_work_type_id or 0) > 0:
        cap_ids = resolve_capability_dept_ids(
            company_id=company_id,
            process_hr_department_id=int(op.effective_work_type_id),
        )
        eid, note = _recommend_employee_for_hr_op(
            op=op,
            company_id=company_id,
            period=period,
            cap_dept_ids=cap_ids,
        )
        return 0, int(eid or 0), note
    return 0, 0, "资源类型无需推荐"


def _yield_from_cap(cap: HrEmployeeCapability) -> Decimal:
    g = _d(cap.good_qty_total)
    b = _d(cap.bad_qty_total)
    if g + b <= 0:
        return DEFAULT_YIELD
    y = g / (g + b)
    if y < MIN_YIELD:
        return MIN_YIELD
    if y > Decimal(1):
        return Decimal(1)
    return y


def _resolve_default_capability_dept_for_machine(machine: Optional[Machine]) -> int:
    """
    机台优先、否则机种：指定「操作该设备」对应的能力工位（hr_department.id）。
    用于白名单 capability_hr_department_id=0 时，避免跨工种择优品率。
    """
    if not machine:
        return 0
    did = int(getattr(machine, "effective_default_capability_work_type_id", 0) or 0)
    if did > 0:
        return did
    mt_id = int(getattr(machine, "machine_type_id", 0) or 0)
    if mt_id <= 0:
        return 0
    mt = getattr(machine, "machine_type", None)
    if mt is None:
        mt = db.session.get(MachineType, mt_id)
    if mt and int(getattr(mt, "effective_default_capability_work_type_id", 0) or 0) > 0:
        return int(mt.effective_default_capability_work_type_id)
    return 0


def _effective_hourly_from_cap(
    cap: HrEmployeeCapability, *, company_id: int, employee_id: int, period: str
) -> Decimal:
    wm = _d(cap.worked_minutes_total)
    lc = _d(cap.labor_cost_total)
    if wm > 0 and lc > 0:
        return lc / (wm / Decimal(60))
    return hourly_wage_for_employee_period(
        company_id=company_id, employee_id=employee_id, period=period
    )


def _pick_capability_row(
    *,
    company_id: int,
    employee_id: int,
    capability_hr_department_id: int,
    machine: Optional[Machine] = None,
) -> Optional[HrEmployeeCapability]:
    eid = int(employee_id)
    if capability_hr_department_id > 0:
        return HrEmployeeCapability.query.filter(
            HrEmployeeCapability.company_id == company_id,
            HrEmployeeCapability.employee_id == eid,
            or_(
                HrEmployeeCapability.work_type_id == int(capability_hr_department_id),
                HrEmployeeCapability.hr_department_id == int(capability_hr_department_id),
            ),
        ).first()
    # 白名单未写工位：优先机台/机种上的「默认能力工位」，只认该工种一条能力记录
    effective_dept = _resolve_default_capability_dept_for_machine(machine)
    if effective_dept > 0:
        return HrEmployeeCapability.query.filter(
            HrEmployeeCapability.company_id == company_id,
            HrEmployeeCapability.employee_id == eid,
            or_(
                HrEmployeeCapability.work_type_id == effective_dept,
                HrEmployeeCapability.hr_department_id == effective_dept,
            ),
        ).first()
    caps = HrEmployeeCapability.query.filter_by(company_id=company_id, employee_id=eid).all()
    if not caps:
        return None
    best = caps[0]
    best_y = _yield_from_cap(best)
    for c in caps[1:]:
        y = _yield_from_cap(c)
        if y > best_y:
            best_y = y
            best = c
    return best


def _machine_hourly_rate(m: Machine) -> Decimal:
    if m.machine_single_run_cost is not None and _d(m.machine_single_run_cost) > 0:
        return _d(m.machine_single_run_cost)
    arh = _d(m.machine_accum_runtime_hours)
    pp = _d(m.machine_cost_purchase_price)
    if arh > 0 and pp > 0:
        return pp / arh
    return FALLBACK_MACHINE_HOURLY


def _labor_cost_expectation(
    *,
    hours: Decimal,
    cap: Optional[HrEmployeeCapability],
    company_id: int,
    employee_id: int,
    period: str,
    planned_qty: Optional[Decimal] = None,
    hr_department_id: int = 0,
) -> Tuple[Decimal, str]:
    # 计件快速路径（在所有其他逻辑之前）
    pr = _piece_rate_for_employee(
        company_id=company_id, employee_id=employee_id,
        period=period, hr_department_id=hr_department_id
    )
    if pr is not None:
        qty = planned_qty if planned_qty is not None else Decimal(0)
        amt = pr * qty
        return amt, f"piece_rate emp={employee_id} dept={hr_department_id} rate={pr} qty={qty}"

    if not cap:
        hw = hourly_wage_for_employee_period(
            company_id=company_id, employee_id=employee_id, period=period
        )
        if hw <= 0:
            hw = FALLBACK_DEPT_HOURLY
        y = DEFAULT_YIELD
        amt = hours * hw / y
        return amt, f"无能力表记录，用时薪或默认 {FALLBACK_DEPT_HOURLY}，yield={y}"
    y = _yield_from_cap(cap)
    hw = _effective_hourly_from_cap(cap, company_id=company_id, employee_id=employee_id, period=period)
    if hw <= 0:
        hw = hourly_wage_for_employee_period(
            company_id=company_id, employee_id=employee_id, period=period
        )
    if hw <= 0:
        hw = FALLBACK_DEPT_HOURLY
    amt = hours * hw / y
    return amt, f"emp={employee_id} work_type={cap.effective_work_type_id} yield={y} hourly={hw}"


def _resolve_material_unit_cost(*, company_id: int, material_id: int) -> Optional[Decimal]:
    if material_id <= 0:
        return None
    if company_id > 0:
        mapping = (
            SupplierMaterialMap.query.join(
                Supplier, Supplier.id == SupplierMaterialMap.supplier_id
            )
            .filter(
                SupplierMaterialMap.company_id == company_id,
                SupplierMaterialMap.material_id == material_id,
                SupplierMaterialMap.is_preferred.is_(True),
                SupplierMaterialMap.is_active.is_(True),
                Supplier.is_active.is_(True),
            )
            .order_by(
                SupplierMaterialMap.updated_at.desc(),
                SupplierMaterialMap.id.desc(),
            )
            .first()
        )
        if mapping and mapping.last_unit_price is not None:
            return _d(mapping.last_unit_price)
    sm = db.session.get(SemiMaterial, material_id)
    if sm and sm.standard_unit_cost is not None:
        return _d(sm.standard_unit_cost)
    return None


def _material_plan_total_and_unpriced(*, preplan_id: int) -> Tuple[Decimal, int]:
    preplan = db.session.get(ProductionPreplan, preplan_id)
    company_id = _company_id_for_preplan(preplan) if preplan else 0
    rows = ProductionMaterialPlanDetail.query.filter_by(preplan_id=preplan_id).all()
    total = Decimal(0)
    unpriced = 0
    for r in rows:
        unit_cost = _resolve_material_unit_cost(
            company_id=company_id,
            material_id=int(r.child_material_id or 0),
        )
        if unit_cost is None:
            unpriced += 1
            continue
        total += _d(r.net_required_qty) * unit_cost
    return total, unpriced


def _cost_hr_department_op(
    *,
    op: ProductionWorkOrderOperation,
    scenario: str,
    company_id: int,
    period: str,
    cap_dept_ids: List[int],
) -> Tuple[Decimal, str]:
    hours = _d(op.estimated_total_minutes) / Decimal(60)
    if hours <= 0:
        return Decimal(0), "工时为0"

    if scenario == "optimized":
        eid, rec_note = _recommend_employee_for_hr_op(
            op=op,
            company_id=company_id,
            period=period,
            cap_dept_ids=cap_dept_ids,
        )
        if eid <= 0:
            amt = hours * FALLBACK_DEPT_HOURLY / DEFAULT_YIELD
            return amt, f"{rec_note}，默认部门费率"
        cap: Optional[HrEmployeeCapability] = None
        for did in cap_dept_ids:
            cap = HrEmployeeCapability.query.filter(
                HrEmployeeCapability.company_id == company_id,
                HrEmployeeCapability.employee_id == eid,
                or_(
                    HrEmployeeCapability.work_type_id == did,
                    HrEmployeeCapability.hr_department_id == did,
                ),
            ).first()
            if cap:
                break
        if cap is None:
            cap = _pick_capability_row(company_id=company_id, employee_id=eid, capability_hr_department_id=0)
        amt, note = _labor_cost_expectation(
            hours=hours,
            cap=cap,
            company_id=company_id,
            employee_id=eid,
            period=period,
            planned_qty=_d(op.plan_qty),
            hr_department_id=int(op.effective_work_type_id or 0),
        )
        return amt, rec_note if rec_note else ("optimized " + note)

    # assigned
    eid = int(op.budget_operator_employee_id or 0)
    if eid <= 0:
        return Decimal(0), "未指定操作员"
    cap: Optional[HrEmployeeCapability] = None
    for did in cap_dept_ids:
        cap = HrEmployeeCapability.query.filter(
            HrEmployeeCapability.company_id == company_id,
            HrEmployeeCapability.employee_id == eid,
            or_(
                HrEmployeeCapability.work_type_id == did,
                HrEmployeeCapability.hr_department_id == did,
            ),
        ).first()
        if cap:
            break
    if cap is None:
        cap = _pick_capability_row(company_id=company_id, employee_id=eid, capability_hr_department_id=0)
    amt, note = _labor_cost_expectation(
        hours=hours, cap=cap, company_id=company_id, employee_id=eid, period=period,
        planned_qty=_d(op.plan_qty),
        hr_department_id=int(op.effective_work_type_id or 0),
    )
    return amt, "assigned " + note


def _cost_machine_op(
    *,
    op: ProductionWorkOrderOperation,
    scenario: str,
    company_id: int,
    period: str,
) -> Tuple[Decimal, Decimal, str]:
    """返回 (人工期望成本, 机台成本, 备注)"""
    hours = _d(op.estimated_total_minutes) / Decimal(60)
    if hours <= 0:
        return Decimal(0), Decimal(0), "工时为0"
    mtid = int(op.machine_type_id or 0)
    machines = (
        Machine.query.filter_by(machine_type_id=mtid, status="enabled")
        .order_by(Machine.id.asc())
        .all()
    )
    if not machines:
        return Decimal(0), Decimal(0), "无可用机台"

    if scenario == "optimized":
        mid, eid, rec_note = _recommend_machine_pair_for_op(
            op=op,
            company_id=company_id,
            period=period,
        )
        if mid <= 0:
            return Decimal(0), Decimal(0), rec_note
        m = db.session.get(Machine, mid)
        if not m:
            return Decimal(0), Decimal(0), "推荐机台不存在"
        if eid <= 0:
            mc = hours * _machine_hourly_rate(m)
            return Decimal(0), mc, rec_note
        al = MachineOperatorAllowlist.query.filter_by(
            machine_id=mid, employee_id=eid, is_active=True
        ).first()
        cap_dept = int(al.effective_capability_work_type_id) if al else 0
        cap = _pick_capability_row(
            company_id=company_id,
            employee_id=eid,
            capability_hr_department_id=cap_dept,
            machine=m,
        )
        lab, _ = _labor_cost_expectation(
            hours=hours,
            cap=cap,
            company_id=company_id,
            employee_id=eid,
            period=period,
            planned_qty=_d(op.plan_qty),
            hr_department_id=int(al.effective_capability_work_type_id or 0) if al else 0,
        )
        mc = hours * _machine_hourly_rate(m)
        return lab, mc, rec_note

    mid = int(op.budget_machine_id or 0)
    eid = int(op.budget_operator_employee_id or 0)
    if mid <= 0 or eid <= 0:
        return Decimal(0), Decimal(0), "未指定机台或操作员"
    m = db.session.get(Machine, mid)
    if not m or int(m.machine_type_id) != mtid:
        return Decimal(0), Decimal(0), "指定机台不存在或机种不匹配"
    al = MachineOperatorAllowlist.query.filter_by(
        machine_id=mid, employee_id=eid, is_active=True
    ).first()
    cap_dept = int(al.effective_capability_work_type_id) if al else 0
    cap = _pick_capability_row(
        company_id=company_id,
        employee_id=eid,
        capability_hr_department_id=cap_dept,
        machine=m,
    )
    lab, n1 = _labor_cost_expectation(
        hours=hours, cap=cap, company_id=company_id, employee_id=eid, period=period,
        planned_qty=_d(op.plan_qty),
        hr_department_id=int(al.effective_capability_work_type_id or 0) if al else 0,
    )
    mc = hours * _machine_hourly_rate(m)
    return lab, mc, f"assigned m={m.id} emp={eid} {n1}"


def build_cost_plan_for_preplan(*, preplan_id: int) -> None:
    db.session.query(ProductionCostPlanDetail).filter_by(preplan_id=preplan_id).delete(
        synchronize_session=False
    )
    db.session.flush()

    preplan = db.session.get(ProductionPreplan, preplan_id)
    if not preplan:
        return

    company_id = _company_id_for_preplan(preplan)
    period = preplan.plan_date.strftime("%Y-%m") if preplan.plan_date else ""

    mat_total, mat_unpriced = _material_plan_total_and_unpriced(preplan_id=preplan_id)
    mat_remark = "物料标准成本汇总"
    if mat_unpriced > 0:
        mat_remark += f"（{mat_unpriced} 行物料未维护 standard_unit_cost，按 0 计）"

    mat_remark = "物料成本按默认供应商报价优先，缺失时回退标准成本"
    if mat_unpriced > 0:
        mat_remark += f"（{mat_unpriced} 行物料缺少默认报价和标准成本，按 0 计）"

    work_orders: Iterable[ProductionWorkOrder] = (
        ProductionWorkOrder.query.filter_by(preplan_id=preplan_id)
        .order_by(ProductionWorkOrder.id.asc())
        .all()
    )
    for scenario in ("optimized", "assigned"):
        for wo in work_orders:
            labor_total = Decimal(0)
            machine_total = Decimal(0)

            ops: Iterable[ProductionWorkOrderOperation] = (
                ProductionWorkOrderOperation.query.filter_by(work_order_id=wo.id)
                .order_by(
                    ProductionWorkOrderOperation.step_no.asc(),
                    ProductionWorkOrderOperation.id.asc(),
                )
                .all()
            )

            for op in ops:
                if op.resource_kind in ("hr_department", "hr_work_type") and int(op.effective_work_type_id or 0) > 0:
                    cap_ids = resolve_capability_dept_ids(
                        company_id=company_id,
                        process_hr_department_id=int(op.effective_work_type_id),
                    )
                    amt, note = _cost_hr_department_op(
                        op=op,
                        scenario=scenario,
                        company_id=company_id,
                        period=period,
                        cap_dept_ids=cap_ids,
                    )
                    labor_total += amt
                    db.session.add(
                        ProductionCostPlanDetail(
                            preplan_id=wo.preplan_id,
                            scenario=scenario,
                            work_order_id=wo.id,
                            operation_id=op.id,
                            cost_category="labor",
                            amount=amt,
                            currency="CNY",
                            unit_cost=None,
                            qty_basis=_d(op.estimated_total_minutes) / Decimal(60),
                            remark=note[:255] if note else None,
                        )
                    )
                elif op.resource_kind == "machine_type" and int(op.machine_type_id or 0) > 0:
                    lab, mac, note = _cost_machine_op(
                        op=op,
                        scenario=scenario,
                        company_id=company_id,
                        period=period,
                    )
                    labor_total += lab
                    machine_total += mac
                    if lab > 0:
                        db.session.add(
                            ProductionCostPlanDetail(
                                preplan_id=wo.preplan_id,
                                scenario=scenario,
                                work_order_id=wo.id,
                                operation_id=op.id,
                                cost_category="labor",
                                amount=lab,
                                currency="CNY",
                                unit_cost=None,
                                qty_basis=_d(op.estimated_total_minutes) / Decimal(60),
                                remark=(note[:255] if note else None),
                            )
                        )
                    if mac > 0:
                        db.session.add(
                            ProductionCostPlanDetail(
                                preplan_id=wo.preplan_id,
                                scenario=scenario,
                                work_order_id=wo.id,
                                operation_id=op.id,
                                cost_category="machine",
                                amount=mac,
                                currency="CNY",
                                unit_cost=None,
                                qty_basis=_d(op.estimated_total_minutes) / Decimal(60),
                                remark=(note[:255] if note else None),
                            )
                        )

            base = labor_total + machine_total
            if base > 0:
                overhead_amount = base * OVERHEAD_RATE
                db.session.add(
                    ProductionCostPlanDetail(
                        preplan_id=wo.preplan_id,
                        scenario=scenario,
                        work_order_id=wo.id,
                        operation_id=None,
                        cost_category="overhead",
                        amount=overhead_amount,
                        currency="CNY",
                        unit_cost=None,
                        qty_basis=None,
                        remark=f"制造费用 {OVERHEAD_RATE*100:.0f}%（人工+机台）",
                    )
                )

        if mat_total > 0 or mat_unpriced > 0:
            first_wo_id = int(work_orders[0].id) if work_orders else 0
            if first_wo_id:
                db.session.add(
                    ProductionCostPlanDetail(
                        preplan_id=preplan_id,
                        scenario=scenario,
                        work_order_id=first_wo_id,
                        operation_id=None,
                        cost_category="material",
                        amount=mat_total,
                        currency="CNY",
                        unit_cost=None,
                        qty_basis=None,
                        remark=mat_remark[:255],
                    )
                )
