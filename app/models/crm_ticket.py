from app import db


class CrmTicket(db.Model):
    __tablename__ = "crm_ticket"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticket_code = db.Column(db.String(64), nullable=False, unique=True)

    # 逻辑外键：不建 FK 约束
    customer_id = db.Column(db.Integer, nullable=False)

    ticket_type = db.Column(db.String(64), nullable=False, default="support")
    priority = db.Column(db.String(32), nullable=False, default="normal")
    status = db.Column(db.String(32), nullable=False, default="open")

    subject = db.Column(db.String(128))
    description = db.Column(db.Text)

    assignee_user_id = db.Column(db.Integer, nullable=True)
    due_date = db.Column(db.Date)

    tags = db.Column(db.String(255))
    remark = db.Column(db.String(255))

    won_order_id = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    activities = db.relationship(
        "CrmTicketActivity",
        primaryjoin="CrmTicket.id == foreign(CrmTicketActivity.ticket_id)",
        backref="ticket",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="CrmTicketActivity.id",
    )

    customer = db.relationship(
        "Customer",
        primaryjoin="foreign(CrmTicket.customer_id) == Customer.id",
        lazy="joined",
    )

