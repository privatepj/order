from app import db


class Customer(db.Model):
    __tablename__ = "customer"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    customer_code = db.Column(db.String(64), nullable=False, unique=True)
    short_code = db.Column(db.String(32), nullable=True)
    name = db.Column(db.String(128), nullable=False)
    contact = db.Column(db.String(64))
    phone = db.Column(db.String(32))
    fax = db.Column(db.String(32))
    address = db.Column(db.String(255))
    payment_terms = db.Column(db.String(64))
    remark = db.Column(db.String(255))
    company_id = db.Column(db.Integer, nullable=False)  # 关联 company.id，不在库建外键
    tax_point = db.Column(db.Numeric(26, 8))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    orders = db.relationship(
        "SalesOrder", primaryjoin="Customer.id == foreign(SalesOrder.customer_id)", backref="customer", lazy="dynamic"
    )
    deliveries = db.relationship(
        "Delivery", primaryjoin="Customer.id == foreign(Delivery.customer_id)", backref="customer", lazy="dynamic"
    )
    customer_products = db.relationship(
        "CustomerProduct", primaryjoin="Customer.id == foreign(CustomerProduct.customer_id)", backref="customer", lazy="dynamic"
    )
