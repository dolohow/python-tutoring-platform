from sqlalchemy.sql import func
from werkzeug.security import generate_password_hash, check_password_hash

from app import db


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    text = db.Column(db.Text, nullable=False)

    # Multiple choice options stored as JSON string
    # Format: [{"text": "Option text", "is_correct": true/false}, ...]
    options = db.Column(db.JSON, nullable=False)

    # Many-to-many relationship with Lesson (questions can be in multiple lessons)
    lessons = db.relationship(
        "Lesson",
        secondary="lesson_questions",
        backref=db.backref("questions", lazy="dynamic"),
    )
    # Foreign key to the user (tutor) who created the question
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User", backref=db.backref("questions", lazy=True))

    created_at = db.Column(db.DateTime, default=func.now())


lesson_questions = db.Table(
    "lesson_questions",
    db.Column("lesson_id", db.Integer, db.ForeignKey("lesson.id"), primary_key=True),
    db.Column(
        "question_id", db.Integer, db.ForeignKey("question.id"), primary_key=True
    ),
)


class QuestionSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    # Selected answers as JSON array of option indices
    selected_options = db.Column(db.JSON, nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=func.now())

    user = db.relationship(
        "User", backref=db.backref("question_submissions", lazy=True)
    )
    question = db.relationship("Question", backref=db.backref("submissions", lazy=True))


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())
    users = db.relationship("User", backref="group", lazy=True)
    enabled_lessons = db.relationship(
        "Lesson", secondary="group_lessons", backref="enabled_groups"
    )


group_lessons = db.Table(
    "group_lessons",
    db.Column("group_id", db.Integer, db.ForeignKey("group.id"), primary_key=True),
    db.Column("lesson_id", db.Integer, db.ForeignKey("lesson.id"), primary_key=True),
)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    first_name = db.Column(db.String(20), nullable=True)
    last_name = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="student")
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())
    last_login = db.Column(db.DateTime, nullable=True)

    submissions = db.relationship("Submission", backref="user", lazy=True)
    challenges = db.relationship("Challenge", backref="creator", lazy=True)
    lessons = db.relationship("Lesson", backref="creator", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_tutor(self):
        return self.role == "tutor"

    def is_student(self):
        return self.role == "student"


class Challenge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    initial_code = db.Column(db.Text, nullable=False)
    test_code = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    submissions = db.relationship("Submission", backref="challenge", lazy=True)


class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.Text, nullable=False)
    result = db.Column(db.Text, nullable=True)
    is_passing = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=func.now())
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenge.id"), nullable=False)


class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    visible = db.Column(db.Boolean, default=False)
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
