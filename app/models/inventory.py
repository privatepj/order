"""
每日库存快照（方案 A）：主表 + 明细行，数量按 product 维度登记。

未来若与送货出库自动扣减打通，可新增台账表 inventory_transaction，
对送货单写入 ref_type='delivery'、ref_id=<delivery.id>，与本快照对账或二选一为主数据。
多仓时再增加 warehouse 表及 record / line 上的 warehouse_id。
"""

from app import db


class InventoryDailyRecord(db.Model):
    __tablename__ = "inventory_daily_record"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    record_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="confirmed")
    remark = db.Column(db.String(500))
    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    lines = db.relationship(
        "InventoryDailyLine",
        primaryjoin="InventoryDailyRecord.id == foreign(InventoryDailyLine.header_id)",
        backref="header",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="InventoryDailyLine.id",
    )


class InventoryDailyLine(db.Model):
    __tablename__ = "inventory_daily_line"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    header_id = db.Column(db.Integer, nullable=False)
    product_id = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    unit = db.Column(db.String(16))
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    product = db.relationship(
        "Product",
        primaryjoin="foreign(InventoryDailyLine.product_id) == Product.id",
        lazy=True,
    )
