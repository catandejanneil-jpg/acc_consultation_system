from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from extensions import db
from models import Notification, ROLE_ADMIN, ROLE_EXPERT, ROLE_STUDENT
from utils import log_action, safe_next

bp = Blueprint("main", __name__)

HOME = {ROLE_ADMIN: "admin.dashboard", ROLE_EXPERT: "expert.dashboard", ROLE_STUDENT: "student.dashboard"}


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@bp.route("/dashboard")
@login_required
def dashboard():
    return redirect(url_for(HOME[current_user.role.name]))


@bp.route("/notifications")
@login_required
def notifications():
    items = (Notification.query.filter_by(user_id=current_user.id)
             .order_by(Notification.created_at.desc()).limit(100).all())
    return render_template("notifications.html", items=items)


@bp.route("/notifications/read-all", methods=["POST"])
@login_required
def read_all():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("main.notifications"))


@bp.route("/notifications/<int:nid>/open")
@login_required
def open_notification(nid):
    n = Notification.query.filter_by(id=nid, user_id=current_user.id).first_or_404()
    n.is_read = True
    db.session.commit()
    return redirect(n.link if safe_next(n.link) else url_for("main.notifications"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        if not name:
            flash("Full name is required.", "danger")
            return render_template("profile.html")
        current_user.full_name = name
        current_user.phone = phone
        new_pw = request.form.get("new_password", "")
        if new_pw:
            if not current_user.check_password(request.form.get("current_password", "")):
                flash("Current password is incorrect.", "danger")
                return render_template("profile.html")
            if len(new_pw) < 8:
                flash("New password must be at least 8 characters.", "danger")
                return render_template("profile.html")
            if new_pw != request.form.get("confirm_password", ""):
                flash("New password and confirmation do not match.", "danger")
                return render_template("profile.html")
            current_user.set_password(new_pw)
            log_action("password_changed")
        log_action("profile_updated")
        db.session.commit()
        flash("Profile saved.", "success")
        return redirect(url_for("main.profile"))
    return render_template("profile.html")
