from __future__ import annotations

from typing import Any, Dict

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy.orm import joinedload

from app import db
from app.auth.decorators import capability_required, menu_required
from app.auth.capabilities import current_user_can_cap
from app.models import (
    CrmLead,
    CrmOpportunity,
    CrmTicket,
    Customer,
    CustomerProduct,
    SalesOrder,
    User,
)
from app.services.crm_lead_svc import create_lead_from_data, update_lead_from_data
from app.services.crm_opportunity_svc import (
    add_opportunity_line,
    create_opportunity_from_data,
    generate_order_from_opportunity,
    remove_opportunity_line,
    set_opportunity_stage,
    update_opportunity_from_data,
)
from app.services.crm_ticket_svc import (
    add_ticket_activity,
    create_ticket_from_data,
    set_ticket_status,
    update_ticket_from_data,
)


def register_crm_routes(bp):
    # -------------------------
    # Lead（线索）
    # -------------------------
    @bp.route("/crm/leads")
    @login_required
    @menu_required("crm_lead")
    def crm_lead_list():
        status = (request.args.get("status") or "").strip()
        q = CrmLead.query
        if status:
            q = q.filter(CrmLead.status == status)
        q = q.order_by(CrmLead.id.desc())
        leads = q.all()
        return render_template("crm/lead/list.html", leads=leads, status=status)

    @bp.route("/crm/leads/new", methods=["GET", "POST"])
    @login_required
    @menu_required("crm_lead")
    @capability_required("crm_lead.action.create")
    def crm_lead_new():
        customers = Customer.query.order_by(Customer.name).all()
        if request.method == "POST":
            payload = _lead_form_payload()
            payload["customer_id"] = request.form.get("customer_id", type=int)
            lead, err = create_lead_from_data(payload)
            if err:
                flash(err, "danger")
            else:
                flash("线索已创建。", "success")
                return redirect(url_for("main.crm_lead_list"))

        return render_template(
            "crm/lead/form.html",
            lead=None,
            customers=customers,
        )

    @bp.route("/crm/leads/<int:lead_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("crm_lead")
    @capability_required("crm_lead.action.edit")
    def crm_lead_edit(lead_id: int):
        lead = CrmLead.query.get_or_404(lead_id)
        customers = Customer.query.order_by(Customer.name).all()
        if request.method == "POST":
            payload = _lead_form_payload()
            payload["customer_id"] = request.form.get("customer_id", type=int)
            err = update_lead_from_data(lead, payload)
            if err:
                flash(err, "danger")
            else:
                flash("线索已保存。", "success")
                return redirect(url_for("main.crm_lead_list"))

        return render_template(
            "crm/lead/form.html",
            lead=lead,
            customers=customers,
        )

    @bp.route("/crm/leads/<int:lead_id>/delete", methods=["POST"])
    @login_required
    @menu_required("crm_lead")
    @capability_required("crm_lead.action.delete")
    def crm_lead_delete(lead_id: int):
        lead = CrmLead.query.get_or_404(lead_id)
        db.session.delete(lead)
        db.session.commit()
        flash("线索已删除。", "success")
        return redirect(url_for("main.crm_lead_list"))

    @bp.route("/crm/leads/<int:lead_id>/to-opportunity", methods=["POST"])
    @login_required
    @menu_required("crm_opportunity")
    @capability_required("crm_opportunity.action.create")
    def crm_lead_to_opportunity(lead_id: int):
        lead = CrmLead.query.get_or_404(lead_id)
        if not lead.customer_id:
            flash("该线索尚未关联客户，无法生成机会。请先在该线索中选择客户。", "danger")
            return redirect(url_for("main.crm_lead_edit", lead_id=lead.id))
        opp, err = create_opportunity_from_data(
            {"lead_id": lead.id, "customer_id": lead.customer_id, "stage": "draft"}
        )
        if err:
            flash(err, "danger")
            return redirect(url_for("main.crm_lead_list"))
        flash("机会已创建。", "success")
        return redirect(url_for("main.crm_opportunity_edit", opp_id=opp.id))

    # -------------------------
    # Opportunity（机会）& Line
    # -------------------------
    @bp.route("/crm/opportunities")
    @login_required
    @menu_required("crm_opportunity")
    def crm_opportunity_list():
        stage = (request.args.get("stage") or "").strip()
        q = CrmOpportunity.query.options(joinedload(CrmOpportunity.customer))
        if stage:
            q = q.filter(CrmOpportunity.stage == stage)
        q = q.order_by(CrmOpportunity.id.desc())
        opps = q.all()
        return render_template("crm/opportunity/list.html", opps=opps, stage=stage)

    @bp.route("/crm/opportunities/new", methods=["GET", "POST"])
    @login_required
    @menu_required("crm_opportunity")
    @capability_required("crm_opportunity.action.create")
    def crm_opportunity_new():
        customers = Customer.query.order_by(Customer.name).all()
        leads = CrmLead.query.order_by(CrmLead.id.desc()).all()
        if request.method == "POST":
            lead_id = request.form.get("lead_id", type=int)
            payload = _opportunity_form_payload()
            payload["lead_id"] = lead_id
            payload["customer_id"] = request.form.get("customer_id", type=int)
            payload["stage"] = request.form.get("stage") or payload.get("stage") or "draft"
            opp, err = create_opportunity_from_data(payload)
            if err:
                flash(err, "danger")
            else:
                flash("机会已创建。", "success")
                return redirect(url_for("main.crm_opportunity_edit", opp_id=opp.id))

        return render_template(
            "crm/opportunity/form.html",
            opp=None,
            customers=customers,
            leads=leads,
        )

    @bp.route("/crm/opportunities/<int:opp_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("crm_opportunity")
    @capability_required("crm_opportunity.action.edit")
    def crm_opportunity_edit(opp_id: int):
        opp = CrmOpportunity.query.options(joinedload(CrmOpportunity.customer)).get_or_404(opp_id)
        customers = Customer.query.order_by(Customer.name).all()
        leads = CrmLead.query.order_by(CrmLead.id.desc()).all()
        if request.method == "POST":
            lead_id = request.form.get("lead_id", type=int)
            payload = _opportunity_form_payload()
            payload["lead_id"] = lead_id
            payload["customer_id"] = request.form.get("customer_id", type=int)
            payload["stage"] = request.form.get("stage") or payload.get("stage") or opp.stage
            err = update_opportunity_from_data(opp, payload)
            if err:
                flash(err, "danger")
            else:
                flash("机会已保存。", "success")
                return redirect(url_for("main.crm_opportunity_edit", opp_id=opp.id))

        return render_template(
            "crm/opportunity/form.html",
            opp=opp,
            customers=customers,
            leads=leads,
        )

    @bp.route("/crm/opportunities/<int:opp_id>/lines", methods=["GET", "POST"])
    @login_required
    @menu_required("crm_opportunity")
    def crm_opportunity_lines(opp_id: int):
        opp = CrmOpportunity.query.options(joinedload(CrmOpportunity.lines)).get_or_404(opp_id)
        cps = CustomerProduct.query.options(joinedload(CustomerProduct.product)).filter_by(
            customer_id=opp.customer_id
        ).order_by(CustomerProduct.id).all()
        if request.method == "POST":
            if not current_user_can_cap("crm_opportunity.action.edit"):
                abort(403)
            if not request.form.get("customer_product_id"):
                flash("请选择客户产品。", "danger")
            else:
                cp_id = request.form.get("customer_product_id", type=int)
                quantity = request.form.get("quantity")
                is_sample = request.form.get("is_sample") == "on"
                is_spare = request.form.get("is_spare") == "on"
                line_remark = (request.form.get("remark") or "").strip() or None
                line, err = add_opportunity_line(
                    opp,
                    customer_product_id=cp_id,
                    quantity=quantity,
                    is_sample=is_sample,
                    is_spare=is_spare,
                    remark=line_remark,
                )
                if err:
                    flash(err, "danger")
                else:
                    flash("机会产品行已保存。", "success")
            return redirect(url_for("main.crm_opportunity_lines", opp_id=opp.id))

        return render_template(
            "crm/opportunity/lines.html",
            opp=opp,
            cps=cps,
        )

    @bp.route("/crm/opportunities/<int:opp_id>/lines/<int:line_id>/delete", methods=["POST"])
    @login_required
    @menu_required("crm_opportunity")
    @capability_required("crm_opportunity.action.edit")
    def crm_opportunity_line_delete(opp_id: int, line_id: int):
        opp = CrmOpportunity.query.get_or_404(opp_id)
        remove_opportunity_line(opp, line_id)
        flash("产品行已删除。", "success")
        return redirect(url_for("main.crm_opportunity_lines", opp_id=opp.id))

    @bp.route("/crm/opportunities/<int:opp_id>/set-stage", methods=["POST"])
    @login_required
    @menu_required("crm_opportunity")
    @capability_required("crm_opportunity.action.edit")
    def crm_opportunity_set_stage(opp_id: int):
        opp = CrmOpportunity.query.get_or_404(opp_id)
        next_stage = request.form.get("stage") or ""
        err = set_opportunity_stage(opp, next_stage)
        if err:
            flash(err, "danger")
        else:
            flash("机会状态已更新。", "success")
        return redirect(url_for("main.crm_opportunity_edit", opp_id=opp.id))

    @bp.route("/crm/opportunities/<int:opp_id>/generate-order", methods=["GET", "POST"])
    @login_required
    @menu_required("crm_opportunity")
    @capability_required("crm_opportunity.action.generate_order")
    def crm_opportunity_generate_order(opp_id: int):
        opp = CrmOpportunity.query.options(joinedload(CrmOpportunity.lines)).get_or_404(opp_id)
        order = None
        if request.method == "POST":
            generation_data = {
                "customer_order_no": request.form.get("customer_order_no") or None,
                "salesperson": request.form.get("salesperson") or None,
                "order_date": request.form.get("order_date") or None,
                "required_date": request.form.get("required_date") or None,
                "payment_type": request.form.get("payment_type") or None,
                "remark": request.form.get("remark") or None,
            }
            order, err = generate_order_from_opportunity(opp.id, generation_data=generation_data)
            if err:
                flash(err, "danger")
            else:
                flash("订单已生成。", "success")
                return redirect(url_for("main.order_edit", order_id=order.id))

        if opp.won_order_id:
            order = SalesOrder.query.get(opp.won_order_id)
        return render_template(
            "crm/opportunity/generate_order.html",
            opp=opp,
            order=order,
        )

    # -------------------------
    # Ticket（工单）
    # -------------------------
    @bp.route("/crm/tickets")
    @login_required
    @menu_required("crm_ticket")
    def crm_ticket_list():
        status = (request.args.get("status") or "").strip()
        q = CrmTicket.query.options(joinedload(CrmTicket.customer))
        if status:
            q = q.filter(CrmTicket.status == status)
        q = q.order_by(CrmTicket.id.desc())
        tickets = q.all()
        return render_template("crm/ticket/list.html", tickets=tickets, status=status)

    @bp.route("/crm/tickets/new", methods=["GET", "POST"])
    @login_required
    @menu_required("crm_ticket")
    @capability_required("crm_ticket.action.create")
    def crm_ticket_new():
        customers = Customer.query.order_by(Customer.name).all()
        users = User.query.order_by(User.id.asc()).all()
        if request.method == "POST":
            payload = _ticket_form_payload()
            payload["customer_id"] = request.form.get("customer_id", type=int)
            payload["assignee_user_id"] = request.form.get("assignee_user_id", type=int)
            ticket, err = create_ticket_from_data(payload)
            if err:
                flash(err, "danger")
            else:
                flash("工单已创建。", "success")
                return redirect(url_for("main.crm_ticket_detail", ticket_id=ticket.id))

        return render_template("crm/ticket/form.html", ticket=None, customers=customers, users=users)

    @bp.route("/crm/tickets/<int:ticket_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("crm_ticket")
    @capability_required("crm_ticket.action.edit")
    def crm_ticket_edit(ticket_id: int):
        ticket = CrmTicket.query.options(joinedload(CrmTicket.customer)).get_or_404(ticket_id)
        customers = Customer.query.order_by(Customer.name).all()
        users = User.query.order_by(User.id.asc()).all()
        if request.method == "POST":
            payload = _ticket_form_payload()
            payload["customer_id"] = request.form.get("customer_id", type=int)
            payload["assignee_user_id"] = request.form.get("assignee_user_id", type=int)
            err = update_ticket_from_data(ticket, payload)
            if err:
                flash(err, "danger")
            else:
                flash("工单已保存。", "success")
                return redirect(url_for("main.crm_ticket_detail", ticket_id=ticket.id))

        return render_template(
            "crm/ticket/form.html",
            ticket=ticket,
            customers=customers,
            users=users,
        )

    @bp.route("/crm/tickets/<int:ticket_id>/delete", methods=["POST"])
    @login_required
    @menu_required("crm_ticket")
    @capability_required("crm_ticket.action.delete")
    def crm_ticket_delete(ticket_id: int):
        ticket = CrmTicket.query.get_or_404(ticket_id)
        db.session.delete(ticket)
        db.session.commit()
        flash("工单已删除。", "success")
        return redirect(url_for("main.crm_ticket_list"))

    @bp.route("/crm/tickets/<int:ticket_id>")
    @login_required
    @menu_required("crm_ticket")
    def crm_ticket_detail(ticket_id: int):
        ticket = (
            CrmTicket.query.options(
                joinedload(CrmTicket.customer),
            )
            .options(joinedload(CrmTicket.activities))
            .get_or_404(ticket_id)
        )
        return render_template("crm/ticket/detail.html", ticket=ticket)

    @bp.route("/crm/tickets/<int:ticket_id>/activity/new", methods=["POST"])
    @login_required
    @menu_required("crm_ticket")
    @capability_required("crm_ticket.action.edit")
    def crm_ticket_activity_new(ticket_id: int):
        ticket = CrmTicket.query.get_or_404(ticket_id)
        actor_user_id = request.form.get("actor_user_id", type=int) or None
        activity_type = request.form.get("activity_type") or "note"
        content = request.form.get("content") or ""
        err = add_ticket_activity(
            ticket,
            actor_user_id=actor_user_id,
            activity_type=activity_type,
            content=content,
        )
        if err:
            flash(err, "danger")
        else:
            flash("活动已添加。", "success")
        return redirect(url_for("main.crm_ticket_detail", ticket_id=ticket.id))

    @bp.route("/crm/tickets/<int:ticket_id>/set-status", methods=["POST"])
    @login_required
    @menu_required("crm_ticket")
    @capability_required("crm_ticket.action.edit")
    def crm_ticket_set_status(ticket_id: int):
        ticket = CrmTicket.query.get_or_404(ticket_id)
        next_status = request.form.get("status") or ""
        err = set_ticket_status(ticket, next_status)
        if err:
            flash(err, "danger")
        else:
            flash("工单状态已更新。", "success")
        return redirect(url_for("main.crm_ticket_detail", ticket_id=ticket.id))


def _lead_form_payload() -> Dict[str, Any]:
    return {
        "customer_name": request.form.get("customer_name") or "",
        "contact": request.form.get("contact") or None,
        "phone": request.form.get("phone") or None,
        "source": request.form.get("source") or "manual",
        "status": request.form.get("status") or "new",
        "tags": request.form.get("tags") or None,
        "remark": request.form.get("remark") or None,
    }


def _opportunity_form_payload() -> Dict[str, Any]:
    # 期望字段均为字符串/可选，由 service 做类型解析
    return {
        "expected_amount": request.form.get("expected_amount") or None,
        "currency": request.form.get("currency") or None,
        "expected_close_date": request.form.get("expected_close_date") or None,
        "salesperson": request.form.get("salesperson") or None,
        "customer_order_no": request.form.get("customer_order_no") or None,
        "order_date": request.form.get("order_date") or None,
        "required_date": request.form.get("required_date") or None,
        "payment_type": request.form.get("payment_type") or None,
        "remark": request.form.get("remark") or None,
        "tags": request.form.get("tags") or None,
        "stage": request.form.get("stage") or None,
    }


def _ticket_form_payload() -> Dict[str, Any]:
    return {
        "ticket_type": request.form.get("ticket_type") or "support",
        "priority": request.form.get("priority") or "normal",
        "status": request.form.get("status") or None,
        "subject": request.form.get("subject") or None,
        "description": request.form.get("description") or None,
        "due_date": request.form.get("due_date") or None,
        "tags": request.form.get("tags") or None,
        "remark": request.form.get("remark") or None,
    }

