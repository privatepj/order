from app import db


class MachineType(db.Model):
    __tablename__ = "machine_type"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(32), nullable=False, unique=True)
    name = db.Column(db.String(64), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    remark = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    machines = db.relationship(
        "Machine",
        primaryjoin="MachineType.id == foreign(Machine.machine_type_id)",
        lazy="dynamic",
    )


class Machine(db.Model):
    __tablename__ = "machine"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    machine_no = db.Column(db.String(32), nullable=False, unique=True)
    name = db.Column(db.String(64), nullable=False)
    machine_type_id = db.Column(db.Integer, nullable=False, index=True)
    capacity_per_hour = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    status = db.Column(db.String(16), nullable=False, default="enabled")
    location = db.Column(db.String(128), nullable=True)
    owner_user_id = db.Column(db.Integer, nullable=True, index=True)
    remark = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    machine_type = db.relationship(
        "MachineType",
        primaryjoin="foreign(Machine.machine_type_id) == MachineType.id",
        lazy=True,
    )
    owner = db.relationship(
        "User",
        primaryjoin="foreign(Machine.owner_user_id) == User.id",
        lazy=True,
    )
    runtime_logs = db.relationship(
        "MachineRuntimeLog",
        primaryjoin="Machine.id == foreign(MachineRuntimeLog.machine_id)",
        lazy="dynamic",
    )


class MachineRuntimeLog(db.Model):
    __tablename__ = "machine_runtime_log"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    machine_id = db.Column(db.Integer, nullable=False, index=True)
    runtime_status = db.Column(db.String(16), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)
    remark = db.Column(db.String(255), nullable=True)
    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    machine = db.relationship(
        "Machine",
        primaryjoin="foreign(MachineRuntimeLog.machine_id) == Machine.id",
        lazy=True,
    )
    creator = db.relationship(
        "User",
        primaryjoin="foreign(MachineRuntimeLog.created_by) == User.id",
        lazy=True,
    )
