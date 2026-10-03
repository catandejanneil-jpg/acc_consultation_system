"""Create tables, roles and demo data.

    python seed.py            # first-time setup (safe to re-run; skips if already seeded)
    python seed.py --reset    # DROP everything and re-seed (destroys all data)
"""
import sys
from datetime import date, time, timedelta, datetime

from app import app
from extensions import db
from models import (Role, User, Availability, Consultation, Notification, ActivityLog, Setting,
                    DEFAULT_SETTINGS, ROLE_ADMIN, ROLE_EXPERT, ROLE_STUDENT,
                    PENDING, APPROVED, COMPLETED)

DEMO_USERS = [
    # role,        name,                 email,               password,       extras
    (ROLE_ADMIN,   "System Administrator", "admin@acc.edu",    "Admin@12345",  {}),
    (ROLE_EXPERT,  "Dr. Maria Santos",     "expert1@acc.edu",  "Expert@12345", {"specialization": "General Medicine"}),
    (ROLE_EXPERT,  "Dr. Paolo Reyes",      "expert2@acc.edu",  "Expert@12345", {"specialization": "Counseling Psychology"}),
    (ROLE_STUDENT, "Ana Dela Cruz",        "student1@acc.edu", "Student@12345", {"school_id": "2024-0001", "department": "BS Nursing"}),
    (ROLE_STUDENT, "Juan Mercado",         "student2@acc.edu", "Student@12345", {"school_id": "2024-0002", "department": "BS Information Technology"}),
]


def seed(reset=False):
    with app.app_context():
        if reset:
            db.drop_all()
        db.create_all()
        if Role.query.first():
            print("Database already seeded. Use --reset to start over.")
            return

        roles = {
            ROLE_ADMIN: "Full system control",
            ROLE_EXPERT: "Manages schedule, requests and consultation notes",
            ROLE_STUDENT: "Books and tracks consultations",
        }
        for name, desc in roles.items():
            db.session.add(Role(name=name, description=desc))
        db.session.flush()

        for k, v in DEFAULT_SETTINGS.items():
            Setting.set(k, v)

        users = {}
        for role_name, full_name, email, pw, extra in DEMO_USERS:
            u = User(role_id=Role.query.filter_by(name=role_name).one().id,
                     full_name=full_name, email=email, **extra)
            u.set_password(pw)
            db.session.add(u)
            users[email] = u
        db.session.flush()

        # Sample slots for the next few days for both experts
        slots = []
        for expert_email in ("expert1@acc.edu", "expert2@acc.edu"):
            for offset in (1, 2, 3):
                for hour in (9, 10, 14):
                    s = Availability(expert_id=users[expert_email].id,
                                     slot_date=date.today() + timedelta(days=offset),
                                     start_time=time(hour, 0), end_time=time(hour, 45))
                    db.session.add(s)
                    slots.append(s)
        db.session.flush()

        # Sample consultations so each dashboard has something to show
        e1, s1, s2 = users["expert1@acc.edu"], users["student1@acc.edu"], users["student2@acc.edu"]
        e1_slots = [s for s in slots if s.expert_id == e1.id]
        samples = [(s1, e1_slots[0], PENDING, "Recurring headaches during exam weeks.", None, None),
                   (s2, e1_slots[1], APPROVED, "Need a medical clearance for the sports team.", None, None),
                   (s1, e1_slots[2], COMPLETED, "Follow-up on sleep problems.",
                    "Patient reports improved routine; monitor stress levels.",
                    "Keep a regular sleep schedule and return if symptoms persist.")]
        for student, slot, status, reason, notes, outcome in samples:
            slot.is_booked = True
            c = Consultation(student_id=student.id, expert_id=e1.id, slot_id=slot.id, reason=reason,
                             status=status, expert_notes=notes, outcome=outcome)
            db.session.add(c)
            db.session.add(Notification(user_id=e1.id, message=f"Sample request from {student.full_name}."))
        db.session.add(ActivityLog(user_id=users["admin@acc.edu"].id, action="database_seeded",
                                   details="Initial roles, demo users and sample data created"))
        db.session.commit()

        print("Seed complete. Demo accounts:")
        for role_name, full_name, email, pw, _ in DEMO_USERS:
            print(f"  {role_name:15} {email:20} {pw}")


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
