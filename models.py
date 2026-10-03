from datetime import datetime
from flask_login import UserMixin
from sqlalchemy import or_, and_
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

PENDING, APPROVED, COMPLETED, CANCELLED = "pending", "approved", "completed", "cancelled"
STATUSES = [PENDING, APPROVED, COMPLETED, CANCELLED]

ROLE_ADMIN, ROLE_EXPERT, ROLE_STUDENT = "super_admin", "medical_expert", "student"
ROLE_LABELS = {ROLE_ADMIN: "Super Admin", ROLE_EXPERT: "Medical Expert", ROLE_STUDENT: "Student"}


class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False)
    description = db.Column(db.String(200))
    users = db.relationship("User", back_populates="role")

    @property
    def label(self):
        return ROLE_LABELS.get(self.name, self.name)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    school_id = db.Column(db.String(40))        # students
    department = db.Column(db.String(100))      # students
    specialization = db.Column(db.String(100))  # medical experts
    phone = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    role = db.relationship("Role", back_populates="users")

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def is_active(self):  # Flask-Login hook: deactivated users cannot log in
        return self.active

    @property
    def is_admin(self):
        return self.role.name == ROLE_ADMIN

    @property
    def is_expert(self):
        return self.role.name == ROLE_EXPERT

    @property
    def is_student(self):
        return self.role.name == ROLE_STUDENT


class Availability(db.Model):
    """A bookable time slot published by a medical expert."""
    __tablename__ = "availabilities"
    id = db.Column(db.Integer, primary_key=True)
    expert_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    slot_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_booked = db.Column(db.Boolean, default=False, nullable=False)

    expert = db.relationship("User", backref="slots")

    @property
    def is_past(self):
        return datetime.combine(self.slot_date, self.start_time) <= datetime.now()


def future_slot_filter():
    now = datetime.now()
    return or_(Availability.slot_date > now.date(),
               and_(Availability.slot_date == now.date(), Availability.start_time > now.time()))


class Consultation(db.Model):
    __tablename__ = "consultations"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    expert_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    slot_id = db.Column(db.Integer, db.ForeignKey("availabilities.id"), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default=PENDING, nullable=False, index=True)
    expert_notes = db.Column(db.Text)   # private to the medical expert
    outcome = db.Column(db.Text)        # shared with the student
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship("User", foreign_keys=[student_id], backref="student_consultations")
    expert = db.relationship("User", foreign_keys=[expert_id], backref="expert_consultations")
    slot = db.relationship("Availability", backref="consultations")


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    message = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(200))
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(60), nullable=False, index=True)
    details = db.Column(db.String(255))
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship("User")


DEFAULT_SETTINGS = {
    "site_name": "ACC Consultation System",
    "allow_registration": "1",
    "max_active_per_student": "3",
}


class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.String(255), nullable=False)

    @staticmethod
    def get(key):
        row = db.session.get(Setting, key)
        return row.value if row else DEFAULT_SETTINGS.get(key, "")

    @staticmethod
    def set(key, value):
        row = db.session.get(Setting, key)
        if row:
            row.value = str(value)
        else:
            db.session.add(Setting(key=key, value=str(value)))
