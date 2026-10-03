from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user
from extensions import db
from decorators import role_required
from models import (User, Availability, Consultation, STATUSES, PENDING, APPROVED, COMPLETED, CANCELLED)
from utils import log_action, notify

bp = Blueprint("expert", __name__, url_prefix="/expert")
expert_only = role_required("medical_expert")


def _mine(cid):
    return Consultation.query.filter_by(id=cid, expert_id=current_user.id).first_or_404()


def _when(c):
    return f"{c.slot.slot_date:%b %d, %Y} at {c.slot.start_time:%I:%M %p}"


@bp.route("/")
@expert_only
def dashboard():
    counts = {s: Consultation.query.filter_by(expert_id=current_user.id, status=s).count() for s in STATUSES}
    pending = (Consultation.query.join(Consultation.slot)
               .filter(Consultation.expert_id == current_user.id, Consultation.status == PENDING)
               .order_by(Availability.slot_date, Availability.start_time).limit(6).all())
    upcoming = (Consultation.query.join(Consultation.slot)
                .filter(Consultation.expert_id == current_user.id, Consultation.status == APPROVED,
                        Availability.slot_date >= date.today())
                .order_by(Availability.slot_date, Availability.start_time).limit(6).all())
    open_slots = Availability.query.filter(Availability.expert_id == current_user.id,
                                           Availability.is_booked.is_(False),
                                           Availability.slot_date >= date.today()).count()
    return render_template("expert/dashboard.html", counts=counts, pending=pending,
                           upcoming=upcoming, open_slots=open_slots)


# ---------- schedule ----------
@bp.route("/schedule", methods=["GET", "POST"])
@expert_only
def schedule():
    if request.method == "POST":
        try:
            d = datetime.strptime(request.form["slot_date"], "%Y-%m-%d").date()
            s = datetime.strptime(request.form["start_time"], "%H:%M").time()
            e = datetime.strptime(request.form["end_time"], "%H:%M").time()
        except (KeyError, ValueError):
            flash("Enter a valid date, start time and end time.", "danger")
            return redirect(url_for("expert.schedule"))
        if s >= e:
            flash("End time must be after start time.", "danger")
        elif datetime.combine(d, s) <= datetime.now():
            flash("You can only publish slots in the future.", "danger")
        elif Availability.query.filter(Availability.expert_id == current_user.id,
                                       Availability.slot_date == d,
                                       Availability.start_time < e, Availability.end_time > s).first():
            flash("That time overlaps a slot you already published.", "danger")
        else:
            db.session.add(Availability(expert_id=current_user.id, slot_date=d, start_time=s, end_time=e))
            log_action("slot_created", f"{d} {s:%H:%M}-{e:%H:%M}")
            db.session.commit()
            flash("Time slot published.", "success")
        return redirect(url_for("expert.schedule"))
    slots = (Availability.query.filter(Availability.expert_id == current_user.id,
                                       Availability.slot_date >= date.today())
             .order_by(Availability.slot_date, Availability.start_time).all())
    return render_template("expert/schedule.html", slots=slots, today=date.today().isoformat())


@bp.route("/schedule/<int:slot_id>/delete", methods=["POST"])
@expert_only
def delete_slot(slot_id):
    slot = Availability.query.filter_by(id=slot_id, expert_id=current_user.id).first_or_404()
    if slot.is_booked:
        flash("This slot is booked. Decline or cancel the consultation first.", "warning")
    elif slot.consultations:
        flash("This slot has consultation history and cannot be deleted.", "warning")
    else:
        db.session.delete(slot)
        log_action("slot_deleted", f"Slot #{slot_id}")
        db.session.commit()
        flash("Time slot removed.", "info")
    return redirect(url_for("expert.schedule"))


# ---------- requests ----------
@bp.route("/requests")
@expert_only
def requests_list():
    status = request.args.get("status")
    q = Consultation.query.filter_by(expert_id=current_user.id)
    if status in STATUSES:
        q = q.filter_by(status=status)
    items = q.order_by(Consultation.created_at.desc()).all()
    return render_template("expert/requests.html", items=items, status=status, statuses=STATUSES)


@bp.route("/consultations/<int:cid>")
@expert_only
def detail(cid):
    c = _mine(cid)
    history = (Consultation.query.filter(Consultation.expert_id == current_user.id,
                                         Consultation.student_id == c.student_id, Consultation.id != c.id)
               .order_by(Consultation.created_at.desc()).all())
    return render_template("expert/detail.html", c=c, history=history)


@bp.route("/consultations/<int:cid>/approve", methods=["POST"])
@expert_only
def approve(cid):
    c = _mine(cid)
    if c.status != PENDING:
        flash("Only pending requests can be approved.", "warning")
    else:
        c.status = APPROVED
        notify(c.student_id, f"Your consultation with {current_user.full_name} on {_when(c)} was approved.",
               url_for("student.detail", cid=c.id))
        log_action("consultation_approved", f"Consultation #{c.id}")
        db.session.commit()
        flash("Request approved. The student has been notified.", "success")
    return redirect(url_for("expert.detail", cid=cid))


@bp.route("/consultations/<int:cid>/decline", methods=["POST"])
@expert_only
def decline(cid):
    c = _mine(cid)
    if c.status not in (PENDING, APPROVED):
        flash("This consultation can no longer be declined.", "warning")
        return redirect(url_for("expert.detail", cid=cid))
    reason = request.form.get("reason", "").strip()
    c.status = CANCELLED
    c.slot.is_booked = False
    if reason:
        c.outcome = f"Declined/cancelled by expert: {reason}"
    notify(c.student_id, f"Your consultation with {current_user.full_name} on {_when(c)} was cancelled by the expert."
           + (f" Reason: {reason}" if reason else ""), url_for("student.detail", cid=c.id))
    log_action("consultation_declined", f"Consultation #{c.id}")
    db.session.commit()
    flash("Consultation cancelled and the time slot reopened.", "info")
    return redirect(url_for("expert.detail", cid=cid))


@bp.route("/consultations/<int:cid>/update", methods=["POST"])
@expert_only
def update(cid):
    c = _mine(cid)
    if c.status not in (APPROVED, COMPLETED):
        flash("Approve the request before recording notes or an outcome.", "warning")
        return redirect(url_for("expert.detail", cid=cid))
    c.expert_notes = request.form.get("expert_notes", "").strip()
    c.outcome = request.form.get("outcome", "").strip()
    if request.form.get("action") == "complete":
        if not c.outcome:
            flash("Add an outcome summary for the student before completing.", "danger")
            return redirect(url_for("expert.detail", cid=cid))
        c.status = COMPLETED
        notify(c.student_id, f"Your consultation on {_when(c)} is complete. View the outcome.",
               url_for("student.detail", cid=c.id))
        log_action("consultation_completed", f"Consultation #{c.id}")
        flash("Consultation marked as completed.", "success")
    else:
        log_action("consultation_notes_saved", f"Consultation #{c.id}")
        flash("Notes saved.", "success")
    db.session.commit()
    return redirect(url_for("expert.detail", cid=cid))


# ---------- student records (only students this expert has consulted) ----------
@bp.route("/students")
@expert_only
def students():
    rows = (User.query.join(Consultation, Consultation.student_id == User.id)
            .filter(Consultation.expert_id == current_user.id).distinct().order_by(User.full_name).all())
    return render_template("expert/students.html", students=rows)


@bp.route("/students/<int:sid>")
@expert_only
def student_record(sid):
    items = (Consultation.query.filter_by(expert_id=current_user.id, student_id=sid)
             .order_by(Consultation.created_at.desc()).all())
    if not items:
        abort(403)
    return render_template("expert/student_record.html", student=items[0].student, items=items)
