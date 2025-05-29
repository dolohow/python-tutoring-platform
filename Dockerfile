FROM python:3.13-slim


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/app/.local/bin:$PATH"

RUN apt update && apt install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libc6-dev \
 && apt purge -y --auto-remove \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1000 app && useradd --create-home --system -u 1000 --gid app app

WORKDIR /usr/src/app
USER app

COPY --chown=app:app requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app gunicorn.conf.py wsgi.py manage_sessions.py ./
COPY --chown=app:app app app
COPY --chown=app:app migrations migrations

CMD ["gunicorn"]
