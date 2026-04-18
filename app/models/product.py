from app import db


class Product(db.Model):
    __tablename__ = "product"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_code = db.Column(db.String(64), nullable=False, unique=True)
    name = db.Column(db.String(128), nullable=False)
    spec = db.Column(db.String(128))
    series = db.Column(db.String(64))
    base_unit = db.Column(db.String(16))
    remark = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    customer_products = db.relationship(
        "CustomerProduct", primaryjoin="Product.id == foreign(CustomerProduct.product_id)", backref="product", lazy="dynamic"
    )


class CustomerProduct(db.Model):
    __tablename__ = "customer_product"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    customer_id = db.Column(db.Integer, nullable=False)  # 关联 customer.id，不在库建外键
    product_id = db.Column(db.Integer, nullable=False)  # 关联 product.id，不在库建外键
    customer_material_no = db.Column(db.String(64))
    material_no = db.Column(db.String(64))
    unit = db.Column(db.String(16))
    price = db.Column(db.Numeric(26, 8))
    currency = db.Column(db.String(8))
    remark = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

