# prom-products.kz

Сайт-каталог «Батыс Курылыс XXI»: Django 5.2 + PostgreSQL 16.

## Локальный запуск

    cp .env.example .env
    docker compose -f compose.yml -f compose.dev.yml up -d db
    uv sync
    uv run python manage.py migrate
    uv run python manage.py createsuperuser
    uv run python manage.py runserver

Админка: http://localhost:8000/manage-dev/

## Тесты

    uv run pytest
    uv run ruff check .

## Деплой

См. `deploy/DEPLOY.md`.
