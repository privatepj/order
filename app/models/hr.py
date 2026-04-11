from __future__ import annotations

from app import db


class HrDepartment(db.Model):
    __tablename__ = "hr_department"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    company = db.relationship(
        "Company",
        primaryjoin="foreign(HrDepartment.company_id) == Company.id",
        backref=db.backref("hr_departments", lazy="dynamic"),
        lazy=True,
    )
    employees = db.relationship(
        "HrEmployee",
        primaryjoin="HrDepartment.id == foreign(HrEmployee.department_id)",
        back_populates="department",
        lazy="dynamic",
    )
    work_type_maps = db.relationship(
        "HrDepartmentWorkTypeMap",
        primaryjoin="HrDepartment.id == foreign(HrDepartmentWorkTypeMap.department_id)",
        back_populates="department",
        lazy="dynamic",
    )


class HrWorkType(db.Model):
    __tablename__ = "hr_work_type"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    remark = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    company = db.relationship(
        "Company",
        primaryjoin="foreign(HrWorkType.company_id) == Company.id",
        backref=db.backref("hr_work_types", lazy="dynamic"),
        lazy=True,
    )
    employee_links = db.relationship(
        "HrEmployeeWorkType",
        primaryjoin="HrWorkType.id == foreign(HrEmployeeWorkType.work_type_id)",
        back_populates="work_type",
        lazy="select",
    )
    department_maps = db.relationship(
        "HrDepartmentWorkTypeMap",
        primaryjoin="HrWorkType.id == foreign(HrDepartmentWorkTypeMap.work_type_id)",
        back_populates="work_type",
        lazy="dynamic",
    )


class HrDepartmentWorkTypeMap(db.Model):
    __tablename__ = "hr_department_work_type_map"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    department_id = db.Column(db.Integer, nullable=False, index=True)
    work_type_id = db.Column(db.Integer, nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    remark = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    company = db.relationship(
        "Company",
        primaryjoin="foreign(HrDepartmentWorkTypeMap.company_id) == Company.id",
        lazy=True,
    )
    department = db.relationship(
        "HrDepartment",
        primaryjoin="foreign(HrDepartmentWorkTypeMap.department_id) == HrDepartment.id",
        back_populates="work_type_maps",
        lazy=True,
    )
    work_type = db.relationship(
        "HrWorkType",
        primaryjoin="foreign(HrDepartmentWorkTypeMap.work_type_id) == HrWorkType.id",
        back_populates="department_maps",
        lazy=True,
    )


class HrEmployee(db.Model):
    __tablename__ = "hr_employee"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    department_id = db.Column(db.Integer, nullable=True, index=True)
    user_id = db.Column(db.Integer, nullable=True, index=True)
    employee_no = db.Column(db.String(32), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    id_card = db.Column(db.String(32), nullable=True)
    phone = db.Column(db.String(32), nullable=True)
    job_title = db.Column(db.String(64), nullable=True)
    main_work_type_id = db.Column(db.Integer, nullable=True, index=True)
    status = db.Column(db.String(16), nullable=False, default="active")
    hire_date = db.Column(db.Date, nullable=True)
    leave_date = db.Column(db.Date, nullable=True)
    remark = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    company = db.relationship(
        "Company",
        primaryjoin="foreign(HrEmployee.company_id) == Company.id",
        backref=db.backref("hr_employees", lazy="dynamic"),
        lazy=True,
    )
    department = db.relationship(
        "HrDepartment",
        primaryjoin="foreign(HrEmployee.department_id) == HrDepartment.id",
        back_populates="employees",
        lazy=True,
    )
    linked_user = db.relationship(
        "User",
        primaryjoin="foreign(HrEmployee.user_id) == User.id",
        lazy=True,
    )
    main_work_type = db.relationship(
        "HrWorkType",
        primaryjoin="foreign(HrEmployee.main_work_type_id) == HrWorkType.id",
        lazy=True,
    )
    work_type_links = db.relationship(
        "HrEmployeeWorkType",
        primaryjoin="HrEmployee.id == foreign(HrEmployeeWorkType.employee_id)",
        back_populates="employee",
        lazy="select",
    )

    @property
    def primary_work_type_name(self) -> str | None:
        if self.main_work_type and self.main_work_type.name:
            return self.main_work_type.name
        for link in self.work_type_links or []:
            if link.is_primary and link.work_type and link.work_type.name:
                return link.work_type.name
        return (self.job_title or "").strip() or None

    @property
    def secondary_work_type_names(self) -> list[str]:
        out: list[str] = []
        main_id = int(self.main_work_type_id or 0)
        for link in self.work_type_links or []:
            work_type = link.work_type
            if not work_type or not work_type.name:
                continue
            if int(link.work_type_id or 0) == main_id:
                continue
            out.append(work_type.name)
        return out

    @property
    def all_work_type_names(self) -> list[str]:
        names: list[str] = []
        primary = self.primary_work_type_name
        if primary:
            names.append(primary)
        for name in self.secondary_work_type_names:
            if name not in names:
                names.append(name)
        return names


class HrEmployeeWorkType(db.Model):
    __tablename__ = "hr_employee_work_type"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(db.Integer, nullable=False, index=True)
    work_type_id = db.Column(db.Integer, nullable=False, index=True)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    employee = db.relationship(
        "HrEmployee",
        primaryjoin="foreign(HrEmployeeWorkType.employee_id) == HrEmployee.id",
        back_populates="work_type_links",
        lazy=True,
    )
    work_type = db.relationship(
        "HrWorkType",
        primaryjoin="foreign(HrEmployeeWorkType.work_type_id) == HrWorkType.id",
        back_populates="employee_links",
        lazy=True,
    )


class HrPayrollLine(db.Model):
    __tablename__ = "hr_payroll_line"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    employee_id = db.Column(db.Integer, nullable=False, index=True)
    period = db.Column(db.String(7), nullable=False)
    wage_kind = db.Column(db.String(16), nullable=False, default="monthly")
    work_hours = db.Column(db.Numeric(26, 8), nullable=True, default=None)
    hourly_rate = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    base_salary = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    allowance = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    deduction = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    net_pay = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    remark = db.Column(db.String(500), nullable=True)
    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    company = db.relationship(
        "Company",
        primaryjoin="foreign(HrPayrollLine.company_id) == Company.id",
        lazy=True,
    )
    employee = db.relationship(
        "HrEmployee",
        primaryjoin="foreign(HrPayrollLine.employee_id) == HrEmployee.id",
        lazy=True,
    )


class HrPerformanceReview(db.Model):
    __tablename__ = "hr_performance_review"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    employee_id = db.Column(db.Integer, nullable=False, index=True)
    cycle = db.Column(db.String(32), nullable=False)
    score = db.Column(db.Numeric(26, 8), nullable=True)
    comment = db.Column(db.Text, nullable=True)
    reviewer_user_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="draft")
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    company = db.relationship(
        "Company",
        primaryjoin="foreign(HrPerformanceReview.company_id) == Company.id",
        lazy=True,
    )
    employee = db.relationship(
        "HrEmployee",
        primaryjoin="foreign(HrPerformanceReview.employee_id) == HrEmployee.id",
        lazy=True,
    )


class HrEmployeeCapability(db.Model):
    __tablename__ = "hr_employee_capability"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    employee_id = db.Column(db.Integer, nullable=False, index=True)
    hr_department_id = db.Column(db.Integer, nullable=False, index=True)
    work_type_id = db.Column(db.Integer, nullable=True, index=True)

    good_qty_total = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    bad_qty_total = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    produced_qty_total = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    work_order_cnt_total = db.Column(db.Integer, nullable=False, default=0)
    worked_minutes_total = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    labor_cost_total = db.Column(db.Numeric(26, 8), nullable=False, default=0)

    processed_to = db.Column(db.DateTime, nullable=True, index=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    employee = db.relationship(
        "HrEmployee",
        primaryjoin="foreign(HrEmployeeCapability.employee_id) == HrEmployee.id",
        lazy=True,
    )
    department = db.relationship(
        "HrDepartment",
        primaryjoin="foreign(HrEmployeeCapability.hr_department_id) == HrDepartment.id",
        lazy=True,
    )
    work_type = db.relationship(
        "HrWorkType",
        primaryjoin="foreign(HrEmployeeCapability.work_type_id) == HrWorkType.id",
        lazy=True,
    )

    @property
    def effective_work_type_id(self) -> int:
        return int(self.work_type_id or self.hr_department_id or 0)


class HrEmployeeScheduleTemplate(db.Model):
    __tablename__ = "hr_employee_schedule_template"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(db.Integer, nullable=False, index=True)

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
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    employee = db.relationship(
        "HrEmployee",
        primaryjoin="foreign(HrEmployeeScheduleTemplate.employee_id) == HrEmployee.id",
        lazy=True,
    )
    creator = db.relationship(
        "User",
        primaryjoin="foreign(HrEmployeeScheduleTemplate.created_by) == User.id",
        lazy=True,
    )

    bookings = db.relationship(
        "HrEmployeeScheduleBooking",
        primaryjoin="HrEmployeeScheduleTemplate.id == foreign(HrEmployeeScheduleBooking.template_id)",
        back_populates="template",
        lazy="dynamic",
    )


class HrEmployeeScheduleBooking(db.Model):
    __tablename__ = "hr_employee_schedule_booking"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(db.Integer, nullable=False, index=True)
    template_id = db.Column(db.Integer, nullable=False, index=True)

    state = db.Column(db.String(16), nullable=False, default="available")
    start_at = db.Column(db.DateTime, nullable=False, index=True)
    end_at = db.Column(db.DateTime, nullable=False, index=True)
    remark = db.Column(db.String(255), nullable=True)

    created_by = db.Column(db.Integer, nullable=False, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    hr_department_id = db.Column(db.Integer, nullable=True, index=True)
    work_type_id = db.Column(db.Integer, nullable=True, index=True)
    work_order_id = db.Column(db.Integer, nullable=True, index=True)
    product_id = db.Column(db.Integer, nullable=True, index=True)
    unit = db.Column(db.String(16), nullable=True)
    good_qty = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    bad_qty = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    produced_qty = db.Column(db.Numeric(26, 8), nullable=False, default=0)

    employee = db.relationship(
        "HrEmployee",
        primaryjoin="foreign(HrEmployeeScheduleBooking.employee_id) == HrEmployee.id",
        lazy=True,
    )
    template = db.relationship(
        "HrEmployeeScheduleTemplate",
        primaryjoin="foreign(HrEmployeeScheduleBooking.template_id) == HrEmployeeScheduleTemplate.id",
        back_populates="bookings",
        lazy=True,
    )
    creator = db.relationship(
        "User",
        primaryjoin="foreign(HrEmployeeScheduleBooking.created_by) == User.id",
        lazy=True,
    )
    department = db.relationship(
        "HrDepartment",
        primaryjoin="foreign(HrEmployeeScheduleBooking.hr_department_id) == HrDepartment.id",
        lazy=True,
    )
    work_type = db.relationship(
        "HrWorkType",
        primaryjoin="foreign(HrEmployeeScheduleBooking.work_type_id) == HrWorkType.id",
        lazy=True,
    )
    work_order = db.relationship(
        "ProductionWorkOrder",
        primaryjoin="foreign(HrEmployeeScheduleBooking.work_order_id) == ProductionWorkOrder.id",
        lazy=True,
        viewonly=True,
    )
    product = db.relationship(
        "Product",
        primaryjoin="foreign(HrEmployeeScheduleBooking.product_id) == Product.id",
        lazy=True,
        viewonly=True,
    )

    @property
    def effective_work_type_id(self) -> int:
        return int(self.work_type_id or self.hr_department_id or 0)


class HrDepartmentPieceRate(db.Model):
    __tablename__ = "hr_department_piece_rate"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    hr_department_id = db.Column(db.Integer, nullable=False, index=True)
    period = db.Column(db.String(7), nullable=False)
    rate_per_unit = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    remark = db.Column(db.String(500), nullable=True)
    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    company = db.relationship(
        "Company",
        primaryjoin="foreign(HrDepartmentPieceRate.company_id) == Company.id",
        lazy=True,
    )
    department = db.relationship(
        "HrDepartment",
        primaryjoin="foreign(HrDepartmentPieceRate.hr_department_id) == HrDepartment.id",
        lazy=True,
    )
    creator = db.relationship(
        "User",
        primaryjoin="foreign(HrDepartmentPieceRate.created_by) == User.id",
        lazy=True,
    )


class HrWorkTypePieceRate(db.Model):
    __tablename__ = "hr_work_type_piece_rate"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    work_type_id = db.Column(db.Integer, nullable=False, index=True)
    period = db.Column(db.String(7), nullable=False)
    rate_per_unit = db.Column(db.Numeric(26, 8), nullable=False, default=0)
    remark = db.Column(db.String(500), nullable=True)
    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    company = db.relationship(
        "Company",
        primaryjoin="foreign(HrWorkTypePieceRate.company_id) == Company.id",
        lazy=True,
    )
    work_type = db.relationship(
        "HrWorkType",
        primaryjoin="foreign(HrWorkTypePieceRate.work_type_id) == HrWorkType.id",
        lazy=True,
    )
    creator = db.relationship(
        "User",
        primaryjoin="foreign(HrWorkTypePieceRate.created_by) == User.id",
        lazy=True,
    )
