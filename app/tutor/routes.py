from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from app.models import User, Challenge, Submission, Lesson, Group
from app.decorators import tutor_required

from app import db


tutor = Blueprint("tutor", __name__, template_folder="templates")


@tutor.before_request
@tutor_required
def before_request():
    pass


@tutor.route("/dashboard")
def dashboard():
    user = User.query.get(session["user_id"])
    challenges = Challenge.query.filter_by(user_id=session["user_id"]).all()

    submissions = Submission.query.order_by(Submission.created_at.desc()).limit(25)

    return render_template(
        "tutor/dashboard.html",
        tutor=user,
        challenges=challenges,
        submissions=submissions,
    )


@tutor.route("/create_challenge", methods=["GET", "POST"])
def create_challenge():
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
            user_id=session["user_id"],
        )

        db.session.add(new_challenge)
        db.session.commit()

        flash("Challenge created successfully!", "success")
        return redirect(url_for("tutor.dashboard"))

    return render_template("tutor/create_challenge.html")


@tutor.route("/edit_challenge/<int:challenge_id>", methods=["GET", "POST"])
def edit_challenge(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)

    # Ensure this challenge belongs to the current tutor
    if challenge.user_id != session["user_id"]:
        flash("You do not have permission to edit this challenge", "error")
        return redirect(url_for("tutor.dashboard"))

    if request.method == "POST":
        challenge.title = request.form.get("title")
        challenge.description = request.form.get("description")
        challenge.initial_code = request.form.get("initial_code")
        challenge.test_code = request.form.get("test_code")

        db.session.commit()

        flash("Challenge updated successfully!", "success")
        return redirect(url_for("tutor.challenge_detail", challenge_id=challenge.id))

    return render_template("tutor/edit_challenge.html", challenge=challenge)


@tutor.route("/submission/<int:submission_id>")
def view_submission(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    student = User.query.get(submission.user_id)
    challenge = Challenge.query.get(submission.challenge_id)

    # Verify this challenge belongs to the current tutor
    if challenge.user_id != session["user_id"]:
        flash("You do not have permission to view this submission", "error")
        return redirect(url_for("tutor.dashboard"))

    return render_template(
        "tutor/view_submission.html",
        submission=submission,
        student=student,
        challenge=challenge,
    )


@tutor.route("/challenge/<int:challenge_id>")
def challenge_detail(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)
    submissions = Submission.query.filter_by(challenge_id=challenge_id).all()

    student_progress = {}
    for submission in submissions:
        student = User.query.get(submission.user_id)
        if student.id not in student_progress:
            student_progress[student.id] = {
                "last_name": student.last_name,
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
        "tutor/challenge_detail.html",
        challenge=challenge,
        student_progress=student_progress.values(),
        Submission=Submission,
    )


@tutor.route("/lessons")
def view_lessons():
    user = User.query.get(session["user_id"])
    lessons = Lesson.query.filter_by(user_id=session["user_id"]).all()

    return render_template("tutor/lessons.html", tutor=user, lessons=lessons)


@tutor.route("/create_lesson", methods=["GET", "POST"])
def create_lesson():
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        visible = True if request.form.get("visible") == "on" else False

        new_lesson = Lesson(
            title=title,
            description=description,
            user_id=session["user_id"],
            visible=visible,
        )

        # Get selected challenges
        challenge_ids = request.form.getlist("challenges")
        for challenge_id in challenge_ids:
            challenge = Challenge.query.get(challenge_id)
            if challenge and challenge.user_id == session["user_id"]:
                new_lesson.challenges.append(challenge)

        db.session.add(new_lesson)
        db.session.commit()

        flash("Lesson created successfully!", "success")
        return redirect(url_for("tutor.view_lessons"))

    # Get all challenges created by this tutor
    challenges = Challenge.query.filter_by(user_id=session["user_id"]).all()
    return render_template("tutor/create_lesson.html", challenges=challenges)


@tutor.route("/lesson/<int:lesson_id>")
def lesson_detail(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)

    # Ensure this lesson belongs to the current tutor
    if lesson.user_id != session["user_id"]:
        flash("You do not have permission to view this lesson", "error")
        return redirect(url_for("tutor.dashboard"))

    # For each challenge in this lesson, get student progress
    challenges_data = []
    for challenge in lesson.challenges:
        submissions = Submission.query.filter_by(challenge_id=challenge.id).all()

        # Count unique students and those who completed the challenge
        students_attempted = set()
        students_completed = set()

        for submission in submissions:
            students_attempted.add(submission.user_id)
            if submission.is_passing:
                students_completed.add(submission.user_id)

        challenges_data.append(
            {
                "challenge": challenge,
                "students_attempted": len(students_attempted),
                "students_completed": len(students_completed),
            }
        )

    return render_template(
        "tutor/lesson_detail.html", lesson=lesson, challenges_data=challenges_data
    )


@tutor.route("/edit_lesson/<int:lesson_id>", methods=["GET", "POST"])
def edit_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)

    # Ensure this lesson belongs to the current tutor
    if lesson.user_id != session["user_id"]:
        flash("You do not have permission to edit this lesson", "error")
        return redirect(url_for("tutor.dashboard"))

    if request.method == "POST":
        lesson.title = request.form.get("title")
        lesson.description = request.form.get("description")
        lesson.visible = True if request.form.get("visible") == "on" else False

        # Update challenges
        lesson.challenges = []
        challenge_ids = request.form.getlist("challenges")
        for challenge_id in challenge_ids:
            challenge = Challenge.query.get(challenge_id)
            if challenge and challenge.user_id == session["user_id"]:
                lesson.challenges.append(challenge)

        db.session.commit()

        flash("Lesson updated successfully!", "success")
        return redirect(url_for("tutor.lesson_detail", lesson_id=lesson.id))

    # Get all challenges created by this tutor
    all_challenges = Challenge.query.filter_by(user_id=session["user_id"]).all()
    selected_challenge_ids = [c.id for c in lesson.challenges]

    return render_template(
        "tutor/edit_lesson.html",
        lesson=lesson,
        all_challenges=all_challenges,
        selected_challenge_ids=selected_challenge_ids,
    )


@tutor.route("/groups")
def view_groups():
    user = User.query.get(session["user_id"])
    groups = Group.query.order_by(Group.year.desc(), Group.name).all()

    return render_template("tutor/groups.html", tutor=user, groups=groups)


@tutor.route("/create_group", methods=["GET", "POST"])
def create_group():
    if request.method == "POST":
        name = request.form.get("name")
        year = request.form.get("year")

        new_group = Group(name=name, year=year)

        db.session.add(new_group)
        db.session.commit()

        flash("Group created successfully!", "success")
        return redirect(url_for("tutor.view_groups"))

    return render_template("tutor/create_group.html")


@tutor.route("/edit_group/<int:group_id>", methods=["GET", "POST"])
def edit_group(group_id):
    group = Group.query.get_or_404(group_id)

    if request.method == "POST":
        group.name = request.form.get("name")
        group.year = request.form.get("year")

        db.session.commit()

        flash("Group updated successfully!", "success")
        return redirect(url_for("tutor.view_groups"))

    return render_template("tutor/edit_group.html", group=group)


@tutor.route("/group/<int:group_id>")
def group_detail(group_id):
    group = Group.query.get_or_404(group_id)
    students = User.query.filter_by(group_id=group_id, role="student").all()

    return render_template("tutor/group_detail.html", group=group, students=students)


@tutor.route("/manage_group_lessons/<int:group_id>", methods=["GET", "POST"])
def manage_group_lessons(group_id):
    group = Group.query.get_or_404(group_id)

    if request.method == "POST":
        # Clear current enabled lessons
        group.enabled_lessons = []

        # Add newly selected lessons
        lesson_ids = request.form.getlist("lessons")
        for lesson_id in lesson_ids:
            lesson = Lesson.query.get(lesson_id)
            if lesson:
                group.enabled_lessons.append(lesson)

        db.session.commit()

        flash("Group lessons updated successfully!", "success")
        return redirect(url_for("tutor.group_detail", group_id=group.id))

    # Get all lessons created by this tutor
    lessons = Lesson.query.filter_by(user_id=session["user_id"]).all()
    enabled_lesson_ids = [lesson.id for lesson in group.enabled_lessons]

    return render_template(
        "tutor/manage_group_lessons.html",
        group=group,
        lessons=lessons,
        enabled_lesson_ids=enabled_lesson_ids,
    )


@tutor.route("/assign_students", methods=["GET", "POST"])
def assign_students():
    groups = Group.query.order_by(Group.year.desc(), Group.name).all()
    students = User.query.filter_by(role="student").order_by(User.last_name).all()

    if request.method == "POST":
        for student_id in request.form:
            if student_id.startswith("student_"):
                user_id = int(student_id.replace("student_", ""))
                group_id = request.form.get(student_id)

                student = User.query.get(user_id)
                if student and student.role == "student":
                    if group_id == "none":
                        student.group_id = None
                    else:
                        student.group_id = int(group_id)

        db.session.commit()
        flash("Student group assignments updated successfully!", "success")
        return redirect(url_for("tutor.view_groups"))

    return render_template(
        "tutor/assign_students.html", groups=groups, students=students
    )
