# Use official slim Python image
FROM python:3.11-slim

# Metadata
LABEL org.opencontainers.image.source="."

# Environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_VIRTUALENVS_CREATE=false

# Install system dependencies required to build some Python packages (e.g. psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies. Expect a requirements.txt at the project root.
# If you use poetry or pipenv adapt these steps accordingly.
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
  && pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY . /app

# Copy entrypoint that creates tables and then starts the app
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Create a non-root user and give ownership of the app folder
RUN groupadd -r app && useradd -r -g app app \
  && chown -R app:app /app

USER app

# FastAPI default port
EXPOSE 8002

# Start via entrypoint which runs create_tables.py then uvicorn
ENTRYPOINT ["/app/entrypoint.sh"]