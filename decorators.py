from functools import wraps
from flask import abort, current_app
from flask_login import current_user


def role_required(*roles):
    """Backend RBAC guard: 401->login redirect if anonymous, 403 if wrong role."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            if current_user.role.name not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapper
    return decorator
