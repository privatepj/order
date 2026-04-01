from __future__ import annotations

from app import db


class ProductionRoutingNodeOverride(db.Model):
    __tablename__ = "production_routing_node_override"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    routing_id = db.Column(db.Integer, nullable=False, index=True)
    process_node_id = db.Column(db.Integer, nullable=False, index=True)

    resource_kind_override = db.Column(db.String(16))
    machine_type_id_override = db.Column(db.Integer, nullable=False, default=0)
    hr_department_id_override = db.Column(db.Integer, nullable=False, default=0)

    setup_minutes_override = db.Column(db.Numeric(12, 2))
    run_minutes_per_unit_override = db.Column(db.Numeric(12, 4))
    scrap_rate_override = db.Column(db.Numeric(8, 4))

    remark = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

