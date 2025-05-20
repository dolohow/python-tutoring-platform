import os

from app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(debug=os.getenv("DEBUG", "false").lower() == "true", host="0.0.0.0")
