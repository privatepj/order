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


class HrPayrollLine(db.Model):
    __tablename__ = "hr_payroll_line"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    employee_id = db.Column(db.Integer, nullable=False, index=True)
    period = db.Column(db.String(7), nullable=False)
    wage_kind = db.Column(db.String(16), nullable=False, default="monthly")
    # 用于将月薪/时薪统一到“小时工资”，从而参与人员能力表的单件成本计算
    work_hours = db.Column(db.Numeric(12, 2), nullable=True, default=None)
    hourly_rate = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    base_salary = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    allowance = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    deduction = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    net_pay = db.Column(db.Numeric(14, 2), nullable=False, default=0)
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
    score = db.Column(db.Numeric(6, 2), nullable=True)
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
    """
    人员能力表（按员工 + 工位/工种维度累计统计）。

    注意：无 DB 外键约束；引用由应用层保证一致性。
    """

    __tablename__ = "hr_employee_capability"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    company_id = db.Column(db.Integer, nullable=False, index=True)
    employee_id = db.Column(db.Integer, nullable=False, index=True)
    hr_department_id = db.Column(db.Integer, nullable=False, index=True)

    good_qty_total = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    bad_qty_total = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    produced_qty_total = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    work_order_cnt_total = db.Column(db.Integer, nullable=False, default=0)
    worked_minutes_total = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    labor_cost_total = db.Column(db.Numeric(18, 2), nullable=False, default=0)

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

    # 工作log（手工维护；应用层保证一致性）
    hr_department_id = db.Column(db.Integer, nullable=True, index=True)
    work_order_id = db.Column(db.Integer, nullable=True, index=True)
    product_id = db.Column(db.Integer, nullable=True, index=True)
    unit = db.Column(db.String(16), nullable=True)
    good_qty = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    bad_qty = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    produced_qty = db.Column(db.Numeric(18, 4), nullable=False, default=0)

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
