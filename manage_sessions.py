#!/usr/bin/env python
import sys
from app import app, db, User
import uuid


def invalidate_all_sessions():
    with app.app_context():
        students = db.session.query(User).filter(User.role == "student").all()
        for student in students:
            student.session_id = str(uuid.uuid4())
        db.session.commit()
        print("Successfully invalidated user sessions")


def list_sessions():
    with app.app_context():
        students = db.session.query(User).filter(User.role == "student").all()
        print(f"{'Email':<40} {'Last Login':<20} {'Session ID':<40}")
        print("-" * 100)
        for student in students:
            last_login = (
                student.last_login.strftime("%Y-%m-%d %H:%M:%S")
                if student.last_login
                else "Never"
            )
            print(f"{student.email:<40} {last_login:<20} {student.session_id}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python manage_sessions.py clear        # Invalidate all sessions")
        print("  python manage_sessions.py list         # List all active sessions")
        sys.exit(1)

    target = sys.argv[1]
    if target.lower() == "clear":
        invalidate_all_sessions()
    elif target.lower() == "list":
        list_sessions()
