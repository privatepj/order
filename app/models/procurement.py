from app import db


class Supplier(db.Model):
    __tablename__ = "supplier"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    contact_name = db.Column(db.String(64), nullable=True)
    phone = db.Column(db.String(32), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    remark = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    company = db.relationship(
        "Company",
        primaryjoin="foreign(Supplier.company_id) == Company.id",
        lazy=True,
    )


class SupplierMaterialMap(db.Model):
    __tablename__ = "supplier_material_map"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    supplier_id = db.Column(db.Integer, nullable=False, index=True)
    material_id = db.Column(db.Integer, nullable=False, index=True)
    is_preferred = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_unit_price = db.Column(db.Numeric(26, 8), nullable=True)
    remark = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    company = db.relationship(
        "Company",
        primaryjoin="foreign(SupplierMaterialMap.company_id) == Company.id",
        lazy=True,
    )
    supplier = db.relationship(
        "Supplier",
        primaryjoin="foreign(SupplierMaterialMap.supplier_id) == Supplier.id",
        lazy=True,
    )
    material = db.relationship(
        "SemiMaterial",
        primaryjoin="foreign(SupplierMaterialMap.material_id) == SemiMaterial.id",
        lazy=True,
    )


class PurchaseRequisition(db.Model):
    __tablename__ = "purchase_requisition"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    req_no = db.Column(db.String(32), nullable=False, unique=True)
    requester_user_id = db.Column(db.Integer, nullable=False, index=True)
    supplier_name = db.Column(db.String(128), nullable=False)
    item_name = db.Column(db.String(128), nullable=False)
    item_spec = db.Column(db.String(128), nullable=True)
    qty = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    unit = db.Column(db.String(16), nullable=False, default="pcs")
    expected_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="draft")
    printed_at = db.Column(db.DateTime, nullable=True)
    signed_at = db.Column(db.DateTime, nullable=True)
    signed_by = db.Column(db.Integer, nullable=True, index=True)
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
    signer = db.relationship(
        "User",
        primaryjoin="foreign(PurchaseRequisition.signed_by) == User.id",
        lazy=True,
    )
    lines = db.relationship(
        "PurchaseRequisitionLine",
        primaryjoin="PurchaseRequisition.id == foreign(PurchaseRequisitionLine.requisition_id)",
        back_populates="requisition",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="PurchaseRequisitionLine.line_no.asc(), PurchaseRequisitionLine.id.asc()",
    )
    purchase_orders = db.relationship(
        "PurchaseOrder",
        primaryjoin="PurchaseRequisition.id == foreign(PurchaseOrder.requisition_id)",
        back_populates="requisition",
        lazy="dynamic",
    )


class PurchaseRequisitionLine(db.Model):
    __tablename__ = "purchase_requisition_line"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    requisition_id = db.Column(db.Integer, nullable=False, index=True)
    line_no = db.Column(db.Integer, nullable=False, default=1)
    supplier_id = db.Column(db.Integer, nullable=True, index=True)
    material_id = db.Column(db.Integer, nullable=True, index=True)
    supplier_name = db.Column(db.String(128), nullable=False)
    item_name = db.Column(db.String(128), nullable=False)
    item_spec = db.Column(db.String(128), nullable=True)
    qty = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    unit = db.Column(db.String(16), nullable=False, default="pcs")
    expected_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(24), nullable=False, default="pending_order")
    remark = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    company = db.relationship(
        "Company",
        primaryjoin="foreign(PurchaseRequisitionLine.company_id) == Company.id",
        lazy=True,
    )
    requisition = db.relationship(
        "PurchaseRequisition",
        primaryjoin="foreign(PurchaseRequisitionLine.requisition_id) == PurchaseRequisition.id",
        back_populates="lines",
        lazy=True,
    )
    supplier = db.relationship(
        "Supplier",
        primaryjoin="foreign(PurchaseRequisitionLine.supplier_id) == Supplier.id",
        lazy=True,
    )
    material = db.relationship(
        "SemiMaterial",
        primaryjoin="foreign(PurchaseRequisitionLine.material_id) == SemiMaterial.id",
        lazy=True,
    )
    purchase_orders = db.relationship(
        "PurchaseOrder",
        primaryjoin="PurchaseRequisitionLine.id == foreign(PurchaseOrder.requisition_line_id)",
        back_populates="requisition_line",
        lazy="dynamic",
    )


class PurchaseOrder(db.Model):
    __tablename__ = "purchase_order"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    po_no = db.Column(db.String(32), nullable=False, unique=True)
    requisition_id = db.Column(db.Integer, nullable=True, index=True)
    requisition_line_id = db.Column(db.Integer, nullable=True, index=True)
    buyer_user_id = db.Column(db.Integer, nullable=False, index=True)
    supplier_id = db.Column(db.Integer, nullable=True, index=True)
    material_id = db.Column(db.Integer, nullable=True, index=True)
    supplier_name = db.Column(db.String(128), nullable=False)
    supplier_contact_name = db.Column(db.String(64), nullable=True)
    supplier_phone = db.Column(db.String(32), nullable=True)
    supplier_address = db.Column(db.String(255), nullable=True)
    item_name = db.Column(db.String(128), nullable=False)
    item_spec = db.Column(db.String(128), nullable=True)
    qty = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    unit = db.Column(db.String(16), nullable=False, default="pcs")
    unit_price = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    amount = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    expected_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="draft")
    ordered_at = db.Column(db.DateTime, nullable=True)
    ordered_by = db.Column(db.Integer, nullable=True, index=True)
    printed_at = db.Column(db.DateTime, nullable=True)
    reconcile_status = db.Column(db.String(24), nullable=False, default="pending")
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
    requisition_line = db.relationship(
        "PurchaseRequisitionLine",
        primaryjoin="foreign(PurchaseOrder.requisition_line_id) == PurchaseRequisitionLine.id",
        back_populates="purchase_orders",
        lazy=True,
    )
    buyer = db.relationship(
        "User",
        primaryjoin="foreign(PurchaseOrder.buyer_user_id) == User.id",
        lazy=True,
    )
    supplier = db.relationship(
        "Supplier",
        primaryjoin="foreign(PurchaseOrder.supplier_id) == Supplier.id",
        lazy=True,
    )
    material = db.relationship(
        "SemiMaterial",
        primaryjoin="foreign(PurchaseOrder.material_id) == SemiMaterial.id",
        lazy=True,
    )
    order_marker = db.relationship(
        "User",
        primaryjoin="foreign(PurchaseOrder.ordered_by) == User.id",
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
    received_qty = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    received_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="draft")
    reconcile_status = db.Column(db.String(24), nullable=False, default="pending")
    reconcile_note = db.Column(db.String(500), nullable=True)
    reconciled_at = db.Column(db.DateTime, nullable=True)
    reconciled_by = db.Column(db.Integer, nullable=True, index=True)
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
    reconciler = db.relationship(
        "User",
        primaryjoin="foreign(PurchaseReceipt.reconciled_by) == User.id",
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
    purchase_order_id = db.Column(db.Integer, nullable=True, index=True)
    qty = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    received_qty = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    warehouse_qty = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    variance_qty = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    approval_status = db.Column(db.String(24), nullable=False, default="matched")
    storage_area = db.Column(db.String(64), nullable=True)
    stock_in_at = db.Column(db.DateTime, nullable=False)
    created_by = db.Column(db.Integer, nullable=False, index=True)
    approved_by = db.Column(db.Integer, nullable=True, index=True)
    approved_at = db.Column(db.DateTime, nullable=True)
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
    purchase_order = db.relationship(
        "PurchaseOrder",
        primaryjoin="foreign(PurchaseStockIn.purchase_order_id) == PurchaseOrder.id",
        lazy=True,
    )
    creator = db.relationship(
        "User",
        primaryjoin="foreign(PurchaseStockIn.created_by) == User.id",
        lazy=True,
    )
    approver = db.relationship(
        "User",
        primaryjoin="foreign(PurchaseStockIn.approved_by) == User.id",
        lazy=True,
    )
