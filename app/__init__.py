import markdown

from flask import Flask
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def create_app():
    app = Flask(__name__)

    from .config import Config

    app.config.from_object(Config)

    db.init_app(app)

    @app.template_filter("markdown")
    def markdown_filter(text):
        return markdown.markdown(text)

    from .auth.routes import auth
    from .tutor.routes import tutor
    from .student.routes import student

    app.register_blueprint(auth)
    app.register_blueprint(student, url_prefix="/student")
    app.register_blueprint(tutor, url_prefix="/tutor")

    with app.app_context():
        db.create_all()

    return app
