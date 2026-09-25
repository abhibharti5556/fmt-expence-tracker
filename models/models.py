from datetime import datetime, date

from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db

STATUS_ACTIVE = "Active"
STATUS_INACTIVE = "Inactive"

TRANSACTION_TYPE_CREDIT = "CREDIT"

EXPENSE_TYPE_LOGISTICS = "LOGISTICS"
EXPENSE_TYPE_WAREHOUSING = "WAREHOUSING"

# Fixed category list shown on the Logistics expense form. Kept as a plain
# list (not a DB enum) so adding/renaming a category is a code change, not
# a migration; the `category` column just stores whichever string was
# selected at submission time.
LOGISTICS_CATEGORIES = [
    "Pickup",
    "Re-packing",
    "Manpower",
    "Halting",
    "Adhoc Vehicle Charges",
    "Parking",
    "Mathadi",
    "Loading",
    "Unloading",
    "Others",
]

# Icon shown on the category picker card. Falls back to a generic tag icon
# in the template if a category is missing here.
LOGISTICS_CATEGORY_ICONS = {
    "Pickup": "ph-truck",
    "Re-packing": "ph-package",
    "Manpower": "ph-users-three",
    "Halting": "ph-hourglass-medium",
    "Adhoc Vehicle Charges": "ph-car",
    "Parking": "ph-map-pin",
    "Mathadi": "ph-hand-fist",
    "Loading": "ph-tray-arrow-down",
    "Unloading": "ph-tray-arrow-up",
    "Others": "ph-dots-three-circle",
}

# Fixed category list shown on the Warehousing expense form. Same reasoning
# as LOGISTICS_CATEGORIES above.
WAREHOUSING_CATEGORIES = [
    "Rent",
    "Property Tax",
    "Facility Insurance",
    "Maintenance",
    "Utilities",
    "Janitorial",
    "Housekeeping",
    "Pantry",
    "Security",
    "Direct Labor",
    "Equipment Repair",
    "Equipment Fuel",
    "Labels",
    "Safety Gear",
    "IT Hardware",
    "Internet & Wi-Fi",
    "Others",
]

WAREHOUSING_CATEGORY_ICONS = {
    "Rent": "ph-key",
    "Property Tax": "ph-bank",
    "Facility Insurance": "ph-shield-check",
    "Maintenance": "ph-wrench",
    "Utilities": "ph-lightning",
    "Janitorial": "ph-broom",
    "Housekeeping": "ph-house-line",
    "Pantry": "ph-coffee",
    "Security": "ph-shield",
    "Direct Labor": "ph-users-three",
    "Equipment Repair": "ph-wrench",
    "Equipment Fuel": "ph-gas-pump",
    "Labels": "ph-tag",
    "Safety Gear": "ph-hard-hat",
    "IT Hardware": "ph-desktop-tower",
    "Internet & Wi-Fi": "ph-wifi-high",
    "Others": "ph-dots-three-circle",
}

# Kept as plain string columns (not a DB enum) so new statuses can be
# introduced without a migration.
#
# Logistics expenses go SUBMITTED-equivalent (PENDING_APPROVAL) at
# creation, then an admin moves them to APPROVED or REJECTED. Warehousing
# expenses still go straight to SUBMITTED (no approval step).
#
# Balance/KPI/report totals reserve the amount as soon as it's submitted,
# not just once approved -- an employee's balance drops immediately and
# only comes back if the entry is REJECTED. That's why PENDING_APPROVAL
# and APPROVED both count here, alongside the original SUBMITTED.
PAYMENT_STATUS_SUBMITTED = "SUBMITTED"
PAYMENT_STATUS_PENDING_APPROVAL = "PENDING_APPROVAL"
PAYMENT_STATUS_APPROVED = "APPROVED"
PAYMENT_STATUS_REJECTED = "REJECTED"
BALANCE_COUNTING_STATUSES = (
    PAYMENT_STATUS_SUBMITTED,
    PAYMENT_STATUS_PENDING_APPROVAL,
    PAYMENT_STATUS_APPROVED,
)

PAYMENT_STATUS_LABELS = {
    PAYMENT_STATUS_SUBMITTED: "Submitted",
    PAYMENT_STATUS_PENDING_APPROVAL: "Pending Approval",
    PAYMENT_STATUS_APPROVED: "Approved",
    PAYMENT_STATUS_REJECTED: "Rejected",
}


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
    category = db.Column(db.String(50), nullable=True)
    purpose = db.Column(db.String(255), nullable=False)
    reason = db.Column(db.String(500), nullable=True)
    approved_by = db.Column(db.String(120), nullable=False)
    remarks = db.Column(db.String(500), nullable=True)

    upi_reference_no = db.Column(db.String(60), nullable=False)
    payment_status = db.Column(db.String(20), nullable=False, default=PAYMENT_STATUS_SUBMITTED)
    rejection_reason = db.Column(db.String(500), nullable=True)
    reviewed_by = db.Column(db.String(120), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    invoice_file = db.Column(db.String(255), nullable=False)
    payment_screenshot = db.Column(db.String(255), nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<Expense {self.transaction_id} {self.expense_type} {self.amount}>"
