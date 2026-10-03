from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from sqlalchemy import or_
from extensions import db
from decorators import role_required
from models import (User, Role, Consultation, ActivityLog, Setting, STATUSES,
                    ROLE_ADMIN, ROLE_EXPERT, ROLE_STUDENT, ROLE_LABELS)
from utils import log_action

bp = Blueprint("admin", __name__, url_prefix="/admin")
admin_only = role_required("super_admin")
MANAGEABLE = (ROLE_EXPERT, ROLE_STUDENT)


@bp.route("/")
@admin_only
def dashboard():
    role_counts = {}
    for r in Role.query.all():
        total = User.query.filter_by(role_id=r.id).count()
        active = User.query.filter_by(role_id=r.id, active=True).count()
        role_counts[r.name] = (total, active)
    status_counts = {s: Consultation.query.filter_by(status=s).count() for s in STATUSES}
    logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(8).all()
    return render_template("admin/dashboard.html", role_counts=role_counts,
                           status_counts=status_counts, logs=logs, labels=ROLE_LABELS)


@bp.route("/users")
@admin_only
def users():
    q = User.query.join(Role)
    role = request.args.get("role", "")
    term = request.args.get("q", "").strip()
    if role in ROLE_LABELS:
        q = q.filter(Role.name == role)
    if term:
        like = f"%{term}%"
        q = q.filter(or_(User.full_name.ilike(like), User.email.ilike(like), User.school_id.ilike(like)))
    page = request.args.get("page", 1, type=int)
    pagination = q.order_by(User.full_name).paginate(page=page, per_page=15, error_out=False)
    return render_template("admin/users.html", pagination=pagination, role=role, term=term, labels=ROLE_LABELS)


def _save_user(user=None):
    form = request.form
    creating = user is None
    name = form.get("full_name", "").strip()
    email = form.get("email", "").strip().lower()
    pw = form.get("password", "")
    role_name = ROLE_ADMIN if (not creating and user.is_admin) else form.get("role", "")
    errors = []
    if not name:
        errors.append("Full name is required.")
    if "@" not in email or "." not in email.split("@")[-1]:
        errors.append("Enter a valid email address.")
    else:
        clash = User.query.filter(User.email == email)
        if not creating:
            clash = clash.filter(User.id != user.id)
        if clash.first():
            errors.append("That email is already in use.")
    if role_name != ROLE_ADMIN and role_name not in MANAGEABLE:
        errors.append("Choose a valid role.")
    if (creating or pw) and len(pw) < 8:
        errors.append("Password must be at least 8 characters.")
    if errors:
        for e in errors:
            flash(e, "danger")
        return None
    role_id = Role.query.filter_by(name=role_name).one().id  # look up before adding the new row (autoflush)
    if creating:
        user = User()
        db.session.add(user)
    user.role_id = role_id
    user.full_name, user.email = name, email
    user.phone = form.get("phone", "").strip()
    user.school_id = form.get("school_id", "").strip()
    user.department = form.get("department", "").strip()
    user.specialization = form.get("specialization", "").strip()
    if pw:
        user.set_password(pw)
    db.session.flush()
    log_action("user_created" if creating else "user_updated", f"{email} ({role_name})")
    db.session.commit()
    return user


@bp.route("/users/new", methods=["GET", "POST"])
@admin_only
def user_new():
    if request.method == "POST":
        if _save_user():
            flash("User created.", "success")
            return redirect(url_for("admin.users"))
        return render_template("admin/user_form.html", u=None, form=request.form, labels=ROLE_LABELS)
    return render_template("admin/user_form.html", u=None, form={}, labels=ROLE_LABELS)


@bp.route("/users/<int:uid>/edit", methods=["GET", "POST"])
@admin_only
def user_edit(uid):
    user = db.session.get(User, uid) or None
    if user is None:
        return render_template("error.html", code=404, title="User not found", message="No such user."), 404
    if request.method == "POST":
        if _save_user(user):
            flash("User updated.", "success")
            return redirect(url_for("admin.users"))
        db.session.rollback()
        return render_template("admin/user_form.html", u=user, form=request.form, labels=ROLE_LABELS)
    return render_template("admin/user_form.html", u=user, form={}, labels=ROLE_LABELS)


@bp.route("/users/<int:uid>/toggle", methods=["POST"])
@admin_only
def user_toggle(uid):
    user = db.session.get(User, uid)
    if user is None:
        return redirect(url_for("admin.users"))
    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "warning")
    else:
        user.active = not user.active
        log_action("user_activated" if user.active else "user_deactivated", user.email)
        db.session.commit()
        flash(f"{user.full_name} is now {'active' if user.active else 'deactivated'}.", "success")
    return redirect(request.referrer or url_for("admin.users"))


@bp.route("/consultations")
@admin_only
def consultations():
    status = request.args.get("status")
    q = Consultation.query
    if status in STATUSES:
        q = q.filter_by(status=status)
    page = request.args.get("page", 1, type=int)
    pagination = q.order_by(Consultation.created_at.desc()).paginate(page=page, per_page=15, error_out=False)
    return render_template("admin/consultations.html", pagination=pagination, status=status, statuses=STATUSES)


@bp.route("/logs")
@admin_only
def logs():
    term = request.args.get("q", "").strip()
    q = ActivityLog.query
    if term:
        like = f"%{term}%"
        q = q.filter(or_(ActivityLog.action.ilike(like), ActivityLog.details.ilike(like)))
    page = request.args.get("page", 1, type=int)
    pagination = q.order_by(ActivityLog.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    return render_template("admin/logs.html", pagination=pagination, term=term)


@bp.route("/settings", methods=["GET", "POST"])
@admin_only
def settings():
    if request.method == "POST":
        name = request.form.get("site_name", "").strip()
        limit = request.form.get("max_active_per_student", type=int)
        if not name or not limit or not (1 <= limit <= 20):
            flash("Enter a system name and a booking limit between 1 and 20.", "danger")
        else:
            Setting.set("site_name", name)
            Setting.set("allow_registration", "1" if request.form.get("allow_registration") else "0")
            Setting.set("max_active_per_student", limit)
            log_action("settings_updated")
            db.session.commit()
            flash("Settings saved.", "success")
        return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html", s={k: Setting.get(k) for k in
                           ("site_name", "allow_registration", "max_active_per_student")})
