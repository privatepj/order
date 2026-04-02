from app import db


class PurchaseRequisition(db.Model):
    __tablename__ = "purchase_requisition"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    req_no = db.Column(db.String(32), nullable=False, unique=True)
    requester_user_id = db.Column(db.Integer, nullable=False, index=True)
    supplier_name = db.Column(db.String(128), nullable=False)
    item_name = db.Column(db.String(128), nullable=False)
    item_spec = db.Column(db.String(128), nullable=True)
    qty = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    unit = db.Column(db.String(16), nullable=False, default="pcs")
    expected_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="draft")
    remark = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    company = db.relationship(
        "Company",
        primaryjoin="foreign(PurchaseRequisition.company_id) == Company.id",
        lazy=True,
    )
    requester = db.relationship(
        "User",
        primaryjoin="foreign(PurchaseRequisition.requester_user_id) == User.id",
        lazy=True,
    )
    purchase_orders = db.relationship(
        "PurchaseOrder",
        primaryjoin="PurchaseRequisition.id == foreign(PurchaseOrder.requisition_id)",
        back_populates="requisition",
        lazy="dynamic",
    )


class PurchaseOrder(db.Model):
    __tablename__ = "purchase_order"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    po_no = db.Column(db.String(32), nullable=False, unique=True)
    requisition_id = db.Column(db.Integer, nullable=True, index=True)
    buyer_user_id = db.Column(db.Integer, nullable=False, index=True)
    supplier_name = db.Column(db.String(128), nullable=False)
    item_name = db.Column(db.String(128), nullable=False)
    item_spec = db.Column(db.String(128), nullable=True)
    qty = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    unit = db.Column(db.String(16), nullable=False, default="pcs")
    unit_price = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    expected_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="draft")
    remark = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    company = db.relationship(
        "Company",
        primaryjoin="foreign(PurchaseOrder.company_id) == Company.id",
        lazy=True,
    )
    requisition = db.relationship(
        "PurchaseRequisition",
        primaryjoin="foreign(PurchaseOrder.requisition_id) == PurchaseRequisition.id",
        back_populates="purchase_orders",
        lazy=True,
    )
    buyer = db.relationship(
        "User",
        primaryjoin="foreign(PurchaseOrder.buyer_user_id) == User.id",
        lazy=True,
    )
    receipts = db.relationship(
        "PurchaseReceipt",
        primaryjoin="PurchaseOrder.id == foreign(PurchaseReceipt.purchase_order_id)",
        back_populates="purchase_order",
        lazy="dynamic",
    )


class PurchaseReceipt(db.Model):
    __tablename__ = "purchase_receipt"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    receipt_no = db.Column(db.String(32), nullable=False, unique=True)
    purchase_order_id = db.Column(db.Integer, nullable=False, index=True)
    receiver_user_id = db.Column(db.Integer, nullable=False, index=True)
    received_qty = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    received_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="draft")
    remark = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    company = db.relationship(
        "Company",
        primaryjoin="foreign(PurchaseReceipt.company_id) == Company.id",
        lazy=True,
    )
    purchase_order = db.relationship(
        "PurchaseOrder",
        primaryjoin="foreign(PurchaseReceipt.purchase_order_id) == PurchaseOrder.id",
        back_populates="receipts",
        lazy=True,
    )
    receiver = db.relationship(
        "User",
        primaryjoin="foreign(PurchaseReceipt.receiver_user_id) == User.id",
        lazy=True,
    )
    stock_ins = db.relationship(
        "PurchaseStockIn",
        primaryjoin="PurchaseReceipt.id == foreign(PurchaseStockIn.receipt_id)",
        back_populates="receipt",
        lazy="dynamic",
    )


class PurchaseStockIn(db.Model):
    __tablename__ = "purchase_stock_in"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    stock_in_no = db.Column(db.String(32), nullable=False, unique=True)
    receipt_id = db.Column(db.Integer, nullable=False, index=True)
    qty = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    storage_area = db.Column(db.String(64), nullable=True)
    stock_in_at = db.Column(db.DateTime, nullable=False)
    created_by = db.Column(db.Integer, nullable=False, index=True)
    remark = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    company = db.relationship(
        "Company",
        primaryjoin="foreign(PurchaseStockIn.company_id) == Company.id",
        lazy=True,
    )
    receipt = db.relationship(
        "PurchaseReceipt",
        primaryjoin="foreign(PurchaseStockIn.receipt_id) == PurchaseReceipt.id",
        back_populates="stock_ins",
        lazy=True,
    )
    creator = db.relationship(
        "User",
        primaryjoin="foreign(PurchaseStockIn.created_by) == User.id",
        lazy=True,
    )
