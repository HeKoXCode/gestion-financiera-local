FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/app:/app

RUN apt-get update \
    && apt-get install --no-install-recommends -y postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.in requirements-cloud.in requirements-cloud.lock ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements-cloud.lock

COPY app ./app
COPY launcher ./launcher
COPY scripts/docker-entrypoint.sh ./scripts/docker-entrypoint.sh
RUN chmod +x ./scripts/docker-entrypoint.sh \
    && useradd --create-home --uid 10001 gestion \
    && mkdir -p /data /backups /exports /media /app/staticfiles \
    && chown -R gestion:gestion /app /data /backups /exports /media

USER gestion
EXPOSE 8000
ENTRYPOINT ["./scripts/docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--chdir", "app", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "2", "--timeout", "60"]
