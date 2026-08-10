FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

# Token is supplied at runtime: -e TELEGRAM_BOT_TOKEN=...
# Optional allow-list: -e TELEGRAM_ALLOWED_USER_ID=123,456
CMD ["python", "bot.py"]
