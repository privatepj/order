from datetime import date
from decimal import Decimal, InvalidOperation

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app import db
from app.auth.capabilities import current_user_can_cap, inventory_stock_query_read_filters
from app.auth.decorators import capability_required, menu_required
from app.models import (
    InventoryDailyLine,
    InventoryDailyRecord,
    InventoryMovement,
    InventoryOpeningBalance,
    Product,
    User,
)
from app.services import inventory_svc
from app.utils.query import keyword_like_or


def _parse_line_rows():
    """从表单解析 (product_id, quantity, unit, note) 列表；非法时 raise ValueError。"""
    pids = request.form.getlist("line_product_id")
    qtys = request.form.getlist("line_quantity")
    units = request.form.getlist("line_unit")
    notes = request.form.getlist("line_note")
    rows = []
    seen_pid = set()
    for i, pid in enumerate(pids):
        pid = (pid or "").strip()
        if not pid:
            continue
        try:
            product_id = int(pid)
        except ValueError:
            continue
        if product_id in seen_pid:
            raise ValueError("同一单据中不能重复选择同一产品。")
        seen_pid.add(product_id)
        qraw = (qtys[i] if i < len(qtys) else "") or "0"
        qraw = str(qraw).strip()
        try:
            qty = Decimal(qraw)
        except InvalidOperation:
            raise ValueError("数量格式不正确。")
        if qty < 0:
            raise ValueError("数量不能为负数。")
        unit = (units[i] if i < len(units) else None) or None
        if unit:
            unit = unit.strip()[:16] or None
        note = (notes[i] if i < len(notes) else None) or None
        if note:
            note = note.strip()[:255] or None
        rows.append((product_id, qty, unit, note))
    return rows


def _validate_products(product_ids):
    if not product_ids:
        return
    cnt = Product.query.filter(Product.id.in_(product_ids)).count()
    if cnt != len(set(product_ids)):
        raise ValueError("存在无效的产品。")


def _parse_movement_line_rows():
    """解析批量手工出入库行：(product_id, storage_area, quantity, unit, remark)；非法时 raise ValueError。"""
    pids = request.form.getlist("line_product_id")
    areas = request.form.getlist("line_storage_area")
    qtys = request.form.getlist("line_quantity")
    units = request.form.getlist("line_unit")
    remarks = request.form.getlist("line_remark")
    rows = []
    for i, pid in enumerate(pids):
        pid = (pid or "").strip()
        if not pid:
            continue
        try:
            product_id = int(pid)
        except ValueError:
            continue
        area = (areas[i] if i < len(areas) else "") or ""
        area = area.strip()
        if not area:
            raise ValueError("每一行有产品的记录都必须填写仓储区。")
        qraw = (qtys[i] if i < len(qtys) else "") or "0"
        qraw = str(qraw).strip()
        try:
            qty = Decimal(qraw)
        except InvalidOperation:
            raise ValueError("数量格式不正确。")
        if qty <= 0:
            raise ValueError("每一行数量须大于 0。")
        unit = (units[i] if i < len(units) else None) or None
        if unit:
            unit = unit.strip()[:16] or None
        remark = (remarks[i] if i < len(remarks) else None) or None
        if remark:
            remark = remark.strip()[:255] or None
        rows.append((product_id, area, qty, unit, remark))
    return rows


def register_inventory_routes(bp):
    # ----- API：产品搜索（库存录入用） -----
    @bp.route("/api/inventory/products-search", methods=["GET"])
    @login_required
    @menu_required("inventory_ops")
    def inventory_products_search():
        if not current_user_can_cap("inventory_ops.api.products_search"):
            abort(403)
        qstr = (request.args.get("q") or "").strip()
        limit = request.args.get("limit", 50, type=int)
        limit = max(1, min(limit, 100))
        q = Product.query.order_by(Product.product_code)
        cond = keyword_like_or(
            qstr,
            Product.product_code,
            Product.name,
            Product.spec,
            Product.base_unit,
            Product.remark,
        )
        if cond is not None:
            q = q.filter(cond)
        items = []
        for p in q.limit(limit).all():
            label = f"{p.product_code} — {p.name}"
            if p.spec:
                label += f"（{p.spec}）"
            items.append(
                {
                    "id": p.id,
                    "label": label,
                    "spec": p.spec or "",
                    "base_unit": p.base_unit or "",
                    "category": inventory_svc.INV_FINISHED,
                }
            )
        return jsonify({"items": items})

    @bp.route("/api/inventory/suggest-storage-area", methods=["GET"])
    @login_required
    @menu_required("inventory_ops")
    def inventory_suggest_storage_area():
        pid = request.args.get("product_id", type=int)
        if not pid:
            return jsonify({"storage_area": ""})
        area = inventory_svc.suggest_storage_area_for_product(pid)
        return jsonify({"storage_area": area})

    # ----- 库存查询（结存聚合） -----
    @bp.route("/inventory/query")
    @login_required
    @menu_required("inventory_query")
    def inventory_stock_query():
        page, category, storage_area, spec_kw, name_spec_kw = inventory_stock_query_read_filters()
        rows, total = inventory_svc.query_stock_aggregate(
            category=category,
            storage_area_kw=storage_area,
            spec_kw=spec_kw,
            name_spec_kw=name_spec_kw,
            page=page,
            per_page=30,
        )
        total_pages = (total + 30 - 1) // 30 if total else 1
        return render_template(
            "inventory/stock_query.html",
            rows=rows,
            page=page,
            total=total,
            total_pages=total_pages,
            category=category,
            storage_area=storage_area,
            spec_kw=spec_kw,
            name_spec_kw=name_spec_kw,
        )

    # ----- 库存录入（批量手工出入库） -----
    @bp.route("/inventory/movement/new", methods=["GET", "POST"])
    @login_required
    @menu_required("inventory_ops")
    @capability_required("inventory_ops.movement.create")
    def inventory_movement_new():
        if request.method == "POST":
            try:
                cat = (request.form.get("category") or "").strip()
                if cat == inventory_svc.INV_SEMI:
                    raise ValueError("半成品出入库尚未接入物料表，暂不可保存。")
                if cat != inventory_svc.INV_FINISHED:
                    raise ValueError("请选择类别。")
                direction = (request.form.get("direction") or "").strip()
                if direction not in ("in", "out"):
                    raise ValueError("请选择入库或出库。")
                rd = request.form.get("biz_date") or ""
                biz_date = date.fromisoformat(rd) if rd else None
                if not biz_date:
                    raise ValueError("请选择业务日期。")
                line_rows = _parse_movement_line_rows()
                if not line_rows:
                    raise ValueError("请至少录入一行有效的产品、仓储区与数量。")
                _validate_products([r[0] for r in line_rows])
                for product_id, area, qty, unit, remark in line_rows:
                    p = Product.query.get(product_id)
                    if not p:
                        raise ValueError("存在无效的产品。")
                    inventory_svc.create_manual_movement(
                        category=inventory_svc.INV_FINISHED,
                        direction=direction,
                        product_id=product_id,
                        material_id=0,
                        storage_area=area,
                        quantity=qty,
                        unit=unit or (p.base_unit or None),
                        biz_date=biz_date,
                        remark=remark,
                        created_by=current_user.id,
                    )
                db.session.commit()
                flash(f"已保存 {len(line_rows)} 条库存流水。", "success")
                return redirect(url_for("main.inventory_list"))
            except ValueError as e:
                db.session.rollback()
                flash(str(e), "danger")
            except InvalidOperation:
                db.session.rollback()
                flash("数量格式不正确。", "danger")
            except IntegrityError:
                db.session.rollback()
                flash("保存失败：数据冲突。", "danger")
        today = date.today().isoformat()
        return render_template(
            "inventory/movement_form.html",
            default_biz_date=today,
        )

    # ----- 进出明细列表（主「库存」入口） -----
    @bp.route("/inventory")
    @login_required
    @menu_required("inventory_ops")
    def inventory_list():
        page = request.args.get("page", 1, type=int)
        q = InventoryMovement.query.options(
            selectinload(InventoryMovement.product)
        ).order_by(
            InventoryMovement.biz_date.desc(),
            InventoryMovement.id.desc(),
        )
        pagination = q.paginate(page=page, per_page=30)
        uid_set = {m.created_by for m in pagination.items}
        users = (
            {
                u.id: (u.name or u.username)
                for u in User.query.filter(User.id.in_(uid_set)).all()
            }
            if uid_set
            else {}
        )
        return render_template(
            "inventory/movement_list.html",
            pagination=pagination,
            creators=users,
        )

    @bp.route("/inventory/movement/<int:movement_id>/delete", methods=["POST"])
    @login_required
    @menu_required("inventory_ops")
    @capability_required("inventory_ops.movement.delete")
    def inventory_movement_delete(movement_id):
        m = InventoryMovement.query.get_or_404(movement_id)
        if m.source_type != inventory_svc.SOURCE_MANUAL:
            flash("仅可删除手工录入的流水。", "warning")
            return redirect(url_for("main.inventory_list"))
        db.session.delete(m)
        db.session.commit()
        flash("已删除该条流水。", "success")
        return redirect(url_for("main.inventory_list"))

    # ----- 期初结存维护 -----
    @bp.route("/inventory/opening")
    @login_required
    @menu_required("inventory_ops")
    @capability_required("inventory_ops.opening.list")
    def inventory_opening_list():
        page = request.args.get("page", 1, type=int)
        q = InventoryOpeningBalance.query.options(
            selectinload(InventoryOpeningBalance.product)
        ).order_by(
            InventoryOpeningBalance.storage_area,
            InventoryOpeningBalance.id,
        )
        pagination = q.paginate(page=page, per_page=30)
        return render_template(
            "inventory/opening_list.html",
            pagination=pagination,
        )

    @bp.route("/inventory/opening/new", methods=["GET", "POST"])
    @login_required
    @menu_required("inventory_ops")
    def inventory_opening_new():
        if request.method == "POST":
            try:
                cat = (request.form.get("category") or "").strip()
                if cat == inventory_svc.INV_SEMI:
                    raise ValueError("半成品期初尚未接入物料表，请仅维护成品。")
                if cat != inventory_svc.INV_FINISHED:
                    raise ValueError("请选择类别。")
                pid = int((request.form.get("product_id") or "").strip())
                if not Product.query.get(pid):
                    raise ValueError("产品无效。")
                area = (request.form.get("storage_area") or "").strip()
                if not area:
                    raise ValueError("请填写仓储区。")
                qraw = (request.form.get("opening_qty") or "").strip()
                oq = Decimal(qraw)
                unit = (request.form.get("unit") or "").strip() or None
                remark = (request.form.get("remark") or "").strip() or None
                row = InventoryOpeningBalance(
                    category=inventory_svc.INV_FINISHED,
                    product_id=pid,
                    material_id=0,
                    storage_area=area[:32],
                    opening_qty=oq,
                    unit=unit[:16] if unit else None,
                    remark=remark[:255] if remark else None,
                )
                db.session.add(row)
                db.session.commit()
                flash("期初已保存。", "success")
                return redirect(url_for("main.inventory_opening_list"))
            except ValueError as e:
                db.session.rollback()
                flash(str(e), "danger")
            except InvalidOperation:
                db.session.rollback()
                flash("数量格式不正确。", "danger")
            except IntegrityError:
                db.session.rollback()
                flash("该维度已存在期初，请编辑原记录。", "danger")
        return render_template("inventory/opening_form.html", row=None)

    @bp.route("/inventory/opening/<int:opening_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("inventory_ops")
    @capability_required("inventory_ops.opening.edit")
    def inventory_opening_edit(opening_id):
        row = InventoryOpeningBalance.query.options(
            selectinload(InventoryOpeningBalance.product)
        ).get_or_404(opening_id)
        if request.method == "POST":
            try:
                qraw = (request.form.get("opening_qty") or "").strip()
                row.opening_qty = Decimal(qraw)
                row.unit = (request.form.get("unit") or "").strip()[:16] or None
                row.remark = (request.form.get("remark") or "").strip()[:255] or None
                db.session.commit()
                flash("已更新。", "success")
                return redirect(url_for("main.inventory_opening_list"))
            except InvalidOperation:
                db.session.rollback()
                flash("数量格式不正确。", "danger")
        return render_template("inventory/opening_form.html", row=row)

    @bp.route("/inventory/opening/<int:opening_id>/delete", methods=["POST"])
    @login_required
    @menu_required("inventory_ops")
    @capability_required("inventory_ops.opening.delete")
    def inventory_opening_delete(opening_id):
        row = InventoryOpeningBalance.query.get_or_404(opening_id)
        db.session.delete(row)
        db.session.commit()
        flash("已删除该条期初。", "success")
        return redirect(url_for("main.inventory_opening_list"))

    # ----- 历史：每日库存快照（旧功能） -----
    @bp.route("/inventory/daily")
    @login_required
    @menu_required("inventory_ops")
    def inventory_daily_list():
        page = request.args.get("page", 1, type=int)
        q = InventoryDailyRecord.query.options(
            selectinload(InventoryDailyRecord.lines)
        ).order_by(
            InventoryDailyRecord.record_date.desc(),
            InventoryDailyRecord.id.desc(),
        )
        pagination = q.paginate(page=page, per_page=20)
        cid_set = {r.created_by for r in pagination.items}
        creators = (
            {
                u.id: (u.name or u.username)
                for u in User.query.filter(User.id.in_(cid_set)).all()
            }
            if cid_set
            else {}
        )
        return render_template(
            "inventory/daily_list.html",
            pagination=pagination,
            creators=creators,
        )

    @bp.route("/inventory/daily/new", methods=["GET", "POST"])
    @login_required
    @menu_required("inventory_ops")
    @capability_required("inventory_ops.daily.create")
    def inventory_daily_new():
        if request.method == "POST":
            try:
                rd = request.form.get("record_date") or ""
                record_date = date.fromisoformat(rd) if rd else None
                if not record_date:
                    raise ValueError("请选择业务日期。")
                status = (request.form.get("status") or "confirmed").strip()
                if status not in ("draft", "confirmed"):
                    status = "confirmed"
                remark = (request.form.get("remark") or "").strip()[:500] or None
                rows = _parse_line_rows()
                if not rows:
                    raise ValueError("请至少录入一行产品数量。")
                _validate_products([r[0] for r in rows])
                rec = InventoryDailyRecord(
                    record_date=record_date,
                    status=status,
                    remark=remark,
                    created_by=current_user.id,
                )
                db.session.add(rec)
                db.session.flush()
                for product_id, qty, unit, note in rows:
                    db.session.add(
                        InventoryDailyLine(
                            header_id=rec.id,
                            product_id=product_id,
                            quantity=qty,
                            unit=unit,
                            note=note,
                        )
                    )
                db.session.commit()
                flash("每日库存录入已保存。", "success")
                return redirect(
                    url_for("main.inventory_daily_detail", record_id=rec.id)
                )
            except ValueError as e:
                db.session.rollback()
                flash(str(e), "danger")
            except IntegrityError:
                db.session.rollback()
                flash("保存失败：产品重复或数据冲突。", "danger")
        today = date.today().isoformat()
        return render_template(
            "inventory/daily_form.html",
            record=None,
            lines=None,
            default_record_date=today,
        )

    @bp.route("/inventory/daily/<int:record_id>")
    @login_required
    @menu_required("inventory_ops")
    def inventory_daily_detail(record_id):
        record = InventoryDailyRecord.query.options(
            selectinload(InventoryDailyRecord.lines).selectinload(
                InventoryDailyLine.product
            )
        ).get_or_404(record_id)
        creator = User.query.get(record.created_by)
        creator_label = (
            (creator.name or creator.username) if creator else str(record.created_by)
        )
        return render_template(
            "inventory/daily_detail.html",
            record=record,
            creator_label=creator_label,
        )

    @bp.route("/inventory/daily/<int:record_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("inventory_ops")
    def inventory_daily_edit(record_id):
        record = InventoryDailyRecord.query.options(
            selectinload(InventoryDailyRecord.lines).selectinload(
                InventoryDailyLine.product
            )
        ).get_or_404(record_id)
        if request.method == "POST":
            try:
                rd = request.form.get("record_date") or ""
                record_date = date.fromisoformat(rd) if rd else None
                if not record_date:
                    raise ValueError("请选择业务日期。")
                status = (request.form.get("status") or "confirmed").strip()
                if status not in ("draft", "confirmed"):
                    status = "confirmed"
                remark = (request.form.get("remark") or "").strip()[:500] or None
                rows = _parse_line_rows()
                if not rows:
                    raise ValueError("请至少录入一行产品数量。")
                _validate_products([r[0] for r in rows])
                record.record_date = record_date
                record.status = status
                record.remark = remark
                InventoryDailyLine.query.filter_by(header_id=record.id).delete(
                    synchronize_session=False
                )
                for product_id, qty, unit, note in rows:
                    db.session.add(
                        InventoryDailyLine(
                            header_id=record.id,
                            product_id=product_id,
                            quantity=qty,
                            unit=unit,
                            note=note,
                        )
                    )
                db.session.commit()
                flash("已更新。", "success")
                return redirect(
                    url_for("main.inventory_daily_detail", record_id=record.id)
                )
            except ValueError as e:
                db.session.rollback()
                flash(str(e), "danger")
            except IntegrityError:
                db.session.rollback()
                flash("保存失败：产品重复或数据冲突。", "danger")
        record = InventoryDailyRecord.query.options(
            selectinload(InventoryDailyRecord.lines).selectinload(
                InventoryDailyLine.product
            )
        ).get_or_404(record_id)
        lines = list(record.lines)
        return render_template(
            "inventory/daily_form.html",
            record=record,
            lines=lines,
            default_record_date=record.record_date.isoformat(),
        )

    @bp.route("/inventory/daily/<int:record_id>/delete", methods=["POST"])
    @login_required
    @menu_required("inventory_ops")
    @capability_required("inventory_ops.daily.delete")
    def inventory_daily_delete(record_id):
        record = InventoryDailyRecord.query.get_or_404(record_id)
        db.session.delete(record)
        db.session.commit()
        flash("已删除该条每日录入。", "success")
        return redirect(url_for("main.inventory_daily_list"))
