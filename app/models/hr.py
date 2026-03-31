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
