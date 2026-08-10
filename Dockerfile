FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/vendor

# Vendored pure-Python deps (no RUN/pip) so image builds succeed in
# restricted nested Podman/Buildah environments that cannot mount /proc.
COPY vendor/ /app/vendor/
COPY bot.py .

# Token is supplied at runtime: -e TELEGRAM_BOT_TOKEN=...
# Optional allow-list: -e TELEGRAM_ALLOWED_USER_ID=123,456
CMD ["python", "bot.py"]
