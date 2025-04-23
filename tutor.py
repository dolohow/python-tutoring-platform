from app import db, Tutor, app


def create_tutor(name, email):
    with app.app_context():
        # Check if tutor already exists
        existing_tutor = Tutor.query.filter_by(email=email).first()
        if existing_tutor:
            print(f"Tutor with email {email} already exists.")
            return

        # Create new tutor
        new_tutor = Tutor(name=name, email=email)
        db.session.add(new_tutor)
        db.session.commit()
        print(f"Tutor '{name}' created successfully with email '{email}'")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python setup_tutor.py <tutor_name> <tutor_email>")
        sys.exit(1)

    name = sys.argv[1]
    email = sys.argv[2]

    create_tutor(name, email)
