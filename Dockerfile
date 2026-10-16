FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 1000 ltl \
    && mkdir -p /app/data \
    && chown -R ltl:ltl /app/data
USER ltl

VOLUME ["/app/data"]

CMD ["python", "main.py"]
