from app import db


class Delivery(db.Model):
    __tablename__ = "delivery"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    delivery_no = db.Column(db.String(64), nullable=False, unique=True)
    delivery_date = db.Column(db.Date, nullable=False)
    customer_id = db.Column(db.Integer, nullable=False)  # 关联 customer.id，不在库建外键
    express_company_id = db.Column(db.Integer, nullable=True)  # NULL=自配送；否则关联 express_company.id
    express_waybill_id = db.Column(db.Integer, nullable=True)  # 关联 express_waybill.id，不在库建外键
    waybill_no = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="created")
    driver = db.Column(db.String(64))
    plate_no = db.Column(db.String(32))
    remark = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    express_company = db.relationship(
        "ExpressCompany", primaryjoin="foreign(Delivery.express_company_id) == ExpressCompany.id", lazy=True
    )

    items = db.relationship(
        "DeliveryItem",
        primaryjoin="Delivery.id == foreign(DeliveryItem.delivery_id)",
        backref="delivery",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )


class DeliveryItem(db.Model):
    __tablename__ = "delivery_item"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    delivery_id = db.Column(db.Integer, nullable=False)  # 关联 delivery.id，不在库建外键
    order_item_id = db.Column(db.Integer, nullable=False)  # 关联 order_item.id，不在库建外键
    order_id = db.Column(db.Integer, nullable=False)  # 关联 sales_order.id，不在库建外键
    product_name = db.Column(db.String(128))
    customer_material_no = db.Column(db.String(64))
    quantity = db.Column(db.Numeric(18, 4), default=0, nullable=False)
    unit = db.Column(db.String(16))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
