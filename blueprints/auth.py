from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import current_user, login_user, logout_user, login_required
from extensions import db
from models import User, Role, Setting, ROLE_STUDENT
from utils import log_action, safe_next

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.active:
                log_action("login_blocked", f"Deactivated account: {email}", user_id=user.id)
                db.session.commit()
                flash("Your account has been deactivated. Please contact the administrator.", "danger")
                return render_template("auth/login.html")
            login_user(user)
            session.permanent = True
            user.last_login = datetime.utcnow()
            log_action("login", user_id=user.id)
            db.session.commit()
            nxt = request.args.get("next")
            return redirect(nxt if safe_next(nxt) else url_for("main.dashboard"))
        log_action("login_failed", f"Email: {email}")
        db.session.commit()
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    log_action("logout")
    db.session.commit()
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if Setting.get("allow_registration") != "1":
        flash("Student registration is currently closed. Please contact the administrator.", "warning")
        return redirect(url_for("auth.login"))
    form = request.form
    if request.method == "POST":
        name = form.get("full_name", "").strip()
        email = form.get("email", "").strip().lower()
        school_id = form.get("school_id", "").strip()
        department = form.get("department", "").strip()
        pw = form.get("password", "")
        errors = []
        if not name:
            errors.append("Full name is required.")
        if "@" not in email or "." not in email.split("@")[-1]:
            errors.append("Enter a valid email address.")
        elif User.query.filter_by(email=email).first():
            errors.append("That email is already registered.")
        if not school_id:
            errors.append("Student ID is required.")
        if len(pw) < 8:
            errors.append("Password must be at least 8 characters.")
        if pw != form.get("confirm_password", ""):
            errors.append("Passwords do not match.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/register.html", form=form)
        role = Role.query.filter_by(name=ROLE_STUDENT).one()
        user = User(role_id=role.id, full_name=name, email=email, school_id=school_id,
                    department=department)
        user.set_password(pw)
        db.session.add(user)
        db.session.flush()
        log_action("student_registered", email, user_id=user.id)
        db.session.commit()
        flash("Account created. You can sign in now.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)
