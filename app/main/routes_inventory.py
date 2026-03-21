from datetime import date
from decimal import Decimal, InvalidOperation

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app import db
from app.auth.decorators import menu_required
from app.models import InventoryDailyLine, InventoryDailyRecord, Product, User
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


def register_inventory_routes(bp):
    @bp.route("/api/inventory/products-search", methods=["GET"])
    @login_required
    @menu_required("inventory")
    def inventory_products_search():
        """产品编号/名称/规格/单位/备注模糊搜索，供库存录入行内选品。"""
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
        items = [
            {
                "id": p.id,
                "label": f"{p.product_code} — {p.name}"
                + (f"（{p.spec}）" if p.spec else ""),
            }
            for p in q.limit(limit).all()
        ]
        return jsonify({"items": items})

    @bp.route("/inventory")
    @login_required
    @menu_required("inventory")
    def inventory_list():
        page = request.args.get("page", 1, type=int)
        q = InventoryDailyRecord.query.options(
            selectinload(InventoryDailyRecord.lines)
        ).order_by(
            InventoryDailyRecord.record_date.desc(),
            InventoryDailyRecord.id.desc(),
        )
        pagination = q.paginate(page=page, per_page=20)
        creators = {
            u.id: (u.name or u.username)
            for u in User.query.filter(
                User.id.in_({r.created_by for r in pagination.items})
            ).all()
        }
        return render_template(
            "inventory/list.html",
            pagination=pagination,
            creators=creators,
        )

    @bp.route("/inventory/new", methods=["GET", "POST"])
    @login_required
    @menu_required("inventory")
    def inventory_new():
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
                flash("库存录入已保存。", "success")
                return redirect(url_for("main.inventory_detail", record_id=rec.id))
            except ValueError as e:
                db.session.rollback()
                flash(str(e), "danger")
            except IntegrityError:
                db.session.rollback()
                flash("保存失败：产品重复或数据冲突。", "danger")
        today = date.today().isoformat()
        return render_template(
            "inventory/form.html",
            record=None,
            lines=None,
            default_record_date=today,
        )

    @bp.route("/inventory/<int:record_id>")
    @login_required
    @menu_required("inventory")
    def inventory_detail(record_id):
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
            "inventory/detail.html",
            record=record,
            creator_label=creator_label,
        )

    @bp.route("/inventory/<int:record_id>/edit", methods=["GET", "POST"])
    @login_required
    @menu_required("inventory")
    def inventory_edit(record_id):
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
                return redirect(url_for("main.inventory_detail", record_id=record.id))
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
            "inventory/form.html",
            record=record,
            lines=lines,
            default_record_date=record.record_date.isoformat(),
        )

    @bp.route("/inventory/<int:record_id>/delete", methods=["POST"])
    @login_required
    @menu_required("inventory")
    def inventory_delete(record_id):
        record = InventoryDailyRecord.query.get_or_404(record_id)
        db.session.delete(record)
        db.session.commit()
        flash("已删除该条录入。", "success")
        return redirect(url_for("main.inventory_list"))
