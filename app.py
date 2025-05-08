import datetime
import markdown
from flask import Flask, render_template, request, redirect, url_for, session, flash
import textwrap
from werkzeug.security import generate_password_hash
from flask_sqlalchemy import SQLAlchemy
import uuid
import subprocess
import tempfile
import os
import sys

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "a")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

EMAIL_DOMAIN = os.getenv("EMAIL_DOMAIN", "gmail.com")

db = SQLAlchemy(app)


@app.template_filter("markdown")
def markdown_filter(text):
    return markdown.markdown(text)


# Models
class Tutor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    challenges = db.relationship("Challenge", backref="tutor", lazy=True)
    lessons = db.relationship("Lesson", backref="tutor", lazy=True)


class Challenge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    initial_code = db.Column(db.Text, nullable=False)
    test_code = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now(datetime.UTC))
    tutor_id = db.Column(db.Integer, db.ForeignKey("tutor.id"), nullable=False)
    submissions = db.relationship("Submission", backref="challenge", lazy=True)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now(datetime.UTC))
    submissions = db.relationship("Submission", backref="student", lazy=True)
    password_hash = db.Column(db.String(256), nullable=False)


class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.Text, nullable=False)
    result = db.Column(db.Text, nullable=True)
    is_passing = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now(datetime.UTC))
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenge.id"), nullable=False)


class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now(datetime.UTC))
    tutor_id = db.Column(db.Integer, db.ForeignKey("tutor.id"), nullable=False)
    challenges = db.relationship(
        "Challenge", secondary="lesson_challenges", backref="lessons"
    )


# Create the many-to-many relationship table between lessons and challenges
lesson_challenges = db.Table(
    "lesson_challenges",
    db.Column("lesson_id", db.Integer, db.ForeignKey("lesson.id"), primary_key=True),
    db.Column(
        "challenge_id", db.Integer, db.ForeignKey("challenge.id"), primary_key=True
    ),
)


# Routes
@app.route("/")
def index():
    return render_template("index.html")


# Student Routes
from werkzeug.security import generate_password_hash, check_password_hash


@app.route("/student/join", methods=["GET", "POST"])
def student_join():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            flash("Please fill out all fields", "error")
            return redirect(url_for("student_join"))

        if not email.endswith(EMAIL_DOMAIN):
            flash(
                "Incorrect email, please provide your university email address", "error"
            )
            return redirect(url_for("student_join"))

        existing_student = Student.query.filter_by(email=email).first()
        if existing_student:
            if check_password_hash(existing_student.password_hash, password):
                session["student_id"] = existing_student.id
                session["student_email"] = existing_student.email
                flash("Welcome back, " + existing_student.email + "!", "success")
                return redirect(url_for("student_dashboard"))
            else:
                flash("Incorrect password", "error")
                return redirect(url_for("student_join"))

        session_id = str(uuid.uuid4())
        password_hash = generate_password_hash(password)
        new_student = Student(
            email=email, session_id=session_id, password_hash=password_hash
        )

        db.session.add(new_student)
        db.session.commit()

        session["student_id"] = new_student.id
        session["student_email"] = new_student.email
        flash("Account created successfully!", "success")
        return redirect(url_for("student_dashboard"))

    return render_template("student_join.html")


@app.route("/student/dashboard")
def student_dashboard():
    if "student_id" not in session:
        return redirect(url_for("student_join"))

    challenges = Challenge.query.all()
    submissions = Submission.query.filter_by(student_id=session["student_id"]).all()

    completed_challenges = set(
        submission.challenge_id for submission in submissions if submission.is_passing
    )

    return render_template(
        "student_dashboard.html",
        challenges=challenges,
        completed_challenges=completed_challenges,
    )


@app.route("/student/challenge/<int:challenge_id>", methods=["GET", "POST"])
def student_challenge(challenge_id):
    if "student_id" not in session:
        return redirect(url_for("student_join"))

    challenge = Challenge.query.get_or_404(challenge_id)

    # Get the student's latest submission for this challenge, if any
    submission = (
        Submission.query.filter_by(
            student_id=session["student_id"], challenge_id=challenge_id
        )
        .order_by(Submission.created_at.desc())
        .first()
    )

    code_to_display = submission.code if submission else challenge.initial_code

    if request.method == "POST":
        code = request.form.get("code")
        action = request.form.get("action")

        new_submission = Submission(
            code=code, student_id=session["student_id"], challenge_id=challenge_id
        )

        if action == "validate":
            result, is_passing = run_code_with_tests(code, challenge.test_code)
            new_submission.result = result
            new_submission.is_passing = is_passing

        db.session.add(new_submission)
        db.session.commit()

        # Redirect to avoid form resubmission
        return redirect(url_for("student_challenge", challenge_id=challenge_id))

    return render_template(
        "student_challenge.html",
        challenge=challenge,
        code=code_to_display,
        submission=submission,
    )


# Tutor Routes
@app.route("/tutor/dashboard")
def tutor_dashboard():
    if "tutor_id" not in session:
        return redirect(url_for("tutor_login"))

    tutor = Tutor.query.get(session["tutor_id"])
    challenges = Challenge.query.filter_by(tutor_id=tutor.id).all()

    # Get all submissions for the tutor's challenges
    submissions = []
    for challenge in challenges:
        challenge_submissions = Submission.query.filter_by(
            challenge_id=challenge.id
        ).all()
        for submission in challenge_submissions:
            student = Student.query.get(submission.student_id)
            submissions.append(
                {
                    "challenge_title": challenge.title,
                    "student_email": student.email,
                    "created_at": submission.created_at,
                    "is_passing": submission.is_passing,
                }
            )

    return render_template(
        "tutor_dashboard.html",
        tutor=tutor,
        challenges=challenges,
        submissions=submissions,
    )


@app.route("/tutor/login", methods=["GET", "POST"])
def tutor_login():
    if request.method == "POST":
        email = request.form.get("email")
        tutor = Tutor.query.filter_by(email=email).first()

        if not tutor:
            flash("Tutor not found", "error")
            return redirect(url_for("tutor_login"))

        session["tutor_id"] = tutor.id
        session["tutor_name"] = tutor.name

        return redirect(url_for("tutor_dashboard"))

    return render_template("tutor_login.html")


@app.route("/tutor/create_challenge", methods=["GET", "POST"])
def create_challenge():
    if "tutor_id" not in session:
        return redirect(url_for("tutor_login"))

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        initial_code = request.form.get("initial_code")
        test_code = request.form.get("test_code")

        new_challenge = Challenge(
            title=title,
            description=description,
            initial_code=initial_code,
            test_code=test_code,
            tutor_id=session["tutor_id"],
        )

        db.session.add(new_challenge)
        db.session.commit()

        flash("Challenge created successfully!", "success")
        return redirect(url_for("tutor_dashboard"))

    return render_template("create_challenge.html")


@app.route("/tutor/edit_challenge/<int:challenge_id>", methods=["GET", "POST"])
def edit_challenge(challenge_id):
    if "tutor_id" not in session:
        return redirect(url_for("tutor_login"))

    challenge = Challenge.query.get_or_404(challenge_id)

    # Ensure this challenge belongs to the current tutor
    if challenge.tutor_id != session["tutor_id"]:
        flash("You do not have permission to edit this challenge", "error")
        return redirect(url_for("tutor_dashboard"))

    if request.method == "POST":
        challenge.title = request.form.get("title")
        challenge.description = request.form.get("description")
        challenge.initial_code = request.form.get("initial_code")
        challenge.test_code = request.form.get("test_code")

        db.session.commit()

        flash("Challenge updated successfully!", "success")
        return redirect(url_for("challenge_detail", challenge_id=challenge.id))

    return render_template("edit_challenge.html", challenge=challenge)


@app.route("/tutor/submission/<int:submission_id>")
def view_submission(submission_id):
    if "tutor_id" not in session:
        return redirect(url_for("tutor_login"))

    submission = Submission.query.get_or_404(submission_id)
    student = Student.query.get(submission.student_id)
    challenge = Challenge.query.get(submission.challenge_id)

    # Verify this challenge belongs to the current tutor
    if challenge.tutor_id != session["tutor_id"]:
        flash("You do not have permission to view this submission", "error")
        return redirect(url_for("tutor_dashboard"))

    return render_template(
        "view_submission.html",
        submission=submission,
        student=student,
        challenge=challenge,
    )


@app.route("/tutor/challenge/<int:challenge_id>")
def challenge_detail(challenge_id):
    if "tutor_id" not in session:
        return redirect(url_for("tutor_login"))

    challenge = Challenge.query.get_or_404(challenge_id)
    submissions = Submission.query.filter_by(challenge_id=challenge_id).all()

    student_progress = {}
    for submission in submissions:
        student = Student.query.get(submission.student_id)
        if student.id not in student_progress:
            student_progress[student.id] = {
                "email": student.email,
                "submissions": 0,
                "latest_submission": None,
                "has_passed": False,
            }

        student_progress[student.id]["submissions"] += 1

        if (
            not student_progress[student.id]["latest_submission"]
            or submission.created_at
            > student_progress[student.id]["latest_submission"].created_at
        ):
            student_progress[student.id]["latest_submission"] = submission

        if submission.is_passing:
            student_progress[student.id]["has_passed"] = True

    return render_template(
        "challenge_detail.html",
        challenge=challenge,
        student_progress=student_progress.values(),
        Submission=Submission,
    )


@app.route("/logout")
def logout():
    # Clear the session
    session.clear()
    flash("You have been logged out successfully", "success")
    return redirect(url_for("index"))


@app.route("/tutor/lessons")
def tutor_lessons():
    if "tutor_id" not in session:
        return redirect(url_for("tutor_login"))

    tutor = Tutor.query.get(session["tutor_id"])
    lessons = Lesson.query.filter_by(tutor_id=tutor.id).all()

    return render_template("tutor_lessons.html", tutor=tutor, lessons=lessons)


@app.route("/tutor/create_lesson", methods=["GET", "POST"])
def create_lesson():
    if "tutor_id" not in session:
        return redirect(url_for("tutor_login"))

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")

        new_lesson = Lesson(
            title=title, description=description, tutor_id=session["tutor_id"]
        )

        # Get selected challenges
        challenge_ids = request.form.getlist("challenges")
        for challenge_id in challenge_ids:
            challenge = Challenge.query.get(challenge_id)
            if challenge and challenge.tutor_id == session["tutor_id"]:
                new_lesson.challenges.append(challenge)

        db.session.add(new_lesson)
        db.session.commit()

        flash("Lesson created successfully!", "success")
        return redirect(url_for("tutor_lessons"))

    # Get all challenges created by this tutor
    challenges = Challenge.query.filter_by(tutor_id=session["tutor_id"]).all()
    return render_template("create_lesson.html", challenges=challenges)


@app.route("/tutor/lesson/<int:lesson_id>")
def lesson_detail(lesson_id):
    if "tutor_id" not in session:
        return redirect(url_for("tutor_login"))

    lesson = Lesson.query.get_or_404(lesson_id)

    # Ensure this lesson belongs to the current tutor
    if lesson.tutor_id != session["tutor_id"]:
        flash("You do not have permission to view this lesson", "error")
        return redirect(url_for("tutor_dashboard"))

    # For each challenge in this lesson, get student progress
    challenges_data = []
    for challenge in lesson.challenges:
        submissions = Submission.query.filter_by(challenge_id=challenge.id).all()

        # Count unique students and those who completed the challenge
        students_attempted = set()
        students_completed = set()

        for submission in submissions:
            students_attempted.add(submission.student_id)
            if submission.is_passing:
                students_completed.add(submission.student_id)

        challenges_data.append(
            {
                "challenge": challenge,
                "students_attempted": len(students_attempted),
                "students_completed": len(students_completed),
            }
        )

    return render_template(
        "lesson_detail.html", lesson=lesson, challenges_data=challenges_data
    )


@app.route("/tutor/edit_lesson/<int:lesson_id>", methods=["GET", "POST"])
def edit_lesson(lesson_id):
    if "tutor_id" not in session:
        return redirect(url_for("tutor_login"))

    lesson = Lesson.query.get_or_404(lesson_id)

    # Ensure this lesson belongs to the current tutor
    if lesson.tutor_id != session["tutor_id"]:
        flash("You do not have permission to edit this lesson", "error")
        return redirect(url_for("tutor_dashboard"))

    if request.method == "POST":
        lesson.title = request.form.get("title")
        lesson.description = request.form.get("description")

        # Update challenges
        lesson.challenges = []
        challenge_ids = request.form.getlist("challenges")
        for challenge_id in challenge_ids:
            challenge = Challenge.query.get(challenge_id)
            if challenge and challenge.tutor_id == session["tutor_id"]:
                lesson.challenges.append(challenge)

        db.session.commit()

        flash("Lesson updated successfully!", "success")
        return redirect(url_for("lesson_detail", lesson_id=lesson.id))

    # Get all challenges created by this tutor
    all_challenges = Challenge.query.filter_by(tutor_id=session["tutor_id"]).all()
    selected_challenge_ids = [c.id for c in lesson.challenges]

    return render_template(
        "edit_lesson.html",
        lesson=lesson,
        all_challenges=all_challenges,
        selected_challenge_ids=selected_challenge_ids,
    )


@app.route("/student/lessons")
def student_lessons():
    if "student_id" not in session:
        return redirect(url_for("student_join"))

    lessons = Lesson.query.all()
    student_id = session["student_id"]

    # For each lesson, calculate completion percentage
    lessons_data = []
    for lesson in lessons:
        total_challenges = len(lesson.challenges)
        if total_challenges == 0:
            completion = 100  # If no challenges, consider it 100% complete
        else:
            completed_challenges = 0
            for challenge in lesson.challenges:
                # Check if student has passed this challenge
                submission = Submission.query.filter_by(
                    student_id=student_id, challenge_id=challenge.id, is_passing=True
                ).first()

                if submission:
                    completed_challenges += 1

            completion = (completed_challenges / total_challenges) * 100

        lessons_data.append(
            {
                "lesson": lesson,
                "completion": completion,
                "completed_challenges": (
                    completed_challenges if total_challenges > 0 else 0
                ),
                "total_challenges": total_challenges,
            }
        )

    return render_template("student_lessons.html", lessons_data=lessons_data)


@app.route("/student/lesson/<int:lesson_id>")
def student_lesson_detail(lesson_id):
    if "student_id" not in session:
        return redirect(url_for("student_join"))

    lesson = Lesson.query.get_or_404(lesson_id)
    student_id = session["student_id"]

    # For each challenge in this lesson, get student's progress
    challenges_data = []
    for challenge in lesson.challenges:
        # Check if student has passed this challenge
        submission = Submission.query.filter_by(
            student_id=student_id, challenge_id=challenge.id, is_passing=True
        ).first()

        challenges_data.append(
            {
                "challenge": challenge,
                "completed": submission is not None,
                "last_submission": Submission.query.filter_by(
                    student_id=student_id, challenge_id=challenge.id
                )
                .order_by(Submission.created_at.desc())
                .first(),
            }
        )

    return render_template(
        "student_lesson_detail.html", lesson=lesson, challenges_data=challenges_data
    )


def run_code_with_tests(student_code, test_code):
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            solution_path = os.path.join(temp_dir, "solution.py")
            test_path = os.path.join(temp_dir, "test_solution.py")

            # Write student code
            with open(solution_path, "w") as f:
                f.write(student_code)

            # Write test code
            with open(test_path, "w") as f:
                indented_test_code = textwrap.indent(test_code.strip(), "    ")
                f.write(
                    f"""
import unittest
from solution import *

class TestSolution(unittest.TestCase):
{indented_test_code}

if __name__ == '__main__':
    unittest.main()
"""
                )

            # Run the test script and capture output
            result = subprocess.run(
                [sys.executable, test_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=5,
                text=True,
            )

            output = result.stdout
            success = result.returncode == 0  # this is more reliable

            return output, success

    except Exception as e:
        return str(e), False


# Initialize database
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
