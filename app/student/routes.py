from flask import request, redirect, url_for, flash
from flask import Blueprint, render_template, session

from app import db
from app.decorators import student_required
from app.models import (
    Challenge,
    Submission,
    Lesson,
    User,
    Group,
    Question,
    QuestionSubmission,
)
from app.services import run_code_with_tests


student = Blueprint("student", __name__, template_folder="templates")


@student.before_request
@student_required
def before_request():
    pass


@student.route("/dashboard")
def dashboard():
    user = db.session.query(User).get(session["user_id"])
    group = db.session.query(Group).get(user.group_id) if user.group_id else None

    return render_template(
        "student/dashboard.html",
        group=group,
    )


@student.route("/challenge/<int:challenge_id>", methods=["GET", "POST"])
def challenge_detail(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)

    # Find the lesson this challenge belongs to
    lesson = None
    for l in challenge.lessons:  # Assuming challenges can belong to multiple lessons
        lesson = l
        break  # Take the first lesson found

    # check if student has access to this challenge
    student = User.query.get(session["user_id"])
    if not lesson or not lesson.visible:
        # Check if lesson is enabled for student's group
        if not student.group or lesson not in student.group.enabled_lessons:
            flash("You do not have access to this challenge", "error")
            return redirect(url_for("student.dashboard"))

    # Get navigation info for next/previous challenges within the lesson
    next_challenge = None
    previous_challenge = None
    current_index = None
    total_challenges = 0

    if lesson:
        lesson_challenges = list(lesson.challenges)
        total_challenges = len(lesson_challenges)

        for i, c in enumerate(lesson_challenges):
            if c.id == challenge_id:
                current_index = i
                break

        if current_index is not None:
            if current_index < len(lesson_challenges) - 1:
                next_challenge = lesson_challenges[current_index + 1]
            if current_index > 0:
                previous_challenge = lesson_challenges[current_index - 1]

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
        lesson=lesson,
        next_challenge=next_challenge,
        previous_challenge=previous_challenge,
        current_index=current_index,
        total_challenges=total_challenges,
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

    # Check if lesson is accessible to this student
    if not lesson.visible:
        # Check if lesson is enabled for student's group
        student = User.query.get(session["user_id"])
        if not student.group or lesson not in student.group.enabled_lessons:
            flash("You do not have access to this lesson", "error")
            return redirect(url_for("student.dashboard"))

    # Process challenges in the lesson
    challenges_data = []
    for challenge in lesson.challenges:
        # Check if user has completed this challenge
        user_submissions = (
            Submission.query.filter_by(
                user_id=session["user_id"], challenge_id=challenge.id
            )
            .order_by(Submission.created_at.desc())
            .all()
        )

        completed = any(sub.is_passing for sub in user_submissions)
        last_submission = user_submissions[0] if user_submissions else None

        challenges_data.append(
            {
                "challenge": challenge,
                "completed": completed,
                "last_submission": last_submission,
            }
        )

    # Process questions in the lesson
    questions_data = []
    for question in lesson.questions:
        # Check if user has completed this question
        user_submissions = (
            QuestionSubmission.query.filter_by(
                user_id=session["user_id"], question_id=question.id
            )
            .order_by(QuestionSubmission.created_at.desc())
            .all()
        )

        completed = any(sub.is_correct for sub in user_submissions)
        last_submission = user_submissions[0] if user_submissions else None

        questions_data.append(
            {
                "question": question,
                "completed": completed,
                "last_submission": last_submission,
            }
        )

    return render_template(
        "student/lesson_detail.html",
        lesson=lesson,
        challenges_data=challenges_data,
        questions_data=questions_data,
    )


@student.route("/question/<int:question_id>", methods=["GET", "POST"])
def view_question(question_id):
    question = Question.query.get_or_404(question_id)
    lesson_id = request.args.get("lesson_id")

    # Check if this question is accessible to the student
    if not lesson_id:
        flash("Invalid access to question", "error")
        return redirect(url_for("student.dashboard"))

    lesson = Lesson.query.get_or_404(lesson_id)
    student = User.query.get(session["user_id"])

    if not lesson.visible and lesson not in student.group.enabled_lessons:
        flash("You do not have access to this question", "error")
        return redirect(url_for("student.dashboard"))

    # Check if the question is part of this lesson
    if question not in lesson.questions:
        flash("Question not found in this lesson", "error")
        return redirect(url_for("student.view_lesson", lesson_id=lesson_id))

    # Get navigation info for next/previous questions
    lesson_questions = list(lesson.questions)  # Convert to list
    current_index = None
    for i, q in enumerate(lesson_questions):
        if q.id == question_id:
            current_index = i
            break

    next_question = None
    previous_question = None

    if current_index is not None:
        if current_index < len(lesson_questions) - 1:
            next_question = lesson_questions[current_index + 1]
        if current_index > 0:
            previous_question = lesson_questions[current_index - 1]

    # Check if student has already answered this question correctly
    existing_submission = QuestionSubmission.query.filter_by(
        user_id=session["user_id"], question_id=question_id, is_correct=True
    ).first()

    answered_correctly = existing_submission is not None

    # If already answered correctly, don't process new submissions
    if request.method == "POST" and not answered_correctly:
        # Process the submission
        selected_indices = request.form.getlist("selected_options")

        # Check if answer is correct
        is_correct = True
        for i, option in enumerate(question.options):
            str_i = str(i)
            if (option["is_correct"] and str_i not in selected_indices) or (
                not option["is_correct"] and str_i in selected_indices
            ):
                is_correct = False
                break

        # Create submission record
        submission = QuestionSubmission(
            user_id=session["user_id"],
            question_id=question_id,
            selected_options=selected_indices,
            is_correct=is_correct,
        )
        db.session.add(submission)
        db.session.commit()

        if is_correct:
            flash("Correct! Well done!", "success")
        else:
            flash("Sorry, that's not correct. Try again!", "error")

        # Refresh the page to show the result
        return redirect(
            url_for(
                "student.view_question", question_id=question_id, lesson_id=lesson_id
            )
        )

    return render_template(
        "student/question.html",
        question=question,
        lesson=lesson,
        answered_correctly=answered_correctly,
        correct_submission=existing_submission,
        next_question=next_question,
        previous_question=previous_question,
        current_index=current_index,
        total_questions=len(lesson_questions),
    )
