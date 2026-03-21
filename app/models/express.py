from app import db


class ExpressCompany(db.Model):
    __tablename__ = "express_company"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False)
    code = db.Column(db.String(32), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())


class ExpressWaybill(db.Model):
    __tablename__ = "express_waybill"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    express_company_id = db.Column(db.Integer, nullable=False)  # 关联 express_company.id，不在库建外键
    waybill_no = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="available")
    delivery_id = db.Column(db.Integer, nullable=True)  # 关联 delivery.id，不在库建外键
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    __table_args__ = (
        db.UniqueConstraint("express_company_id", "waybill_no", name="uk_company_waybill"),
    )
