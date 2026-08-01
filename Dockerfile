FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot
COPY assets ./assets
RUN mkdir -p data

ENV PYTHONPATH=/app

CMD ["python3", "-m", "bot.main"]
