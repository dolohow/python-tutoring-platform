from functools import wraps
from flask import session, redirect, url_for, flash
from app import db
from app.models import User


def role_required(role_check_func):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first", "error")
                return redirect(url_for("auth.index"))

            user = db.session.get(User, session["user_id"])
            if (
                not user
                or user.session_id != session["session_id"]
                or not role_check_func(user)
            ):
                session.clear()
                flash("Your session has expired or you don't have permission", "error")
                return redirect(url_for("auth.index"))

            return f(*args, **kwargs)

        return decorated_function

    return decorator


student_required = role_required(lambda user: user.is_student())
tutor_required = role_required(lambda user: user.is_tutor())
