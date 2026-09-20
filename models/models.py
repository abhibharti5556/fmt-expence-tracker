from datetime import datetime, date

from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db

STATUS_ACTIVE = "Active"
STATUS_INACTIVE = "Inactive"

TRANSACTION_TYPE_CREDIT = "CREDIT"

EXPENSE_TYPE_LOGISTICS = "LOGISTICS"
EXPENSE_TYPE_WAREHOUSING = "WAREHOUSING"

# The only payment_status value the app ever writes today. Kept as a plain
# string column (not a DB enum) so future statuses (e.g. VERIFIED/REJECTED)
# can be introduced without a migration. This is the single status that
# counts toward balance, KPIs, and reports everywhere in the app.
PAYMENT_STATUS_SUBMITTED = "SUBMITTED"
BALANCE_COUNTING_STATUSES = (PAYMENT_STATUS_SUBMITTED,)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    profile_image = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="EMPLOYEE")
    status = db.Column(db.String(20), nullable=False, default=STATUS_ACTIVE)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    money_transactions = db.relationship(
        "MoneyTransaction", backref="user", lazy="dynamic",
        foreign_keys="MoneyTransaction.user_id",
    )
    expenses = db.relationship(
        "Expense", backref="user", lazy="dynamic", foreign_keys="Expense.user_id"
    )

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def is_active(self):
        return self.status == STATUS_ACTIVE

    def __repr__(self):
        return f"<User {self.employee_id} {self.name}>"


class MoneyTransaction(db.Model):
    __tablename__ = "money_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False, default=TRANSACTION_TYPE_CREDIT)
    purpose = db.Column(db.String(255), nullable=False)
    remarks = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_by = db.Column(db.String(120), nullable=False)

    @property
    def display_id(self):
        return f"TXN-{self.id:06d}"


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(30), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    expense_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)

    docket_no = db.Column(db.String(60), nullable=True)
    purpose = db.Column(db.String(255), nullable=False)
    reason = db.Column(db.String(500), nullable=True)
    approved_by = db.Column(db.String(120), nullable=False)
    remarks = db.Column(db.String(500), nullable=True)

    upi_reference_no = db.Column(db.String(60), nullable=False)
    payment_status = db.Column(db.String(20), nullable=False, default=PAYMENT_STATUS_SUBMITTED)

    invoice_file = db.Column(db.String(255), nullable=False)
    payment_screenshot = db.Column(db.String(255), nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<Expense {self.transaction_id} {self.expense_type} {self.amount}>"
