FROM python:3.13-slim

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd app \
    && useradd --create-home -g app app

USER app
ENV PATH="/home/app/.local/bin:$PATH"

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY gunicorn.conf.py wsgi.py manage_sessions.py .
COPY app app

CMD ["gunicorn"]
