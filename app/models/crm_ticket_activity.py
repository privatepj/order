from app import db


class CrmTicketActivity(db.Model):
    __tablename__ = "crm_ticket_activity"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    ticket_id = db.Column(db.Integer, nullable=False)
    actor_user_id = db.Column(db.Integer, nullable=True)

    activity_type = db.Column(db.String(64), nullable=False, default="note")
    content = db.Column(db.Text)

    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

