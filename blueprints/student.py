from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from extensions import db
from decorators import role_required
from models import (User, Role, Availability, Consultation, Setting, future_slot_filter,
                    STATUSES, PENDING, APPROVED, CANCELLED, ROLE_EXPERT)
from utils import log_action, notify

bp = Blueprint("student", __name__, url_prefix="/student")
student_only = role_required("student")


def _mine(cid):
    return Consultation.query.filter_by(id=cid, student_id=current_user.id).first_or_404()


@bp.route("/")
@student_only
def dashboard():
    counts = {s: Consultation.query.filter_by(student_id=current_user.id, status=s).count() for s in STATUSES}
    upcoming = (Consultation.query.join(Consultation.slot)
                .filter(Consultation.student_id == current_user.id, Consultation.status == APPROVED,
                        Availability.slot_date >= date.today())
                .order_by(Availability.slot_date, Availability.start_time).limit(5).all())
    recent = (Consultation.query.filter_by(student_id=current_user.id)
              .order_by(Consultation.created_at.desc()).limit(5).all())
    return render_template("student/dashboard.html", counts=counts, upcoming=upcoming, recent=recent)


@bp.route("/book")
@student_only
def book():
    expert_id = request.args.get("expert_id", type=int)
    experts = (User.query.join(Role).filter(Role.name == ROLE_EXPERT, User.active.is_(True))
               .order_by(User.full_name).all())
    q = (Availability.query.join(User, Availability.expert_id == User.id)
         .filter(Availability.is_booked.is_(False), User.active.is_(True), future_slot_filter()))
    if expert_id:
        q = q.filter(Availability.expert_id == expert_id)
    slots = q.order_by(Availability.slot_date, Availability.start_time).all()
    return render_template("student/book.html", experts=experts, slots=slots, expert_id=expert_id)


@bp.route("/book/<int:slot_id>", methods=["GET", "POST"])
@student_only
def book_slot(slot_id):
    slot = db.session.get(Availability, slot_id)
    if slot is None:
        flash("That time slot no longer exists.", "warning")
        return redirect(url_for("student.book"))
    if slot.is_booked or slot.is_past or not slot.expert.active:
        flash("That time slot is no longer available. Please pick another.", "warning")
        return redirect(url_for("student.book"))
    if request.method == "POST":
        reason = request.form.get("reason", "").strip()
        if len(reason) < 10:
            flash("Please describe your concern in at least 10 characters.", "danger")
            return render_template("student/book_form.html", slot=slot, reason=reason)
        limit = int(Setting.get("max_active_per_student") or 3)
        active = Consultation.query.filter(Consultation.student_id == current_user.id,
                                           Consultation.status.in_([PENDING, APPROVED])).count()
        if active >= limit:
            flash(f"You can have at most {limit} open consultations. Cancel or complete one first.", "warning")
            return redirect(url_for("student.consultations"))
        # Atomic claim: only one student can flip is_booked from False to True.
        claimed = Availability.query.filter_by(id=slot.id, is_booked=False).update({"is_booked": True})
        if not claimed:
            db.session.rollback()
            flash("Someone just booked that slot. Please pick another.", "warning")
            return redirect(url_for("student.book"))
        c = Consultation(student_id=current_user.id, expert_id=slot.expert_id, slot_id=slot.id,
                         reason=reason, status=PENDING)
        db.session.add(c)
        db.session.flush()
        notify(slot.expert_id, f"New request from {current_user.full_name} for "
               f"{slot.slot_date:%b %d} at {slot.start_time:%I:%M %p}.", url_for("expert.detail", cid=c.id))
        log_action("consultation_requested", f"Consultation #{c.id}")
        db.session.commit()
        flash("Request sent. You will be notified when the expert responds.", "success")
        return redirect(url_for("student.detail", cid=c.id))
    return render_template("student/book_form.html", slot=slot, reason="")


@bp.route("/consultations")
@student_only
def consultations():
    status = request.args.get("status")
    q = Consultation.query.filter_by(student_id=current_user.id)
    if status in STATUSES:
        q = q.filter_by(status=status)
    items = q.order_by(Consultation.created_at.desc()).all()
    return render_template("student/consultations.html", items=items, status=status, statuses=STATUSES)


@bp.route("/consultations/<int:cid>")
@student_only
def detail(cid):
    return render_template("student/detail.html", c=_mine(cid))


@bp.route("/consultations/<int:cid>/cancel", methods=["POST"])
@student_only
def cancel(cid):
    c = _mine(cid)
    if c.status not in (PENDING, APPROVED):
        flash("Only pending or approved consultations can be cancelled.", "warning")
        return redirect(url_for("student.detail", cid=cid))
    c.status = CANCELLED
    c.slot.is_booked = False
    notify(c.expert_id, f"{current_user.full_name} cancelled the consultation on "
           f"{c.slot.slot_date:%b %d} at {c.slot.start_time:%I:%M %p}.", url_for("expert.detail", cid=c.id))
    log_action("consultation_cancelled", f"Consultation #{c.id} by student")
    db.session.commit()
    flash("Consultation cancelled. The time slot is open again.", "info")
    return redirect(url_for("student.detail", cid=cid))
