import uuid


from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    current_app,
)
from sqlalchemy.sql import func

from app.models import User
from app import db

auth = Blueprint("auth", __name__)


@auth.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            flash("Please fill out all fields", "error")
            return redirect(url_for("auth.index"))

        if not email.endswith(current_app.config["EMAIL_DOMAIN"]):
            flash(
                "Incorrect email, please provide your university email address", "error"
            )
            return redirect(url_for("auth.index"))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            if existing_user.check_password(password):
                new_session_id = str(uuid.uuid4())
                existing_user.session_id = new_session_id
                existing_user.last_login = func.now()
                db.session.commit()

                session["user_id"] = existing_user.id
                session["user_email"] = existing_user.email
                session["user_role"] = existing_user.role
                print(existing_user.role)
                session["session_id"] = new_session_id

                flash(
                    f"Welcome back, {existing_user.first_name} {existing_user.last_name}!",
                    "success",
                )

                if existing_user.is_tutor():
                    return redirect(url_for("tutor.dashboard"))
                return redirect(url_for("student.dashboard"))
            flash("Incorrect password", "error")
            return redirect(url_for("auth.index"))

        session_id = str(uuid.uuid4())
        new_user = User(
            email=email,
            session_id=session_id,
            last_login=func.now(),
        )
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        session["user_id"] = new_user.id
        session["user_email"] = new_user.email
        session["user_role"] = new_user.role
        session["session_id"] = session_id
        flash("Account created successfully!", "success")
        return redirect(url_for("student.dashboard"))

    return render_template("index.html")


@auth.route("/logout")
def logout():
    if "user_id" in session:
        # Update the session ID in the database when the user logs out
        user = db.session.get(User, session["user_id"])
        if user:
            user.session_id = str(uuid.uuid4())
            db.session.commit()

    session.clear()
    flash("You have been logged out successfully", "success")
    return redirect(url_for("auth.index"))
