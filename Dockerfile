FROM python:3.12-slim

ARG UV_VERSION=0.12.15
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir "uv==${UV_VERSION}"

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .
RUN DEBUG=False SECRET_KEY=build-only-not-secret DATABASE_URL=sqlite:////tmp/build.sqlite3 \
    python manage.py collectstatic --noinput

RUN useradd --system --uid 1000 --home-dir /app app \
    && mkdir -p /app/media /app/.gunicorn \
    && chown app /app/media /app/.gunicorn
USER app

EXPOSE 8000
ENTRYPOINT ["sh", "/app/deploy/entrypoint.sh"]
