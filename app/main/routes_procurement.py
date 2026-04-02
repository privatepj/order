from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app import db
from app.auth.capabilities import current_user_can_cap
from app.auth.decorators import capability_required, menu_required
from app.models import (
    Company,
    PurchaseOrder,
    PurchaseReceipt,
    PurchaseRequisition,
    PurchaseStockIn,
    User,
)
from app.services import orchestrator_engine
from app.services.orchestrator_contracts import EVENT_PROCUREMENT_RECEIVED

REQUISITION_STATUS = ("draft", "ordered", "cancelled")
PO_STATUS = ("draft", "ordered", "partially_received", "received", "cancelled")
RECEIPT_STATUS = ("draft", "posted")


def _companies():
    return Company.query.order_by(Company.id).all()


def _resolve_company_id():
    # 采购前端不再允许选择主体：一律使用默认主体（无则兜底取最小 id）
    companies = _companies()
    return Company.get_default_id(), companies


def _next_no(prefix: str, model, field_name: str) -> str:
    today = date.today().strftime("%Y%m%d")
    start = f"{prefix}{today}"
    column = getattr(model, field_name)
    latest = model.query.filter(column.like(f"{start}%")).order_by(model.id.desc()).first()
    if latest:
        raw = getattr(latest, field_name)
        try:
            seq = int(str(raw)[-4:]) + 1
        except Exception:
            seq = 1
    else:
        seq = 1
    return f"{start}{seq:04d}"


def _parse_decimal(raw: str, name: str) -> Decimal | None:
    try:
        v = Decimal((raw or "").strip())
    except InvalidOperation:
        flash(f"{name}格式不正确。", "danger")
        return None
    if v < 0:
        flash(f"{name}不能为负数。", "danger")
        return None
    return v


def register_procurement_routes(bp):
    @bp.route("/purchase-requisitions")
    @login_required
    @menu_required("procurement_requisition")
    def procurement_requisition_list():
        company_id, companies = _resolve_company_id()
        keyword = (request.args.get("keyword") or "").strip()
        status = (request.args.get("status") or "").strip()
        q = PurchaseRequisition.query
        if company_id:
            q = q.filter(PurchaseRequisition.company_id == company_id)
        if current_user_can_cap("procurement_requisition.filter.keyword") and keyword:
            q = q.filter(
                or_(
                    PurchaseRequisition.req_no.contains(keyword),
                    PurchaseRequisition.supplier_name.contains(keyword),
                    PurchaseRequisition.item_name.contains(keyword),
                )
            )
        if status in REQUISITION_STATUS:
            q = q.filter(PurchaseRequisition.status == status)
        rows = q.order_by(PurchaseRequisition.id.desc()).all()
        return render_template(
            "procurement/requisition_list.html",
            rows=rows,
            companies=companies,
            company_id=company_id,
            keyword=keyword,
            status=status,
            requisition_statuses=REQUISITION_STATUS,
        )

    @bp.route("/purchase-requisitions/new", methods=["GET", "POST"])
    @login_required
    @menu_required("procurement_requisition")
    @capability_required("procurement_requisition.action.create")
    def procurement_requisition_new():
        companies = _companies()
        if request.method == "POST":
            return _save_requisition(None, companies)
        return render_template(
            "procurement/requisition_form.html",
            row=None,
            companies=companies,
            company_id=Company.get_default_id(),
            requisition_statuses=REQUISITION_STATUS,
        )

    @bp.route("/purchase-requisitions/<int:req_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("procurement_requisition")
    @capability_required("procurement_requisition.action.edit")
    def procurement_requisition_edit(req_id):
        row = PurchaseRequisition.query.get_or_404(req_id)
        companies = _companies()
        if request.method == "POST":
            return _save_requisition(row, companies)
        return render_template(
            "procurement/requisition_form.html",
            row=row,
            companies=companies,
            company_id=row.company_id,
            requisition_statuses=REQUISITION_STATUS,
        )

    def _save_requisition(row, companies):
        company_id = row.company_id if row else Company.get_default_id()
        supplier_name = (request.form.get("supplier_name") or "").strip()
        item_name = (request.form.get("item_name") or "").strip()
        item_spec = (request.form.get("item_spec") or "").strip() or None
        unit = (request.form.get("unit") or "pcs").strip() or "pcs"
        status = (request.form.get("status") or "draft").strip()
        expected_raw = (request.form.get("expected_date") or "").strip()
        remark = (request.form.get("remark") or "").strip() or None
        qty = _parse_decimal(request.form.get("qty") or "0", "请购数量")
        if qty is None:
            return render_template(
                "procurement/requisition_form.html",
                row=row,
                companies=companies,
                company_id=company_id,
                requisition_statuses=REQUISITION_STATUS,
            )
        if not company_id:
            flash("请先设置默认经营主体。", "danger")
            return render_template(
                "procurement/requisition_form.html",
                row=row,
                companies=companies,
                company_id=company_id,
                requisition_statuses=REQUISITION_STATUS,
            )
        if not supplier_name or not item_name:
            flash("供应商、物料名称、数量为必填。", "danger")
            return render_template(
                "procurement/requisition_form.html",
                row=row,
                companies=companies,
                company_id=company_id,
                requisition_statuses=REQUISITION_STATUS,
            )
        expected_date = None
        if expected_raw:
            try:
                expected_date = datetime.strptime(expected_raw, "%Y-%m-%d").date()
            except ValueError:
                flash("期望到货日期格式错误。", "danger")
                return render_template(
                    "procurement/requisition_form.html",
                    row=row,
                    companies=companies,
                    company_id=company_id,
                    requisition_statuses=REQUISITION_STATUS,
                )
        if status not in REQUISITION_STATUS:
            status = "draft"
        if not row:
            row = PurchaseRequisition(
                req_no=_next_no("REQ", PurchaseRequisition, "req_no"),
                requester_user_id=int(current_user.get_id()),
            )
            db.session.add(row)
        row.company_id = company_id
        row.supplier_name = supplier_name
        row.item_name = item_name
        row.item_spec = item_spec
        row.qty = qty
        row.unit = unit
        row.status = status
        row.expected_date = expected_date
        row.remark = remark
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("请购单号冲突，请重试。", "danger")
            return render_template(
                "procurement/requisition_form.html",
                row=row,
                companies=companies,
                company_id=company_id,
                requisition_statuses=REQUISITION_STATUS,
            )
        flash("请购单已保存。", "success")
        return redirect(url_for("main.procurement_requisition_list", company_id=company_id))

    @bp.route("/purchase-requisitions/<int:req_id>/delete", methods=["POST"])
    @login_required
    @menu_required("procurement_requisition")
    @capability_required("procurement_requisition.action.delete")
    def procurement_requisition_delete(req_id):
        row = PurchaseRequisition.query.get_or_404(req_id)
        if PurchaseOrder.query.filter_by(requisition_id=row.id).first():
            flash("该请购单已关联采购单，不能删除。", "danger")
            return redirect(url_for("main.procurement_requisition_list", company_id=row.company_id))
        cid = row.company_id
        db.session.delete(row)
        db.session.commit()
        flash("请购单已删除。", "success")
        return redirect(url_for("main.procurement_requisition_list", company_id=cid))

    @bp.route("/purchase-orders")
    @login_required
    @menu_required("procurement_order")
    def procurement_order_list():
        company_id, companies = _resolve_company_id()
        keyword = (request.args.get("keyword") or "").strip()
        status = (request.args.get("status") or "").strip()
        q = PurchaseOrder.query
        if company_id:
            q = q.filter(PurchaseOrder.company_id == company_id)
        if current_user_can_cap("procurement_order.filter.keyword") and keyword:
            q = q.filter(
                or_(
                    PurchaseOrder.po_no.contains(keyword),
                    PurchaseOrder.supplier_name.contains(keyword),
                    PurchaseOrder.item_name.contains(keyword),
                )
            )
        if status in PO_STATUS:
            q = q.filter(PurchaseOrder.status == status)
        rows = q.order_by(PurchaseOrder.id.desc()).all()
        return render_template(
            "procurement/order_list.html",
            rows=rows,
            companies=companies,
            company_id=company_id,
            keyword=keyword,
            status=status,
            po_statuses=PO_STATUS,
        )

    @bp.route("/purchase-orders/new", methods=["GET", "POST"])
    @login_required
    @menu_required("procurement_order")
    @capability_required("procurement_order.action.create")
    def procurement_order_new():
        companies = _companies()
        company_id, _ = _resolve_company_id()
        q = PurchaseRequisition.query.filter(PurchaseRequisition.status != "cancelled")
        if company_id:
            q = q.filter(PurchaseRequisition.company_id == company_id)
        reqs = q.order_by(PurchaseRequisition.id.desc()).limit(200).all()
        if request.method == "POST":
            return _save_order(None, companies, reqs)
        return render_template(
            "procurement/order_form.html",
            row=None,
            companies=companies,
            requisitions=reqs,
            company_id=company_id,
            po_statuses=PO_STATUS,
        )

    @bp.route("/purchase-orders/<int:po_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("procurement_order")
    @capability_required("procurement_order.action.edit")
    def procurement_order_edit(po_id):
        row = PurchaseOrder.query.get_or_404(po_id)
        companies = _companies()
        company_id = row.company_id
        q = PurchaseRequisition.query.filter(PurchaseRequisition.status != "cancelled")
        if company_id:
            q = q.filter(PurchaseRequisition.company_id == company_id)
        reqs = q.order_by(PurchaseRequisition.id.desc()).limit(200).all()
        if request.method == "POST":
            return _save_order(row, companies, reqs)
        return render_template(
            "procurement/order_form.html",
            row=row,
            companies=companies,
            requisitions=reqs,
            company_id=company_id,
            po_statuses=PO_STATUS,
        )

    def _save_order(row, companies, requisitions):
        company_id = row.company_id if row else Company.get_default_id()
        requisition_id = request.form.get("requisition_id", type=int) or None
        supplier_name = (request.form.get("supplier_name") or "").strip()
        item_name = (request.form.get("item_name") or "").strip()
        item_spec = (request.form.get("item_spec") or "").strip() or None
        unit = (request.form.get("unit") or "pcs").strip() or "pcs"
        status = (request.form.get("status") or "draft").strip()
        expected_raw = (request.form.get("expected_date") or "").strip()
        remark = (request.form.get("remark") or "").strip() or None
        qty = _parse_decimal(request.form.get("qty") or "0", "采购数量")
        unit_price = _parse_decimal(request.form.get("unit_price") or "0", "单价")
        if qty is None or unit_price is None:
            return render_template(
                "procurement/order_form.html",
                row=row,
                companies=companies,
                requisitions=requisitions,
                company_id=company_id,
                po_statuses=PO_STATUS,
            )
        if not company_id:
            flash("请先设置默认经营主体。", "danger")
            return render_template(
                "procurement/order_form.html",
                row=row,
                companies=companies,
                requisitions=requisitions,
                company_id=company_id,
                po_statuses=PO_STATUS,
            )
        req = None
        if requisition_id:
            req = PurchaseRequisition.query.get(requisition_id)
            if not req or req.company_id != company_id:
                flash("关联请购单不存在或不属于当前主体。", "danger")
                return render_template(
                    "procurement/order_form.html",
                    row=row,
                    companies=companies,
                    requisitions=requisitions,
                    company_id=company_id,
                    po_statuses=PO_STATUS,
                )
        if not supplier_name or not item_name:
            flash("供应商、物料名称、数量为必填。", "danger")
            return render_template(
                "procurement/order_form.html",
                row=row,
                companies=companies,
                requisitions=requisitions,
                company_id=company_id,
                po_statuses=PO_STATUS,
            )
        expected_date = None
        if expected_raw:
            try:
                expected_date = datetime.strptime(expected_raw, "%Y-%m-%d").date()
            except ValueError:
                flash("期望到货日期格式错误。", "danger")
                return render_template(
                    "procurement/order_form.html",
                    row=row,
                    companies=companies,
                    requisitions=requisitions,
                    company_id=company_id,
                    po_statuses=PO_STATUS,
                )
        if status not in PO_STATUS:
            status = "draft"
        if not row:
            row = PurchaseOrder(po_no=_next_no("PO", PurchaseOrder, "po_no"), buyer_user_id=int(current_user.get_id()))
            db.session.add(row)
        row.company_id = company_id
        row.requisition_id = requisition_id
        row.supplier_name = supplier_name
        row.item_name = item_name
        row.item_spec = item_spec
        row.qty = qty
        row.unit = unit
        row.unit_price = unit_price
        row.amount = qty * unit_price
        row.status = status
        row.expected_date = expected_date
        row.remark = remark
        if req and req.status != "cancelled":
            req.status = "ordered"
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("采购单号冲突，请重试。", "danger")
            return render_template(
                "procurement/order_form.html",
                row=row,
                companies=companies,
                requisitions=requisitions,
                company_id=company_id,
                po_statuses=PO_STATUS,
            )
        flash("采购单已保存。", "success")
        return redirect(url_for("main.procurement_order_list", company_id=company_id))

    @bp.route("/purchase-orders/<int:po_id>/delete", methods=["POST"])
    @login_required
    @menu_required("procurement_order")
    @capability_required("procurement_order.action.delete")
    def procurement_order_delete(po_id):
        row = PurchaseOrder.query.get_or_404(po_id)
        if PurchaseReceipt.query.filter_by(purchase_order_id=row.id).first():
            flash("该采购单已有收货，不能删除。", "danger")
            return redirect(url_for("main.procurement_order_list", company_id=row.company_id))
        cid = row.company_id
        db.session.delete(row)
        db.session.commit()
        flash("采购单已删除。", "success")
        return redirect(url_for("main.procurement_order_list", company_id=cid))

    @bp.route("/purchase-orders/<int:po_id>")
    @login_required
    @menu_required("procurement_order")
    def procurement_order_detail(po_id):
        row = PurchaseOrder.query.get_or_404(po_id)
        receipts = PurchaseReceipt.query.filter_by(purchase_order_id=row.id).order_by(PurchaseReceipt.id.desc()).all()
        return render_template("procurement/order_detail.html", row=row, receipts=receipts)

    @bp.route("/purchase-receipts")
    @login_required
    @menu_required("procurement_receipt")
    def procurement_receipt_list():
        company_id, companies = _resolve_company_id()
        keyword = (request.args.get("keyword") or "").strip()
        status = (request.args.get("status") or "").strip()
        q = PurchaseReceipt.query
        if company_id:
            q = q.filter(PurchaseReceipt.company_id == company_id)
        if current_user_can_cap("procurement_receipt.filter.keyword") and keyword:
            q = q.join(PurchaseOrder, PurchaseOrder.id == PurchaseReceipt.purchase_order_id).filter(
                or_(
                    PurchaseReceipt.receipt_no.contains(keyword),
                    PurchaseOrder.po_no.contains(keyword),
                    PurchaseOrder.supplier_name.contains(keyword),
                )
            )
        if status in RECEIPT_STATUS:
            q = q.filter(PurchaseReceipt.status == status)
        rows = q.order_by(PurchaseReceipt.id.desc()).all()
        return render_template(
            "procurement/receipt_list.html",
            rows=rows,
            companies=companies,
            company_id=company_id,
            keyword=keyword,
            status=status,
            receipt_statuses=RECEIPT_STATUS,
        )

    @bp.route("/purchase-receipts/new", methods=["GET", "POST"])
    @login_required
    @menu_required("procurement_receipt")
    @capability_required("procurement_receipt.action.create")
    def procurement_receipt_new():
        companies = _companies()
        company_id, _ = _resolve_company_id()
        q = PurchaseOrder.query.filter(PurchaseOrder.status.in_(("ordered", "partially_received", "draft")))
        if company_id:
            q = q.filter(PurchaseOrder.company_id == company_id)
        orders = q.order_by(PurchaseOrder.id.desc()).limit(200).all()
        if request.method == "POST":
            return _save_receipt(None, companies, orders)
        return render_template(
            "procurement/receipt_form.html",
            row=None,
            companies=companies,
            orders=orders,
            company_id=company_id,
            receipt_statuses=RECEIPT_STATUS,
        )

    @bp.route("/purchase-receipts/<int:receipt_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("procurement_receipt")
    @capability_required("procurement_receipt.action.edit")
    def procurement_receipt_edit(receipt_id):
        row = PurchaseReceipt.query.get_or_404(receipt_id)
        companies = _companies()
        company_id = row.company_id
        q = PurchaseOrder.query.filter(
            PurchaseOrder.status.in_(("ordered", "partially_received", "draft", "received"))
        )
        if company_id:
            q = q.filter(PurchaseOrder.company_id == company_id)
        orders = q.order_by(PurchaseOrder.id.desc()).limit(200).all()
        if request.method == "POST":
            return _save_receipt(row, companies, orders)
        return render_template(
            "procurement/receipt_form.html",
            row=row,
            companies=companies,
            orders=orders,
            company_id=company_id,
            receipt_statuses=RECEIPT_STATUS,
        )

    def _sync_po_status_from_receipts(po: PurchaseOrder):
        posted_sum = (
            db.session.query(db.func.coalesce(db.func.sum(PurchaseReceipt.received_qty), 0))
            .filter(PurchaseReceipt.purchase_order_id == po.id, PurchaseReceipt.status == "posted")
            .scalar()
        )
        if posted_sum >= po.qty:
            po.status = "received"
        elif posted_sum > 0:
            po.status = "partially_received"
        elif po.status not in ("cancelled", "draft"):
            po.status = "ordered"

    def _save_receipt(row, companies, orders):
        company_id = row.company_id if row else Company.get_default_id()
        purchase_order_id = request.form.get("purchase_order_id", type=int)
        status = (request.form.get("status") or "draft").strip()
        received_at_raw = (request.form.get("received_at") or "").strip()
        remark = (request.form.get("remark") or "").strip() or None
        storage_area = (request.form.get("storage_area") or "").strip() or None
        received_qty = _parse_decimal(request.form.get("received_qty") or "0", "收货数量")
        if received_qty is None:
            return render_template(
                "procurement/receipt_form.html",
                row=row,
                companies=companies,
                orders=orders,
                company_id=company_id,
                receipt_statuses=RECEIPT_STATUS,
            )
        if not company_id:
            flash("请先设置默认经营主体。", "danger")
            return render_template(
                "procurement/receipt_form.html",
                row=row,
                companies=companies,
                orders=orders,
                company_id=company_id,
                receipt_statuses=RECEIPT_STATUS,
            )
        po = PurchaseOrder.query.get(purchase_order_id)
        if not po or po.company_id != company_id:
            flash("请选择有效采购单。", "danger")
            return render_template(
                "procurement/receipt_form.html",
                row=row,
                companies=companies,
                orders=orders,
                company_id=company_id,
                receipt_statuses=RECEIPT_STATUS,
            )
        if status not in RECEIPT_STATUS:
            status = "draft"
        try:
            received_at = datetime.strptime(received_at_raw, "%Y-%m-%dT%H:%M")
        except ValueError:
            flash("收货时间格式错误。", "danger")
            return render_template(
                "procurement/receipt_form.html",
                row=row,
                companies=companies,
                orders=orders,
                company_id=company_id,
                receipt_statuses=RECEIPT_STATUS,
            )
        was_posted = False
        if not row:
            row = PurchaseReceipt(
                receipt_no=_next_no("RCV", PurchaseReceipt, "receipt_no"),
                receiver_user_id=int(current_user.get_id()),
            )
            db.session.add(row)
        else:
            was_posted = row.status == "posted"
        row.company_id = company_id
        row.purchase_order_id = purchase_order_id
        row.received_qty = received_qty
        row.received_at = received_at
        row.status = status
        row.remark = remark
        posting_now = (not was_posted) and status == "posted"
        if posting_now:
            sin = PurchaseStockIn(
                company_id=company_id,
                stock_in_no=_next_no("SIN", PurchaseStockIn, "stock_in_no"),
                receipt=row,
                qty=received_qty,
                storage_area=storage_area,
                stock_in_at=received_at,
                created_by=int(current_user.get_id()),
                remark=f"由收货单 {row.receipt_no or '(新建)'} 生成",
            )
            db.session.add(sin)
            orchestrator_engine.emit_event(
                event_type=EVENT_PROCUREMENT_RECEIVED,
                biz_key=f"receipt:{row.id or 0}",
                payload={
                    "source_id": int(row.id or 0),
                    "version": int(received_at.timestamp()),
                    "source": "routes_procurement._save_receipt",
                },
            )
        _sync_po_status_from_receipts(po)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("收货单号冲突，请重试。", "danger")
            return render_template(
                "procurement/receipt_form.html",
                row=row,
                companies=companies,
                orders=orders,
                company_id=company_id,
                receipt_statuses=RECEIPT_STATUS,
            )
        flash("收货单已保存。", "success")
        return redirect(url_for("main.procurement_receipt_list", company_id=company_id))

    @bp.route("/purchase-receipts/<int:receipt_id>/delete", methods=["POST"])
    @login_required
    @menu_required("procurement_receipt")
    @capability_required("procurement_receipt.action.delete")
    def procurement_receipt_delete(receipt_id):
        row = PurchaseReceipt.query.get_or_404(receipt_id)
        if PurchaseStockIn.query.filter_by(receipt_id=row.id).first():
            flash("该收货单已入库，不能删除。", "danger")
            return redirect(url_for("main.procurement_receipt_list", company_id=row.company_id))
        po = row.purchase_order
        cid = row.company_id
        db.session.delete(row)
        if po:
            _sync_po_status_from_receipts(po)
        db.session.commit()
        flash("收货单已删除。", "success")
        return redirect(url_for("main.procurement_receipt_list", company_id=cid))

    @bp.route("/purchase-stock-ins")
    @login_required
    @menu_required("procurement_stockin")
    def procurement_stockin_list():
        company_id, companies = _resolve_company_id()
        keyword = (request.args.get("keyword") or "").strip()
        q = PurchaseStockIn.query
        if company_id:
            q = q.filter(PurchaseStockIn.company_id == company_id)
        if current_user_can_cap("procurement_stockin.filter.keyword") and keyword:
            q = q.filter(
                or_(
                    PurchaseStockIn.stock_in_no.contains(keyword),
                    PurchaseStockIn.storage_area.contains(keyword),
                )
            )
        rows = q.order_by(PurchaseStockIn.id.desc()).all()
        return render_template(
            "procurement/stockin_list.html",
            rows=rows,
            companies=companies,
            company_id=company_id,
            keyword=keyword,
        )
