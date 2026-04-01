from __future__ import annotations

from app import db


class ProductionProcessEdge(db.Model):
    __tablename__ = "production_process_edge"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    template_id = db.Column(db.Integer, nullable=False, index=True)
    from_node_id = db.Column(db.Integer, nullable=False, index=True)
    to_node_id = db.Column(db.Integer, nullable=False, index=True)

    edge_type = db.Column(db.String(16), nullable=False, default="fs")
    lag_minutes = db.Column(db.Integer, nullable=False, default=0)

    remark = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

