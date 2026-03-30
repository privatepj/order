from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app import db
from app.auth.decorators import capability_required, menu_required
from app.models import (
    Customer,
    Product,
    ProductionComponentNeed,
    ProductionPreplan,
    ProductionPreplanLine,
    ProductionWorkOrder,
)
from app.services import delivery_svc, production_svc


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
    @menu_required("production")
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
    @menu_required("production")
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
    @menu_required("production")
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
    @menu_required("production")
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
    @menu_required("production")
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
    @menu_required("production")
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
        return render_template(
            "production/preplan_detail.html",
            preplan=preplan,
            work_orders=work_orders,
        )

    # ----------------------------
    # 测算运行（已存在预生产计划）
    # ----------------------------
    @bp.route("/production/preplans/<int:preplan_id>/measure", methods=["POST"])
    @login_required
    @menu_required("production")
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

