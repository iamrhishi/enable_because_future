FROM python:3.11-slim

# System libraries needed by opencv-python-headless, Pillow/rembg, and psycopg2 build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/logs /app/images \
    && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

# Cloud Run sets $PORT (defaults to 8080); gunicorn binds to it.
# --timeout 0 disables gunicorn's own worker timeout since Cloud Run enforces
# its own request timeout - avoids double-timeout surprises on slow try-on calls.
CMD exec gunicorn --bind :${PORT:-8080} --workers 2 --threads 8 --timeout 0 app:app
