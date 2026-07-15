FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

RUN addgroup --system eidolon \
    && adduser --system --ingroup eidolon --home /nonexistent --no-create-home eidolon

COPY pyproject.toml alembic.ini ./
COPY alembic ./alembic
COPY app ./app

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

USER eidolon

EXPOSE 8080

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT}\" --proxy-headers --forwarded-allow-ips='*'"]
