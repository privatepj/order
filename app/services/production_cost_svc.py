from __future__ import annotations

from decimal import Decimal
from typing import Iterable, List, Optional, Tuple

from app import db
from app.models import (
    Customer,
    HrDepartmentCapabilityMap,
    HrEmployeeCapability,
    Machine,
    MachineType,
    MachineOperatorAllowlist,
    ProductionCostPlanDetail,
    ProductionMaterialPlanDetail,
    ProductionPreplan,
    ProductionWorkOrder,
    ProductionWorkOrderOperation,
    SemiMaterial,
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


def _company_id_for_preplan(preplan: ProductionPreplan) -> int:
    cid = int(preplan.customer_id or 0)
    if cid <= 0:
        return 0
    cust = db.session.get(Customer, cid)
    return int(cust.company_id) if cust else 0


def resolve_capability_dept_ids(*, company_id: int, process_hr_department_id: int) -> List[int]:
    pid = int(process_hr_department_id)
    if company_id <= 0 or pid <= 0:
        return [pid] if pid > 0 else []
    maps = (
        HrDepartmentCapabilityMap.query.filter_by(
            company_id=company_id, process_hr_department_id=pid, is_active=True
        )
        .all()
    )
    if maps:
        return list({int(m.capability_hr_department_id) for m in maps})
    return [pid]


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
    did = int(getattr(machine, "default_capability_hr_department_id", 0) or 0)
    if did > 0:
        return did
    mt_id = int(getattr(machine, "machine_type_id", 0) or 0)
    if mt_id <= 0:
        return 0
    mt = getattr(machine, "machine_type", None)
    if mt is None:
        mt = db.session.get(MachineType, mt_id)
    if mt and int(getattr(mt, "default_capability_hr_department_id", 0) or 0) > 0:
        return int(mt.default_capability_hr_department_id)
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
        return HrEmployeeCapability.query.filter_by(
            company_id=company_id,
            employee_id=eid,
            hr_department_id=int(capability_hr_department_id),
        ).first()
    # 白名单未写工位：优先机台/机种上的「默认能力工位」，只认该工种一条能力记录
    effective_dept = _resolve_default_capability_dept_for_machine(machine)
    if effective_dept > 0:
        return HrEmployeeCapability.query.filter_by(
            company_id=company_id,
            employee_id=eid,
            hr_department_id=effective_dept,
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
) -> Tuple[Decimal, str]:
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
    return amt, f"emp={employee_id} dept_cap={cap.hr_department_id} yield={y} hourly={hw}"


def _material_plan_total_and_unpriced(*, preplan_id: int) -> Tuple[Decimal, int]:
    rows = ProductionMaterialPlanDetail.query.filter_by(preplan_id=preplan_id).all()
    total = Decimal(0)
    unpriced = 0
    for r in rows:
        sm = db.session.get(SemiMaterial, int(r.child_material_id))
        if sm is None or sm.standard_unit_cost is None:
            unpriced += 1
            continue
        total += _d(r.net_required_qty) * _d(sm.standard_unit_cost)
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
        if not cap_dept_ids:
            amt = hours * FALLBACK_DEPT_HOURLY / DEFAULT_YIELD
            return amt, "工序部门未配置或映射为空，默认部门费率"
        caps = HrEmployeeCapability.query.filter(
            HrEmployeeCapability.company_id == company_id,
            HrEmployeeCapability.hr_department_id.in_(cap_dept_ids),
        ).all()
        if not caps:
            amt = hours * FALLBACK_DEPT_HOURLY / DEFAULT_YIELD
            return amt, "无能力表候选人，默认部门费率"
        best_amt: Optional[Decimal] = None
        best_note = ""
        for cap in caps:
            amt, note = _labor_cost_expectation(
                hours=hours,
                cap=cap,
                company_id=company_id,
                employee_id=int(cap.employee_id),
                period=period,
            )
            if best_amt is None or amt < best_amt:
                best_amt = amt
                best_note = "optimized " + note
        return best_amt or Decimal(0), best_note

    # assigned
    eid = int(op.budget_operator_employee_id or 0)
    if eid <= 0:
        return Decimal(0), "未指定操作员"
    cap: Optional[HrEmployeeCapability] = None
    for did in cap_dept_ids:
        cap = HrEmployeeCapability.query.filter_by(
            company_id=company_id, employee_id=eid, hr_department_id=did
        ).first()
        if cap:
            break
    if cap is None:
        cap = _pick_capability_row(company_id=company_id, employee_id=eid, capability_hr_department_id=0)
    amt, note = _labor_cost_expectation(
        hours=hours, cap=cap, company_id=company_id, employee_id=eid, period=period
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
        pairs: List[Tuple[Machine, MachineOperatorAllowlist]] = []
        for m in machines:
            als = MachineOperatorAllowlist.query.filter_by(machine_id=m.id, is_active=True).all()
            for al in als:
                pairs.append((m, al))
        if not pairs:
            m0 = machines[0]
            mc = hours * _machine_hourly_rate(m0)
            return Decimal(0), mc, f"optimized 无白名单，仅机台 machine={m0.id} {mc}"
        best_total: Optional[Decimal] = None
        best_lab = Decimal(0)
        best_mac = Decimal(0)
        best_note = ""
        for m, al in pairs:
            cap = _pick_capability_row(
                company_id=company_id,
                employee_id=int(al.employee_id),
                capability_hr_department_id=int(al.capability_hr_department_id or 0),
                machine=m,
            )
            lab, n1 = _labor_cost_expectation(
                hours=hours,
                cap=cap,
                company_id=company_id,
                employee_id=int(al.employee_id),
                period=period,
            )
            mc = hours * _machine_hourly_rate(m)
            tot = lab + mc
            if best_total is None or tot < best_total:
                best_total = tot
                best_lab = lab
                best_mac = mc
                best_note = f"optimized m={m.id} emp={al.employee_id} {n1} mac_rate={_machine_hourly_rate(m)}"
        return best_lab, best_mac, best_note

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
    cap_dept = int(al.capability_hr_department_id) if al else 0
    cap = _pick_capability_row(
        company_id=company_id,
        employee_id=eid,
        capability_hr_department_id=cap_dept,
        machine=m,
    )
    lab, n1 = _labor_cost_expectation(
        hours=hours, cap=cap, company_id=company_id, employee_id=eid, period=period
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
                if op.resource_kind == "hr_department" and int(op.hr_department_id or 0) > 0:
                    cap_ids = resolve_capability_dept_ids(
                        company_id=company_id,
                        process_hr_department_id=int(op.hr_department_id),
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
