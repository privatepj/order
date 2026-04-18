from decimal import Decimal

from app import db


class MachineType(db.Model):
    __tablename__ = "machine_type"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(32), nullable=False, unique=True)
    name = db.Column(db.String(64), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    remark = db.Column(db.String(255), nullable=True)
    default_capability_hr_department_id = db.Column(db.Integer, nullable=False, default=0)
    default_capability_work_type_id = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    machines = db.relationship(
        "Machine",
        primaryjoin="MachineType.id == foreign(Machine.machine_type_id)",
        back_populates="machine_type",
        lazy="dynamic",
    )

    @property
    def effective_default_capability_work_type_id(self) -> int:
        return int(
            self.default_capability_work_type_id
            or self.default_capability_hr_department_id
            or 0
        )


class Machine(db.Model):
    __tablename__ = "machine"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    machine_no = db.Column(db.String(32), nullable=False, unique=True)
    name = db.Column(db.String(64), nullable=False)
    machine_type_id = db.Column(db.Integer, nullable=False, index=True)
    capacity_per_hour = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    machine_cost_purchase_price = db.Column(
        db.Numeric(26, 8), nullable=False, default=Decimal("0.00")
    )
    machine_accum_produced_qty = db.Column(
        db.Numeric(26, 8), nullable=False, default=Decimal("0.0000")
    )
    machine_accum_runtime_hours = db.Column(
        db.Numeric(26, 8), nullable=False, default=Decimal("0.0000")
    )
    machine_single_run_cost = db.Column(db.Numeric(26, 8), nullable=True, default=None)
    status = db.Column(db.String(16), nullable=False, default="enabled")
    location = db.Column(db.String(128), nullable=True)
    owner_user_id = db.Column(db.Integer, nullable=True, index=True)
    remark = db.Column(db.String(255), nullable=True)
    default_capability_hr_department_id = db.Column(db.Integer, nullable=False, default=0)
    default_capability_work_type_id = db.Column(db.Integer, nullable=False, default=0)
    owning_hr_department_id = db.Column(db.Integer, nullable=False, default=0, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    machine_type = db.relationship(
        "MachineType",
        primaryjoin="foreign(Machine.machine_type_id) == MachineType.id",
        back_populates="machines",
        lazy=True,
    )
    owner = db.relationship(
        "User",
        primaryjoin="foreign(Machine.owner_user_id) == User.id",
        lazy=True,
    )
    owning_hr_department = db.relationship(
        "HrDepartment",
        primaryjoin="foreign(Machine.owning_hr_department_id) == HrDepartment.id",
        lazy=True,
        viewonly=True,
    )
    runtime_logs = db.relationship(
        "MachineRuntimeLog",
        primaryjoin="Machine.id == foreign(MachineRuntimeLog.machine_id)",
        back_populates="machine",
        lazy="dynamic",
    )

    schedule_templates = db.relationship(
        "MachineScheduleTemplate",
        primaryjoin="Machine.id == foreign(MachineScheduleTemplate.machine_id)",
        back_populates="machine",
        lazy="dynamic",
    )

    schedule_bookings = db.relationship(
        "MachineScheduleBooking",
        primaryjoin="Machine.id == foreign(MachineScheduleBooking.machine_id)",
        back_populates="machine",
        lazy="dynamic",
    )

    @property
    def effective_default_capability_work_type_id(self) -> int:
        return int(
            self.default_capability_work_type_id
            or self.default_capability_hr_department_id
            or 0
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
        back_populates="runtime_logs",
        lazy=True,
    )
    creator = db.relationship(
        "User",
        primaryjoin="foreign(MachineRuntimeLog.created_by) == User.id",
        lazy=True,
    )


class MachineScheduleTemplate(db.Model):
    __tablename__ = "machine_schedule_template"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    machine_id = db.Column(db.Integer, nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)
    repeat_kind = db.Column(db.String(16), nullable=False, default="weekly")
    days_of_week = db.Column(db.String(32), nullable=False, default="0,1,2,3,4,5,6")
    valid_from = db.Column(db.Date, nullable=False, index=True)
    valid_to = db.Column(db.Date, nullable=True, index=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    state = db.Column(db.String(16), nullable=False, default="available")
    remark = db.Column(db.String(255), nullable=True)
    created_by = db.Column(db.Integer, nullable=False, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    machine = db.relationship(
        "Machine",
        primaryjoin="foreign(MachineScheduleTemplate.machine_id) == Machine.id",
        back_populates="schedule_templates",
        lazy=True,
    )
    creator = db.relationship(
        "User",
        primaryjoin="foreign(MachineScheduleTemplate.created_by) == User.id",
        lazy=True,
    )

    bookings = db.relationship(
        "MachineScheduleBooking",
        primaryjoin="MachineScheduleTemplate.id == foreign(MachineScheduleBooking.template_id)",
        back_populates="template",
        lazy="dynamic",
    )


class MachineScheduleBooking(db.Model):
    __tablename__ = "machine_schedule_booking"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    machine_id = db.Column(db.Integer, nullable=False, index=True)
    template_id = db.Column(db.Integer, nullable=False, index=True)
    state = db.Column(db.String(16), nullable=False, default="available")
    start_at = db.Column(db.DateTime, nullable=False, index=True)
    end_at = db.Column(db.DateTime, nullable=False, index=True)
    remark = db.Column(db.String(255), nullable=True)
    created_by = db.Column(db.Integer, nullable=False, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    machine = db.relationship(
        "Machine",
        primaryjoin="foreign(MachineScheduleBooking.machine_id) == Machine.id",
        back_populates="schedule_bookings",
        lazy=True,
    )
    template = db.relationship(
        "MachineScheduleTemplate",
        primaryjoin="foreign(MachineScheduleBooking.template_id) == MachineScheduleTemplate.id",
        back_populates="bookings",
        lazy=True,
    )
    creator = db.relationship(
        "User",
        primaryjoin="foreign(MachineScheduleBooking.created_by) == User.id",
        lazy=True,
    )


class MachineScheduleDispatchLog(db.Model):
    __tablename__ = "machine_schedule_dispatch_log"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    machine_id = db.Column(db.Integer, nullable=False, index=True)
    booking_id = db.Column(db.Integer, nullable=False, unique=True, index=True)

    dispatch_start_at = db.Column(db.DateTime, nullable=True)
    dispatch_end_at = db.Column(db.DateTime, nullable=True)
    planned_runtime_hours = db.Column(db.Numeric(26, 8), nullable=False, default=Decimal("0.0000"))

    state = db.Column(db.String(16), nullable=False, default="scheduled")

    actual_produced_qty = db.Column(db.Numeric(26, 8), nullable=True)
    actual_runtime_hours = db.Column(db.Numeric(26, 8), nullable=True)

    work_order_id = db.Column(db.Integer, nullable=True, index=True)
    reported_by = db.Column(db.Integer, nullable=True, index=True)
    reported_at = db.Column(db.DateTime, nullable=True)

    remark = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    machine = db.relationship(
        "Machine",
        primaryjoin="foreign(MachineScheduleDispatchLog.machine_id) == Machine.id",
        lazy=True,
    )
    booking = db.relationship(
        "MachineScheduleBooking",
        primaryjoin="foreign(MachineScheduleDispatchLog.booking_id) == MachineScheduleBooking.id",
        lazy=True,
    )
    reporter = db.relationship(
        "User",
        primaryjoin="foreign(MachineScheduleDispatchLog.reported_by) == User.id",
        lazy=True,
    )
