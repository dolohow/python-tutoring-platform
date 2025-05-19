import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "default-key")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    EMAIL_DOMAIN = os.getenv("EMAIL_DOMAIN", "gmail.com")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///dev.db")
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
