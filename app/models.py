from sqlalchemy.sql import func
from werkzeug.security import generate_password_hash, check_password_hash

from app import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
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
