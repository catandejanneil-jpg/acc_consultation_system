import os
from flask import Flask, render_template, request, url_for, flash, redirect
from flask_login import current_user, logout_user
from config import Config
from extensions import db, login_manager, csrf


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to continue."
    login_manager.login_message_category = "warning"

    from models import User, Notification, Setting

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from blueprints.main import bp as main_bp
    from blueprints.auth import bp as auth_bp
    from blueprints.student import bp as student_bp
    from blueprints.expert import bp as expert_bp
    from blueprints.admin import bp as admin_bp
    for bp in (main_bp, auth_bp, student_bp, expert_bp, admin_bp):
        app.register_blueprint(bp)

    @app.before_request
    def block_deactivated_sessions():
        if current_user.is_authenticated and not current_user.active:
            logout_user()
            flash("Your account has been deactivated. Please contact the administrator.", "danger")
            return redirect(url_for("auth.login"))

    @app.context_processor
    def inject_globals():
        unread = 0
        if current_user.is_authenticated:
            unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()

        def page_url(page):
            args = request.args.to_dict()
            args["page"] = page
            return url_for(request.endpoint, **{**(request.view_args or {}), **args})

        return {"site_name": Setting.get("site_name"), "unread_count": unread, "page_url": page_url}

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403, title="Access denied",
                               message="Your role does not have permission to open this page."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, title="Page not found",
                               message="The page or record you asked for does not exist."), 404

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("error.html", code=400, title="Request could not be verified",
                               message="Your form expired or was invalid. Go back, refresh the page and try again."), 400

    with app.app_context():
        db.create_all()
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
