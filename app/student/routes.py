from flask import request, redirect, url_for
from flask import Blueprint, render_template, session

from app import db
from app.decorators import student_required
from app.models import Challenge, Submission, Lesson, User, Group
from app.services import run_code_with_tests


student = Blueprint("student", __name__, template_folder="templates")


@student.before_request
@student_required
def before_request():
    pass


@student.route("/dashboard")
def dashboard():
    submissions = Submission.query.filter_by(user_id=session["user_id"]).all()
    user = db.session.query(User).get(session["user_id"])
    group = db.session.query(Group).get(user.group_id) if user.group_id else None

    completed_challenges = set(
        submission.challenge_id for submission in submissions if submission.is_passing
    )

    # Add challenges from lessons enabled for the student's group
    available_challenges = []
    if group:
        for lesson in group.enabled_lessons:
            for challenge in lesson.challenges:
                if challenge not in available_challenges:
                    available_challenges.append(challenge)

    # Add challenges from globally visible lessons
    visible_lessons = Lesson.query.filter_by(visible=True).all()
    for lesson in visible_lessons:
        for challenge in lesson.challenges:
            if challenge not in available_challenges:
                available_challenges.append(challenge)

    return render_template(
        "student/dashboard.html",
        group=group,
        challenges=available_challenges,
        completed_challenges=completed_challenges,
    )


@student.route("/challenge/<int:challenge_id>", methods=["GET", "POST"])
def challenge_detail(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)

    # Get the student's latest submission for this challenge, if any
    submission = (
        Submission.query.filter_by(
            user_id=session["user_id"], challenge_id=challenge_id
        )
        .order_by(Submission.created_at.desc())
        .first()
    )

    code_to_display = submission.code if submission else challenge.initial_code

    if request.method == "POST":
        code = request.form.get("code")

        new_submission = Submission(
            code=code, user_id=session["user_id"], challenge_id=challenge_id
        )

        result, is_passing = run_code_with_tests(code, challenge.test_code)
        new_submission.result = result
        new_submission.is_passing = is_passing

        db.session.add(new_submission)
        db.session.commit()

        return redirect(url_for("student.challenge_detail", challenge_id=challenge_id))

    return render_template(
        "student/challenge.html",
        challenge=challenge,
        code=code_to_display,
        submission=submission,
    )


@student.route("/lessons")
def view_lessons():
    user = db.session.query(User).get(session["user_id"])
    lessons = Lesson.query.filter_by(visible=True).all()
    if user.group_id:
        group = db.session.query(Group).get(user.group_id)
        lessons.extend(group.enabled_lessons)

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
                    user_id=session["user_id"],
                    challenge_id=challenge.id,
                    is_passing=True,
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

    return render_template("student/lessons.html", lessons_data=lessons_data)


@student.route("/lesson/<int:lesson_id>")
def lesson_detail(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)

    # For each challenge in this lesson, get student's progress
    challenges_data = []
    for challenge in lesson.challenges:
        # Check if student has passed this challenge
        submission = Submission.query.filter_by(
            user_id=session["user_id"], challenge_id=challenge.id, is_passing=True
        ).first()

        challenges_data.append(
            {
                "challenge": challenge,
                "completed": submission is not None,
                "last_submission": Submission.query.filter_by(
                    user_id=session["user_id"], challenge_id=challenge.id
                )
                .order_by(Submission.created_at.desc())
                .first(),
            }
        )

    return render_template(
        "student/lesson_detail.html", lesson=lesson, challenges_data=challenges_data
    )
