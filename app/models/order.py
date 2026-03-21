from app import db
from decimal import Decimal


class SalesOrder(db.Model):
    __tablename__ = "sales_order"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_no = db.Column(db.String(64), nullable=False, unique=True)
    customer_order_no = db.Column(db.String(64))
    customer_id = db.Column(db.Integer, nullable=False)  # 关联 customer.id，不在库建外键
    salesperson = db.Column(db.String(64), nullable=False, default="GaoMeiHua")
    order_date = db.Column(db.Date)
    required_date = db.Column(db.Date)
    status = db.Column(db.String(32), nullable=False, default="pending")
    # monthly=月结 cash=现金（sample=样板为旧数据兼容，系统不再新建）
    payment_type = db.Column(db.String(16), nullable=False, default="monthly")
    remark = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    items = db.relationship(
        "OrderItem",
        primaryjoin="SalesOrder.id == foreign(OrderItem.order_id)",
        backref="order",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="OrderItem.id",
    )


class OrderItem(db.Model):
    __tablename__ = "order_item"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, nullable=False)  # 关联 sales_order.id，不在库建外键
    customer_product_id = db.Column(db.Integer, nullable=True)  # 关联 customer_product.id，不在库建外键
    product_name = db.Column(db.String(128))
    product_spec = db.Column(db.String(128))
    customer_material_no = db.Column(db.String(64))
    quantity = db.Column(db.Numeric(18, 4), default=0, nullable=False)
    unit = db.Column(db.String(16))
    price = db.Column(db.Numeric(18, 4))
    amount = db.Column(db.Numeric(18, 2))
    is_sample = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    delivery_items = db.relationship(
        "DeliveryItem", primaryjoin="OrderItem.id == foreign(DeliveryItem.order_item_id)", backref="order_item", lazy="dynamic"
    )
    customer_product = db.relationship(
        "CustomerProduct", primaryjoin="foreign(OrderItem.customer_product_id) == CustomerProduct.id", backref="order_items", lazy=True
    )

    def compute_amount(self):
        if self.price is not None and self.quantity is not None:
            self.amount = Decimal(str(self.quantity)) * Decimal(str(self.price))
