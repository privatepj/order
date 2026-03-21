from app import db


class Company(db.Model):
    __tablename__ = "company"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False)
    code = db.Column(db.String(32), nullable=False, unique=True)
    # 我方订单号前缀；空则建单时用 code
    order_no_prefix = db.Column(db.String(32), nullable=True)
    # 送货单号前缀；空则用 code
    delivery_no_prefix = db.Column(db.String(32), nullable=True)
    # 转月日/月结日：每月该日起为新业务月（1=自然月）
    billing_cycle_day = db.Column(db.SmallInteger, nullable=False, default=1)
    phone = db.Column(db.String(32))
    fax = db.Column(db.String(32))
    address = db.Column(db.String(255))
    contact_person = db.Column(db.String(64))
    private_account = db.Column(db.String(64))
    public_account = db.Column(db.String(64))
    account_name = db.Column(db.String(64))
    bank_name = db.Column(db.String(128))
    preparer_name = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    customers = db.relationship(
        "Customer", primaryjoin="Company.id == foreign(Customer.company_id)", backref="company", lazy="dynamic"
    )
