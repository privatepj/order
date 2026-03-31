from __future__ import annotations

from app import db


class ProductionIncident(db.Model):
    __tablename__ = "production_incident"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    incident_no = db.Column(db.String(32), unique=True, nullable=True)
    title = db.Column(db.String(255), nullable=False)
    occurred_at = db.Column(db.DateTime, nullable=False)
    workshop = db.Column(db.String(128), nullable=True)
    severity = db.Column(db.String(32), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="open")
    remark = db.Column(db.String(500), nullable=True)

    d1_team = db.Column(db.Text, nullable=True)
    d2_problem = db.Column(db.Text, nullable=True)
    d3_containment = db.Column(db.Text, nullable=True)
    d4_root_cause = db.Column(db.Text, nullable=True)
    d5_corrective = db.Column(db.Text, nullable=True)
    d6_implementation = db.Column(db.Text, nullable=True)
    d7_prevention = db.Column(db.Text, nullable=True)
    d8_recognition = db.Column(db.Text, nullable=True)

    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )
