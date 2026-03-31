from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from io import BytesIO
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from flask import flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app import db
from app.auth.decorators import capability_required, menu_required
from app.models import (
    Customer,
    Product,
    ProductionComponentNeed,
    ProductionIncident,
    ProductionPreplan,
    ProductionPreplanLine,
    ProductionWorkOrder,
    User,
)
from app.services import bom_svc, delivery_svc, production_svc


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


def _require_preplan_with_lines(preplan_id: int) -> ProductionPreplan:
    preplan = (
        ProductionPreplan.query.options(selectinload(ProductionPreplan.lines))
        .filter(ProductionPreplan.id == preplan_id)
        .first()
    )
    if not preplan:
        raise ValueError("预生产计划不存在。")
    return preplan


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
                selectinload(ProductionWorkOrder.component_needs).selectinload(
                    ProductionComponentNeed.child_material
                ),
            )
            .order_by(ProductionWorkOrder.id.asc())
            .all()
        )
        raw_material_totals = _raw_material_totals_from_work_orders(work_orders)
        return render_template(
            "production/preplan_detail.html",
            preplan=preplan,
            work_orders=work_orders,
            raw_material_totals=raw_material_totals,
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
            flash("生产测算已完成。", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"测算失败：{e}", "danger")
        return redirect(
            url_for("main.production_preplan_detail", preplan_id=preplan_id)
        )

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

