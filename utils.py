from flask import request
from flask_login import current_user
from extensions import db
from models import ActivityLog, Notification


def log_action(action, details="", user_id=None):
    """Queue an audit-log row. Caller is responsible for db.session.commit()."""
    if user_id is None and current_user.is_authenticated:
        user_id = current_user.id
    db.session.add(ActivityLog(user_id=user_id, action=action,
                               details=(details or "")[:255], ip_address=request.remote_addr))


def notify(user_id, message, link=None):
    """Queue an in-app notification. Caller is responsible for db.session.commit()."""
    db.session.add(Notification(user_id=user_id, message=message[:255], link=link))


def safe_next(url):
    return bool(url) and url.startswith("/") and not url.startswith("//") and "\\" not in url
