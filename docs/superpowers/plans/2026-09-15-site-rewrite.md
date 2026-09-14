# Переписывание prom-products.kz на Django — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить старый FastAPI + React сайт на Django-монолит с SEO-страницами, корзиной-запросом, админкой и переписанным контентом.

**Architecture:** Один Django-проект (`config/`) с двумя приложениями: `catalog` (категории, товары, фото, редиректы, настройки сайта, публичные страницы, SEO) и `orders` (заявки, форма, email). Шаблоны рендерятся на сервере, корзина — один файл `static/js/cart.js` на `localStorage`. Контент загружается командой `import_catalog` из `content/catalog.yaml`. Деплой — Docker Compose (Postgres 16 + gunicorn) за существующим Caddy.

**Tech Stack:** Python 3.12, Django 5.2, PostgreSQL 16 (psycopg 3), django-environ, whitenoise, Pillow, nh3, django-axes, django-prose-editor, PyYAML, gunicorn; dev: uv, pytest, pytest-django, beautifulsoup4, ruff.

**Spec:** `docs/superpowers/specs/2026-09-14-site-rewrite-design.md`

## Global Constraints

- Язык сайта и админки — только русский (`LANGUAGE_CODE = "ru"`), часовой пояс `Asia/Almaty`.
- URL — английские slug: `/catalog/<category>/`, `/catalog/<category>/<product>/`, `/quote/`, `/quote/thanks/`, `/contacts/`, `/sitemap.xml`, `/robots.txt`.
- Название компании в интерфейсе и `<title>`: «Батыс Курылыс XXI».
- Производитель (ИНСТАН / INSTAN) нигде не упоминается: ни в текстах, ни в названиях, ни в разметке; поле `brand` в JSON-LD не выводится.
- Цена показывается (на странице и в JSON-LD `offers`) только если `show_price=True` и `price` не пустая. Валюта — KZT.
- HTML из админки и контента проходит `catalog.sanitize.sanitize_html`; allowlist тегов: `p, br, strong, em, ul, ol, li, h2, h3, h4, a, table, thead, tbody, tr, th, td`; атрибуты — только `href` у `a`, схемы `http, https, tel, mailto`.
- Заявка: имя 2–100 символов; телефон нормализуется в `+7XXXXXXXXXX`; позиций 1–50; количество 1–999; не более 5 заявок в час с одного IP; honeypot-поле `website`.
- Письмо о заявке отправляется через `transaction.on_commit`, SMTP-таймаут 10 с; сбой не теряет заявку, `email_sent` остаётся `False`.
- Админка по адресу из env `ADMIN_URL` (не `admin/`); `django-axes`: 5 неудачных попыток → блокировка на 30 минут.
- Никаких seed-скриптов при старте контейнера.
- Числа в характеристиках и текстах товаров — только из исходных данных `legacy/products.json`; ничего не придумывать.
- Секреты только в `.env`; `.env` и `media/` не коммитятся.
- Все shell-скрипты с окончаниями строк LF (`.gitattributes`).
- В тестах логин в админку только через `client.force_login(user)` — `client.login()` не работает с `django-axes`.

## Локальное окружение (прочитать перед Task 1)

- Разработка идёт на Windows в ветке `rewrite` репозитория `C:\Users\Turar\Desktop\promproduct`. Команды ниже — для Git Bash; в PowerShell они такие же, кроме `cp` → `Copy-Item`.
- Нужны: Docker Desktop (для Postgres) и `uv` (`pip install uv`, если `uv --version` не работает).
- Postgres для разработки и тестов: `docker compose -f compose.yml -f compose.dev.yml up -d db` (порт `127.0.0.1:5433`). До Task 19 файл `compose.yml` содержит только сервис `db`.
- Тесты: `uv run pytest`. Линтер: `uv run ruff check .`.

## Структура файлов

```
.gitattributes, .gitignore, .env.example, README.md
pyproject.toml, uv.lock
manage.py
compose.yml                         db (+ web в Task 19)
compose.dev.yml                     проброс порта Postgres для разработки
Dockerfile                          Task 19
config/__init__.py, settings.py, urls.py, wsgi.py
catalog/
  __init__.py, apps.py
  paths.py                          category_path(), product_path()
  sanitize.py                       sanitize_html()
  images.py                         to_webp()
  models.py                         Category, Product, ProductSpec, ProductImage, Redirect, SiteSettings
  middleware.py                     RedirectFallbackMiddleware
  context_processors.py             site()
  roles.py                          ensure_manager_group()
  forms.py                          CategoryAdminForm, ProductAdminForm
  admin.py
  seo.py                            заголовки, описания, JSON-LD
  templatetags/__init__.py, seo_tags.py   {% ld_json %}
  views.py, urls.py, sitemaps.py
  management/__init__.py
  management/commands/__init__.py, import_catalog.py
  migrations/
orders/
  __init__.py, apps.py
  models.py                         QuoteRequest, QuoteItem
  services.py                       normalize_phone(), parse_items(), create_quote()
  notifications.py                  send_quote_notification()
  forms.py                          QuoteForm
  views.py, urls.py, admin.py
  management/__init__.py
  management/commands/__init__.py, import_legacy_requests.py
  migrations/
templates/
  base.html, 404.html
  includes/product_card.html, includes/breadcrumbs.html
  catalog/home.html, catalog/index.html, catalog/category.html, catalog/product.html, catalog/contacts.html
  orders/quote.html, orders/thanks.html
static/css/site.css
static/js/cart.js
scripts/fetch_legacy.py             скачивает legacy/*.json
scripts/prepare_catalog.py          legacy → content/catalog.draft.yaml + content/images/
legacy/categories.json, legacy/products.json
content/catalog.draft.yaml          черновик (генерируется)
content/catalog.yaml                итоговый контент
content/images/<product-slug>/N.webp
docs/design/mockup.html             макет для согласования
deploy/entrypoint.sh, deploy/backup.sh, deploy/Caddyfile.example, deploy/DEPLOY.md
tests/conftest.py, tests/factories.py, tests/test_*.py
```

---

### Task 1: Скелет проекта

Удаляет старый код и создаёт пустой Django-проект, который проходит `manage.py check` и тесты.

**Files:**
- Delete: `main.py`, `db.py`, `models_db.py`, `schemas.py`, `create_tables.py`, `emailtest.py`, `ddl.sql`, `entrypoint.sh`, `Dockerfile`, `docker-compose.yml`, `DOCKER.md`, `README.md`, `dev-requirements.txt`, `requirements.txt`, `pyproject.toml`, `frontend/`
- Create: `pyproject.toml`, `.gitignore`, `.gitattributes`, `.env.example`, `README.md`, `manage.py`, `config/__init__.py`, `config/settings.py`, `config/urls.py`, `config/wsgi.py`, `catalog/__init__.py`, `catalog/apps.py`, `catalog/migrations/__init__.py`, `orders/__init__.py`, `orders/apps.py`, `orders/migrations/__init__.py`, `compose.yml`, `compose.dev.yml`, `tests/__init__.py`, `tests/conftest.py`
- Test: `tests/test_project.py`

**Interfaces:**
- Produces: настройки `settings.SITE_URL` (str без завершающего `/`), `settings.ADMIN_URL` (str с завершающим `/`), `settings.ADMIN_EMAIL` (str); приложения `catalog`, `orders`; фикстура `media_root` (autouse) в `tests/conftest.py`.

- [ ] **Step 1: Удалить старый код**

```bash
git rm -r -q main.py db.py models_db.py schemas.py create_tables.py emailtest.py ddl.sql entrypoint.sh Dockerfile docker-compose.yml DOCKER.md README.md dev-requirements.txt requirements.txt pyproject.toml frontend
git status --short | head
```
Expected: только строки `D ...`.

- [ ] **Step 2: Создать `pyproject.toml`**

```toml
[project]
name = "promproduct"
version = "2.0.0"
requires-python = ">=3.12"
dependencies = [
    "django>=5.2,<5.3",
    "psycopg[binary]>=3.2",
    "django-environ>=0.12",
    "gunicorn>=23",
    "whitenoise>=6.9",
    "pillow>=11",
    "nh3>=0.2.20",
    "django-axes>=8",
    "django-prose-editor>=0.15",
    "pyyaml>=6",
]

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-django>=4.9",
    "beautifulsoup4>=4.12",
    "ruff>=0.8",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings"
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-q"

[tool.ruff]
line-length = 110
target-version = "py312"
extend-exclude = ["*/migrations/*"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "DJ"]
```

- [ ] **Step 3: Создать `.gitignore` и `.gitattributes`**

`.gitignore`:
```gitignore
.env
.venv/
__pycache__/
*.pyc
media/
staticfiles/
node_modules/
.pytest_cache/
.ruff_cache/
*.sql
*.dump
```

`.gitattributes`:
```gitattributes
* text=auto
*.sh text eol=lf
deploy/entrypoint.sh text eol=lf
*.webp binary
*.png binary
*.jpg binary
```

- [ ] **Step 4: Создать `.env.example` и локальный `.env`**

`.env.example`:
```dotenv
# --- Django ---
DEBUG=True
SECRET_KEY=change-me-to-a-long-random-string-at-least-50-characters-long
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000
SITE_URL=http://localhost:8000
ADMIN_URL=manage-dev/

# --- Database ---
POSTGRES_DB=promproduct
POSTGRES_USER=promproduct
POSTGRES_PASSWORD=promproduct
# локально (compose.dev.yml пробрасывает 5433); на сервере: postgres://promproduct:<пароль>@db:5432/promproduct
DATABASE_URL=postgres://promproduct:promproduct@127.0.0.1:5433/promproduct

# --- Cache (на сервере: django.core.cache.backends.db.DatabaseCache / django_cache) ---
CACHE_BACKEND=django.core.cache.backends.locmem.LocMemCache
CACHE_LOCATION=promproduct

# --- Email ---
# локально письма печатаются в консоль. На сервере для Gmail (пароль приложения, пробелы убрать, @ → %40):
# EMAIL_URL=submission://user%40gmail.com:apppassword@smtp.gmail.com:587
EMAIL_URL=consolemail://
DEFAULT_FROM_EMAIL=webmaster@localhost
ADMIN_EMAIL=admin@example.com

# --- Media ---
MEDIA_ROOT=media

# --- Docker (сервер) ---
WEB_PORT=8001
```

```bash
cp .env.example .env
```

- [ ] **Step 5: Создать `manage.py` и пакет `config`**

`manage.py`:
```python
#!/usr/bin/env python
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

`config/__init__.py`: пустой файл.

`config/wsgi.py`:
```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()
```

`config/settings.py`:
```python
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
if (BASE_DIR / ".env").exists():
    environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
SITE_URL = env("SITE_URL", default="http://localhost:8000").rstrip("/")
ADMIN_URL = env("ADMIN_URL", default="manage-dev/").strip("/") + "/"
ADMIN_EMAIL = env("ADMIN_EMAIL", default="")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "axes",
    "django_prose_editor",
    "catalog",
    "orders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL")}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {
    "default": {
        "BACKEND": env("CACHE_BACKEND", default="django.core.cache.backends.locmem.LocMemCache"),
        "LOCATION": env("CACHE_LOCATION", default="promproduct"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru"
TIME_ZONE = "Asia/Almaty"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "media")))
if not MEDIA_ROOT.is_absolute():
    MEDIA_ROOT = BASE_DIR / MEDIA_ROOT

vars().update(env.email_url("EMAIL_URL", default="consolemail://"))
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="webmaster@localhost")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# django-axes
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=30)
AXES_RESET_ON_SUCCESS = True
# Caddy перезаписывает X-Forwarded-For для недоверенных клиентов, поэтому первое значение — реальный IP
AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"]

# Security (HTTPS терминирует Caddy)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SILENCED_SYSTEM_CHECKS = [
    "security.W008",  # редирект на HTTPS делает Caddy
    "security.W005",  # HSTS без includeSubDomains: new.prom-products.kz — отдельный стенд
    "security.W021",  # HSTS preload сознательно не включаем
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
```

`config/urls.py`:
```python
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

- [ ] **Step 6: Создать приложения `catalog` и `orders`**

`catalog/__init__.py`, `catalog/migrations/__init__.py`, `orders/__init__.py`, `orders/migrations/__init__.py`: пустые файлы.

`catalog/apps.py`:
```python
from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"
    verbose_name = "Каталог"
```

`orders/apps.py`:
```python
from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orders"
    verbose_name = "Заявки"
```

Создать пустые каталоги статики и шаблонов, чтобы `STATICFILES_DIRS` существовал:
```bash
mkdir -p static/css static/js templates && touch static/.gitkeep templates/.gitkeep
```

- [ ] **Step 7: Создать compose-файлы для Postgres**

`compose.yml`:
```yaml
services:
  db:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-promproduct}
      POSTGRES_USER: ${POSTGRES_USER:-promproduct}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in .env}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      retries: 10

volumes:
  pgdata:
```

`compose.dev.yml`:
```yaml
services:
  db:
    ports:
      - "127.0.0.1:5433:5432"
```

```bash
docker compose -f compose.yml -f compose.dev.yml up -d db
```
Expected: контейнер `db` в статусе `healthy` (`docker compose ps`).

- [ ] **Step 8: Установить зависимости**

```bash
uv sync
```
Expected: создан `uv.lock` и `.venv`.

- [ ] **Step 9: Написать тест проекта**

`tests/__init__.py`: пустой файл.

`tests/conftest.py`:
```python
import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()
```

`tests/test_project.py`:
```python
import pytest
from django.conf import settings
from django.core.management import call_command


def test_system_check_passes():
    call_command("check")


def test_admin_url_is_not_default():
    assert settings.ADMIN_URL != "admin/"
    assert settings.ADMIN_URL.endswith("/")


@pytest.mark.django_db
def test_default_admin_path_is_404(client):
    assert client.get("/admin/").status_code == 404


def test_site_language_is_russian():
    assert settings.LANGUAGE_CODE == "ru"
```

- [ ] **Step 10: Запустить тесты**

```bash
uv run pytest
uv run ruff check .
```
Expected: `4 passed`; ruff без ошибок. Если падает `test_system_check_passes` на `django_prose_editor` или `axes` — проверить, что `uv sync` прошёл без ошибок.

- [ ] **Step 11: Написать `README.md`**

```markdown
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
```

- [ ] **Step 12: Commit**

```bash
git add -A
git commit -m "chore: replace legacy FastAPI/React code with Django project skeleton"
```

### Task 2: Очистка HTML

**Files:**
- Create: `catalog/sanitize.py`
- Test: `tests/test_sanitize.py`

**Interfaces:**
- Produces: `catalog.sanitize.sanitize_html(value: str | None) -> str`; константа `catalog.sanitize.ALLOWED_TAGS: set[str]`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_sanitize.py`:
```python
from catalog.sanitize import ALLOWED_TAGS, sanitize_html


def test_empty_values_return_empty_string():
    assert sanitize_html(None) == ""
    assert sanitize_html("") == ""


def test_script_and_style_removed_with_content():
    result = sanitize_html("<script>alert(1)</script><style>p{}</style><p>ok</p>")
    assert result == "<p>ok</p>"


def test_style_and_class_attributes_removed():
    assert sanitize_html('<p style="color:red" class="x">text</p>') == "<p>text</p>"


def test_font_tag_unwrapped_keeping_text():
    assert sanitize_html('<p><font color="red">text</font></p>') == "<p>text</p>"


def test_img_removed():
    assert sanitize_html('<p>a<img src="x.jpg" onerror="alert(1)">b</p>') == "<p>ab</p>"


def test_javascript_links_lose_href():
    result = sanitize_html('<a href="javascript:alert(1)">x</a>')
    assert "javascript" not in result
    assert ">x</a>" in result


def test_allowed_link_keeps_href_and_gets_rel():
    result = sanitize_html('<a href="https://prom-products.kz/" target="_blank">site</a>')
    assert 'href="https://prom-products.kz/"' in result
    assert 'rel="noopener noreferrer"' in result
    assert "target" not in result


def test_tables_and_lists_kept():
    html = "<table><thead><tr><th>A</th></tr></thead><tbody><tr><td>1</td></tr></tbody></table><ul><li>x</li></ul>"
    assert sanitize_html(html) == html


def test_allowed_tags_match_spec():
    assert ALLOWED_TAGS == {
        "p", "br", "strong", "em", "ul", "ol", "li", "h2", "h3", "h4",
        "a", "table", "thead", "tbody", "tr", "th", "td",
    }
```

- [ ] **Step 2: Запустить — должны упасть**

Run: `uv run pytest tests/test_sanitize.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'catalog.sanitize'`.

- [ ] **Step 3: Реализация**

`catalog/sanitize.py`:
```python
import nh3

ALLOWED_TAGS = {
    "p", "br", "strong", "em", "ul", "ol", "li", "h2", "h3", "h4",
    "a", "table", "thead", "tbody", "tr", "th", "td",
}
ALLOWED_ATTRIBUTES = {"a": {"href"}}
URL_SCHEMES = {"http", "https", "tel", "mailto"}


def sanitize_html(value: str | None) -> str:
    """Оставляет только безопасное подмножество HTML для описаний и SEO-текстов."""
    if not value:
        return ""
    return nh3.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=URL_SCHEMES,
        link_rel="noopener noreferrer",
    ).strip()
```

- [ ] **Step 4: Запустить — должны пройти**

Run: `uv run pytest tests/test_sanitize.py`
Expected: `9 passed`.

- [ ] **Step 5: Commit**

```bash
git add catalog/sanitize.py tests/test_sanitize.py
git commit -m "feat(catalog): add HTML sanitizer with spec allowlist"
```

---

### Task 3: Модели каталога и редиректы

**Files:**
- Create: `catalog/paths.py`, `catalog/models.py`, `catalog/middleware.py`, `tests/factories.py`
- Create (generated): `catalog/migrations/0001_initial.py`
- Modify: `config/settings.py` (список `MIDDLEWARE`)
- Test: `tests/test_catalog_models.py`

**Interfaces:**
- Consumes: `catalog.sanitize.sanitize_html`.
- Produces:
  - `catalog.paths.category_path(slug: str) -> str` → `"/catalog/<slug>/"`; `catalog.paths.product_path(category_slug: str, slug: str) -> str` → `"/catalog/<category_slug>/<slug>/"`.
  - Модели `Category(name, slug, seo_text, meta_title, meta_description, sort_order, is_active)`, related name `products`; `Category.get_absolute_url() -> str`.
  - `Product(category, name, slug, model_code, short_description, description, price: Decimal|None, show_price, is_active, sort_order, meta_title, meta_description, created_at, updated_at)`; `Product.get_absolute_url() -> str`; свойство `Product.displayed_price -> Decimal | None`; related names `specs`, `images` (images — в Task 4).
  - `ProductSpec(product, name, value, sort_order)`.
  - `Redirect(old_path, new_path)`; `Redirect.record(old_path: str, new_path: str) -> None`.
  - `catalog.middleware.RedirectFallbackMiddleware`.
  - `tests.factories.make_category(**kwargs) -> Category`, `tests.factories.make_product(category: Category | None = None, **kwargs) -> Product`.

- [ ] **Step 1: Фабрики для тестов**

`tests/factories.py`:
```python
from itertools import count

from catalog.models import Category, Product

_seq = count(1)


def make_category(**kwargs) -> Category:
    n = next(_seq)
    data = {"name": f"Категория {n}", "slug": f"category-{n}"}
    data.update(kwargs)
    return Category.objects.create(**data)


def make_product(category: Category | None = None, **kwargs) -> Product:
    n = next(_seq)
    data = {
        "category": category or make_category(),
        "name": f"Трубогиб ТПГ-{n}",
        "slug": f"tpg-{n}",
    }
    data.update(kwargs)
    return Product.objects.create(**data)
```

- [ ] **Step 2: Написать падающие тесты**

`tests/test_catalog_models.py`:
```python
from decimal import Decimal

import pytest
from django.db import IntegrityError

from catalog.models import Redirect
from tests.factories import make_category, make_product

pytestmark = pytest.mark.django_db


def test_absolute_urls():
    category = make_category(slug="pipe-benders")
    product = make_product(category=category, slug="tpg-2b")
    assert category.get_absolute_url() == "/catalog/pipe-benders/"
    assert product.get_absolute_url() == "/catalog/pipe-benders/tpg-2b/"


def test_html_fields_sanitized_on_save():
    category = make_category(seo_text='<p style="x">a</p><script>x</script>')
    product = make_product(description='<p><font>b</font></p><img src="x">')
    category.refresh_from_db()
    product.refresh_from_db()
    assert category.seo_text == "<p>a</p>"
    assert product.description == "<p>b</p>"


def test_slug_is_unique():
    make_product(slug="same")
    with pytest.raises(IntegrityError):
        make_product(slug="same")


@pytest.mark.parametrize(
    ("price", "show_price", "expected"),
    [
        (Decimal("150000"), False, None),
        (Decimal("150000"), True, Decimal("150000")),
        (None, True, None),
    ],
)
def test_displayed_price(price, show_price, expected):
    product = make_product(price=price, show_price=show_price)
    assert product.displayed_price == expected


def test_changing_product_slug_creates_redirect():
    category = make_category(slug="jacks")
    product = make_product(category=category, slug="old")
    product.slug = "new"
    product.save()
    assert Redirect.objects.get(old_path="/catalog/jacks/old/").new_path == "/catalog/jacks/new/"


def test_changing_product_category_creates_redirect():
    first = make_category(slug="first")
    second = make_category(slug="second")
    product = make_product(category=first, slug="item")
    product.category = second
    product.save()
    assert Redirect.objects.get(old_path="/catalog/first/item/").new_path == "/catalog/second/item/"


def test_saving_without_slug_change_creates_no_redirect():
    product = make_product()
    product.name = "Другое название"
    product.save()
    assert Redirect.objects.count() == 0


def test_changing_category_slug_redirects_category_and_products():
    category = make_category(slug="old-cat")
    make_product(category=category, slug="p1")
    category.slug = "new-cat"
    category.save()
    assert Redirect.objects.get(old_path="/catalog/old-cat/").new_path == "/catalog/new-cat/"
    assert Redirect.objects.get(old_path="/catalog/old-cat/p1/").new_path == "/catalog/new-cat/p1/"


def test_redirect_chains_are_collapsed():
    Redirect.record("/a/", "/b/")
    Redirect.record("/b/", "/c/")
    assert Redirect.objects.get(old_path="/a/").new_path == "/c/"
    assert Redirect.objects.get(old_path="/b/").new_path == "/c/"


def test_moving_back_removes_loop():
    Redirect.record("/a/", "/b/")
    Redirect.record("/b/", "/a/")
    assert not Redirect.objects.filter(old_path="/a/").exists()
    assert Redirect.objects.get(old_path="/b/").new_path == "/a/"


def test_middleware_redirects_known_old_path(client):
    Redirect.record("/catalog/old/", "/catalog/new/")
    response = client.get("/catalog/old/")
    assert response.status_code == 301
    assert response["Location"] == "/catalog/new/"


def test_middleware_keeps_unknown_404(client):
    assert client.get("/catalog/unknown/").status_code == 404
```

- [ ] **Step 3: Запустить — должны упасть**

Run: `uv run pytest tests/test_catalog_models.py`
Expected: FAIL, `ImportError: cannot import name 'Redirect' from 'catalog.models'`.

- [ ] **Step 4: Реализация путей**

`catalog/paths.py`:
```python
def category_path(slug: str) -> str:
    return f"/catalog/{slug}/"


def product_path(category_slug: str, slug: str) -> str:
    return f"/catalog/{category_slug}/{slug}/"
```

- [ ] **Step 5: Реализация моделей**

`catalog/models.py`:
```python
from decimal import Decimal

from django.db import models

from catalog.paths import category_path, product_path
from catalog.sanitize import sanitize_html


class Redirect(models.Model):
    old_path = models.CharField("Старый путь", max_length=300, unique=True)
    new_path = models.CharField("Новый путь", max_length=300)

    class Meta:
        verbose_name = "редирект"
        verbose_name_plural = "редиректы"
        ordering = ["old_path"]

    def __str__(self) -> str:
        return f"{self.old_path} → {self.new_path}"

    @classmethod
    def record(cls, old_path: str, new_path: str) -> None:
        if old_path == new_path:
            return
        cls.objects.filter(new_path=old_path).update(new_path=new_path)
        cls.objects.filter(old_path=new_path).delete()
        cls.objects.update_or_create(old_path=old_path, defaults={"new_path": new_path})


class Category(models.Model):
    name = models.CharField("Название", max_length=200)
    slug = models.SlugField("Slug", max_length=100, unique=True)
    seo_text = models.TextField("SEO-текст", blank=True)
    meta_title = models.CharField("Meta title", max_length=70, blank=True, help_text="До 60 символов.")
    meta_description = models.CharField(
        "Meta description", max_length=200, blank=True, help_text="До 160 символов."
    )
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "категория"
        verbose_name_plural = "категории"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return category_path(self.slug)

    def save(self, *args, **kwargs) -> None:
        self.seo_text = sanitize_html(self.seo_text)
        old_slug = None
        if self.pk:
            old_slug = type(self).objects.filter(pk=self.pk).values_list("slug", flat=True).first()
        super().save(*args, **kwargs)
        if old_slug and old_slug != self.slug:
            Redirect.record(category_path(old_slug), category_path(self.slug))
            for product_slug in self.products.values_list("slug", flat=True):
                Redirect.record(product_path(old_slug, product_slug), product_path(self.slug, product_slug))


class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products", verbose_name="Категория"
    )
    name = models.CharField("Название", max_length=255)
    slug = models.SlugField("Slug", max_length=100, unique=True)
    model_code = models.CharField("Модель", max_length=100, blank=True)
    short_description = models.CharField("Краткое описание", max_length=300, blank=True)
    description = models.TextField("Описание", blank=True)
    price = models.DecimalField("Цена, ₸", max_digits=12, decimal_places=0, null=True, blank=True)
    show_price = models.BooleanField("Показывать цену", default=False)
    is_active = models.BooleanField("Активен", default=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    meta_title = models.CharField("Meta title", max_length=70, blank=True, help_text="До 60 символов.")
    meta_description = models.CharField(
        "Meta description", max_length=200, blank=True, help_text="До 160 символов."
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Изменён", auto_now=True)

    class Meta:
        verbose_name = "товар"
        verbose_name_plural = "товары"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return product_path(self.category.slug, self.slug)

    @property
    def displayed_price(self) -> Decimal | None:
        if self.show_price and self.price is not None:
            return self.price
        return None

    def save(self, *args, **kwargs) -> None:
        self.description = sanitize_html(self.description)
        old_path = None
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values_list("slug", "category__slug").first()
            if old:
                old_path = product_path(old[1], old[0])
        super().save(*args, **kwargs)
        new_path = self.get_absolute_url()
        if old_path and old_path != new_path:
            Redirect.record(old_path, new_path)


class ProductSpec(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="specs")
    name = models.CharField("Характеристика", max_length=200)
    value = models.CharField("Значение", max_length=300)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "характеристика"
        verbose_name_plural = "характеристики"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return f"{self.name}: {self.value}"
```

- [ ] **Step 6: Middleware редиректов**

`catalog/middleware.py`:
```python
from django.http import HttpResponsePermanentRedirect

from catalog.models import Redirect


class RedirectFallbackMiddleware:
    """Для 404-ответов ищет путь в таблице Redirect и отдаёт 301."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code != 404:
            return response
        target = Redirect.objects.filter(old_path=request.path).values_list("new_path", flat=True).first()
        if target:
            return HttpResponsePermanentRedirect(target)
        return response
```

В `config/settings.py` заменить список `MIDDLEWARE` целиком:
```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "catalog.middleware.RedirectFallbackMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]
```

- [ ] **Step 7: Миграция**

```bash
uv run python manage.py makemigrations catalog
```
Expected: `catalog/migrations/0001_initial.py` с моделями Category, Product, ProductSpec, Redirect.

- [ ] **Step 8: Запустить тесты**

Run: `uv run pytest tests/test_catalog_models.py`
Expected: `14 passed`.

- [ ] **Step 9: Commit**

```bash
git add catalog tests/factories.py tests/test_catalog_models.py config/settings.py
git commit -m "feat(catalog): add category, product, spec and redirect models"
```

---
### Task 4: Фото товаров и настройки сайта

**Files:**
- Create: `catalog/images.py`, `catalog/context_processors.py`
- Modify: `catalog/models.py` (добавить `ProductImage`, `SiteSettings`, сигнал удаления файлов), `config/settings.py` (context processor)
- Create (generated): `catalog/migrations/0002_*.py`
- Test: `tests/test_images_and_settings.py`

**Interfaces:**
- Consumes: `Product` из Task 3.
- Produces:
  - `catalog.images.to_webp(file) -> tuple[ContentFile, ContentFile]` — (полное ≤1600 px, миниатюра ≤400 px), формат WebP.
  - `ProductImage(product, image, thumbnail, alt, sort_order)`, related name `images`, порядок `sort_order, id`.
  - Свойство `Product.main_image -> ProductImage | None` (использует `images.all()`, совместимо с `prefetch_related("images")`).
  - `SiteSettings` (одна запись, pk=1): поля `company_name, address, phones, whatsapp_numbers, notification_email, public_email, working_hours, bin, map_url`; `SiteSettings.load() -> SiteSettings`; свойства `phone_list -> list[str]`, `whatsapp_list -> list[dict]` с ключами `display` (как введено) и `wa` (только цифры).
  - Контекст шаблонов: `site` (SiteSettings), `site_url` (str), `nav_categories` (QuerySet активных категорий).

- [ ] **Step 1: Написать падающие тесты**

`tests/test_images_and_settings.py`:
```python
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from PIL import Image

from catalog.context_processors import site
from catalog.models import ProductImage, SiteSettings
from tests.factories import make_category, make_product

pytestmark = pytest.mark.django_db


def png_upload(width: int = 3000, height: int = 1000, mode: str = "RGB") -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new(mode, (width, height), "orange").save(buffer, "PNG")
    return SimpleUploadedFile("photo.png", buffer.getvalue(), content_type="image/png")


def test_uploaded_image_converted_to_webp_with_thumbnail():
    product = make_product(slug="tpg-2b")
    image = ProductImage.objects.create(product=product, image=png_upload())
    assert image.image.name.startswith("products/tpg-2b/")
    assert image.image.name.endswith(".webp")
    with Image.open(image.image.path) as full:
        assert full.format == "WEBP"
        assert full.size == (1600, 533)
    with Image.open(image.thumbnail.path) as thumb:
        assert thumb.format == "WEBP"
        assert thumb.size == (400, 133)


def test_small_image_not_upscaled_and_transparency_supported():
    product = make_product()
    image = ProductImage.objects.create(product=product, image=png_upload(300, 200, "RGBA"))
    with Image.open(image.image.path) as full:
        assert full.size == (300, 200)


def test_alt_defaults_to_product_name():
    product = make_product(name="Домкрат ДА5")
    image = ProductImage.objects.create(product=product, image=png_upload(100, 100))
    assert image.alt == "Домкрат ДА5"


def test_main_image_is_first_by_sort_order():
    product = make_product()
    second = ProductImage.objects.create(product=product, image=png_upload(100, 100), sort_order=2)
    first = ProductImage.objects.create(product=product, image=png_upload(100, 100), sort_order=1)
    assert product.main_image == first
    assert second != first


def test_main_image_none_without_images():
    assert make_product().main_image is None


def test_deleting_image_removes_files():
    product = make_product()
    image = ProductImage.objects.create(product=product, image=png_upload(100, 100))
    full_path, thumb_path = image.image.path, image.thumbnail.path
    ProductImage.objects.filter(pk=image.pk).delete()
    import os

    assert not os.path.exists(full_path)
    assert not os.path.exists(thumb_path)


def test_site_settings_singleton_with_defaults():
    settings_obj = SiteSettings.load()
    assert settings_obj.pk == 1
    assert settings_obj.company_name == "Батыс Курылыс XXI"
    assert "Астана" in settings_obj.address
    SiteSettings(company_name="Другое").save()
    assert SiteSettings.objects.count() == 1


def test_whatsapp_and_phone_lists():
    settings_obj = SiteSettings.load()
    settings_obj.phones = "+7 (7172) 00-00-00\n\n"
    settings_obj.save()
    assert settings_obj.phone_list == ["+7 (7172) 00-00-00"]
    assert settings_obj.whatsapp_list == [
        {"display": "+7 777 305 4243", "wa": "77773054243"},
        {"display": "+7 777 377 3763", "wa": "77773773763"},
    ]


def test_context_processor():
    make_category(name="Активная", is_active=True)
    make_category(name="Скрытая", is_active=False)
    context = site(RequestFactory().get("/"))
    assert context["site"].company_name == "Батыс Курылыс XXI"
    assert context["site_url"] == "http://localhost:8000"
    assert [c.name for c in context["nav_categories"]] == ["Активная"]
```

- [ ] **Step 2: Запустить — должны упасть**

Run: `uv run pytest tests/test_images_and_settings.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'catalog.context_processors'`.

- [ ] **Step 3: Конвертация изображений**

`catalog/images.py`:
```python
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

FULL_MAX_SIDE = 1600
THUMB_MAX_SIDE = 400
WEBP_QUALITY = 82


def _encode(image: Image.Image, max_side: int) -> ContentFile:
    copy = image.copy()
    copy.thumbnail((max_side, max_side))
    buffer = BytesIO()
    copy.save(buffer, "WEBP", quality=WEBP_QUALITY, method=6)
    return ContentFile(buffer.getvalue())


def to_webp(file) -> tuple[ContentFile, ContentFile]:
    """Возвращает (полное изображение ≤1600 px, миниатюру ≤400 px) в WebP."""
    if hasattr(file, "seek"):
        file.seek(0)
    with Image.open(file) as source:
        image = ImageOps.exif_transpose(source)
        has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
        image = image.convert("RGBA" if has_alpha else "RGB")
        return _encode(image, FULL_MAX_SIDE), _encode(image, THUMB_MAX_SIDE)
```

- [ ] **Step 4: Модели `ProductImage` и `SiteSettings`**

В `catalog/models.py` заменить блок импортов в начале файла:
```python
import re
import uuid
from decimal import Decimal

from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from catalog.images import to_webp
from catalog.paths import category_path, product_path
from catalog.sanitize import sanitize_html
```

В класс `Product` добавить свойство сразу после `displayed_price`:
```python
    @property
    def main_image(self) -> "ProductImage | None":
        images = list(self.images.all())
        return images[0] if images else None
```

В конец `catalog/models.py` добавить:
```python
def product_image_path(instance: "ProductImage", filename: str) -> str:
    return f"products/{instance.product.slug}/{uuid.uuid4().hex}.webp"


def product_thumbnail_path(instance: "ProductImage", filename: str) -> str:
    return f"products/{instance.product.slug}/thumbs/{uuid.uuid4().hex}.webp"


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField("Фото", upload_to=product_image_path)
    thumbnail = models.ImageField(upload_to=product_thumbnail_path, blank=True, editable=False)
    alt = models.CharField("Alt-текст", max_length=255, blank=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "фото"
        verbose_name_plural = "фото"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return self.alt or self.image.name

    def save(self, *args, **kwargs) -> None:
        if self.image and not getattr(self.image, "_committed", True):
            full, thumb = to_webp(self.image.file)
            self.image.save("image.webp", full, save=False)
            self.thumbnail.save("thumb.webp", thumb, save=False)
        if not self.alt:
            self.alt = self.product.name
        super().save(*args, **kwargs)


@receiver(post_delete, sender=ProductImage)
def delete_product_image_files(sender, instance: ProductImage, **kwargs) -> None:
    for field_file in (instance.image, instance.thumbnail):
        if field_file:
            field_file.delete(save=False)


DEFAULT_ADDRESS = "Казахстан, г. Астана, ул. Керей Жанибек хандар, 50/3"
DEFAULT_WHATSAPP = "+7 777 305 4243\n+7 777 377 3763"


class SiteSettings(models.Model):
    company_name = models.CharField("Название компании", max_length=200, default="Батыс Курылыс XXI")
    address = models.CharField("Адрес", max_length=300, blank=True, default=DEFAULT_ADDRESS)
    phones = models.TextField("Телефоны", blank=True, help_text="По одному номеру в строке.")
    whatsapp_numbers = models.TextField(
        "WhatsApp", blank=True, default=DEFAULT_WHATSAPP, help_text="По одному номеру в строке."
    )
    notification_email = models.EmailField("Email для заявок", blank=True)
    public_email = models.EmailField("Email для клиентов", blank=True)
    working_hours = models.CharField(
        "Часы работы", max_length=200, blank=True, help_text="Формат schema.org, например: Mo-Fr 09:00-18:00"
    )
    bin = models.CharField("БИН", max_length=12, blank=True)
    map_url = models.URLField("Ссылка на карту (2GIS)", blank=True)

    class Meta:
        verbose_name = "настройки сайта"
        verbose_name_plural = "настройки сайта"

    def __str__(self) -> str:
        return "Настройки сайта"

    def save(self, *args, **kwargs) -> None:
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "SiteSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def phone_list(self) -> list[str]:
        return [line.strip() for line in self.phones.splitlines() if line.strip()]

    @property
    def whatsapp_list(self) -> list[dict]:
        return [
            {"display": line.strip(), "wa": re.sub(r"\D", "", line)}
            for line in self.whatsapp_numbers.splitlines()
            if line.strip()
        ]
```

- [ ] **Step 5: Context processor**

`catalog/context_processors.py`:
```python
from django.conf import settings

from catalog.models import Category, SiteSettings


def site(request) -> dict:
    return {
        "site": SiteSettings.load(),
        "site_url": settings.SITE_URL,
        "nav_categories": Category.objects.filter(is_active=True).only("name", "slug"),
    }
```

В `config/settings.py` в `TEMPLATES[0]["OPTIONS"]["context_processors"]` добавить последней строкой:
```python
                "catalog.context_processors.site",
```

- [ ] **Step 6: Миграция и тесты**

```bash
uv run python manage.py makemigrations catalog
uv run pytest tests/test_images_and_settings.py tests/test_catalog_models.py
```
Expected: создана `0002_...`; `23 passed`.

- [ ] **Step 7: Commit**

```bash
git add catalog config/settings.py tests/test_images_and_settings.py
git commit -m "feat(catalog): add WebP product images and site settings singleton"
```

---

### Task 5: Админка каталога

**Files:**
- Create: `catalog/forms.py`, `catalog/admin.py`, `catalog/roles.py`
- Modify: `catalog/apps.py`
- Test: `tests/test_catalog_admin.py`

**Interfaces:**
- Consumes: модели из Tasks 3–4.
- Produces: `catalog.roles.MANAGER_GROUP = "Менеджер"`, `catalog.roles.ensure_manager_group(**kwargs) -> None` (подключена к `post_migrate`); константа `catalog.forms.EDITOR_EXTENSIONS: dict`; фикстура `superuser` в `tests/conftest.py`.

- [ ] **Step 1: Проверить API редактора**

```bash
uv run python -c "import inspect; from django_prose_editor.fields import ProseEditorFormField; print(inspect.signature(ProseEditorFormField.__init__))"
```
Expected: сигнатура содержит `extensions`. Если импорта нет или `extensions` отсутствует — открыть README установленной версии (`.venv/Lib/site-packages/django_prose_editor/` и страницу пакета на PyPI для этой версии) и адаптировать **только** `catalog/forms.py` (Step 4) так, чтобы поля `description` и `seo_text` использовали виджет редактора с набором расширений из `EDITOR_EXTENSIONS`. Остальной код задачи не меняется.

- [ ] **Step 2: Добавить фикстуру суперпользователя**

В конец `tests/conftest.py`:
```python
@pytest.fixture
def superuser(django_user_model):
    return django_user_model.objects.create_superuser("root", "root@example.com", "very-strong-pass-123")
```

- [ ] **Step 3: Написать падающие тесты**

`tests/test_catalog_admin.py`:
```python
import pytest
from django.conf import settings
from django.contrib.auth.models import Group

from catalog.models import SiteSettings
from catalog.roles import MANAGER_GROUP
from tests.factories import make_product

pytestmark = pytest.mark.django_db

ADMIN = f"/{settings.ADMIN_URL}"


@pytest.mark.parametrize("model", ["category", "product", "redirect", "sitesettings"])
def test_changelists_open(client, superuser, model):
    make_product()
    client.force_login(superuser)
    assert client.get(f"{ADMIN}catalog/{model}/").status_code == 200


def test_product_add_and_change_pages_open(client, superuser):
    product = make_product()
    client.force_login(superuser)
    assert client.get(f"{ADMIN}catalog/product/add/").status_code == 200
    assert client.get(f"{ADMIN}catalog/product/{product.pk}/change/").status_code == 200


def test_site_settings_cannot_be_added_twice_or_deleted(client, superuser):
    SiteSettings.load()
    client.force_login(superuser)
    assert client.get(f"{ADMIN}catalog/sitesettings/add/").status_code == 403
    assert client.get(f"{ADMIN}catalog/sitesettings/1/delete/").status_code == 403


def test_login_locked_after_five_failures(client, superuser):
    url = f"{ADMIN}login/"
    for _ in range(5):
        client.post(url, {"username": "root", "password": "wrong"})
    response = client.post(url, {"username": "root", "password": "very-strong-pass-123"})
    assert response.status_code == 429


def test_manager_group_has_catalog_permissions():
    group = Group.objects.get(name=MANAGER_GROUP)
    codenames = set(group.permissions.values_list("codename", flat=True))
    assert {"change_product", "add_product", "change_category", "view_sitesettings", "change_redirect"} <= codenames
    assert "change_user" not in codenames
```

- [ ] **Step 4: Реализация форм**

`catalog/forms.py`:
```python
from django import forms
from django_prose_editor.fields import ProseEditorFormField

from catalog.models import Category, Product

EDITOR_EXTENSIONS = {
    "Bold": True,
    "Italic": True,
    "Heading": {"levels": [2, 3, 4]},
    "BulletList": True,
    "OrderedList": True,
    "ListItem": True,
    "Link": {"protocols": ["http", "https", "tel", "mailto"]},
    "Table": True,
    "HardBreak": True,
}


class CategoryAdminForm(forms.ModelForm):
    seo_text = ProseEditorFormField(label="SEO-текст", required=False, extensions=EDITOR_EXTENSIONS)

    class Meta:
        model = Category
        fields = "__all__"


class ProductAdminForm(forms.ModelForm):
    description = ProseEditorFormField(label="Описание", required=False, extensions=EDITOR_EXTENSIONS)

    class Meta:
        model = Product
        fields = "__all__"
```

- [ ] **Step 5: Реализация админки**

`catalog/admin.py`:
```python
from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from catalog.forms import CategoryAdminForm, ProductAdminForm
from catalog.models import Category, Product, ProductImage, ProductSpec, Redirect, SiteSettings

admin.site.site_header = "Батыс Курылыс XXI — управление сайтом"
admin.site.site_title = "Батыс Курылыс XXI"
admin.site.index_title = "Разделы"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    form = CategoryAdminForm
    list_display = ("name", "slug", "product_count", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (None, {"fields": ("name", "slug", "seo_text", "is_active", "sort_order")}),
        ("SEO", {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_product_count=Count("products"))

    @admin.display(description="Товаров", ordering="_product_count")
    def product_count(self, obj: Category) -> int:
        return obj._product_count


class ProductSpecInline(admin.TabularInline):
    model = ProductSpec
    extra = 1
    fields = ("name", "value", "sort_order")


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("preview", "image", "alt", "sort_order")
    readonly_fields = ("preview",)

    @admin.display(description="Превью")
    def preview(self, obj: ProductImage) -> str:
        if obj.pk and obj.thumbnail:
            return format_html('<img src="{}" alt="" style="height:60px">', obj.thumbnail.url)
        return "—"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ("thumb", "name", "category", "is_active", "show_price", "price")
    list_display_links = ("thumb", "name")
    list_filter = ("category", "is_active", "show_price")
    search_fields = ("name", "model_code")
    list_select_related = ("category",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ProductSpecInline, ProductImageInline)
    fieldsets = (
        (None, {"fields": ("category", "name", "slug", "model_code", "short_description", "description")}),
        ("Цена", {"fields": ("price", "show_price")}),
        ("Публикация", {"fields": ("is_active", "sort_order")}),
        ("SEO", {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("images")

    @admin.display(description="Фото")
    def thumb(self, obj: Product) -> str:
        image = obj.main_image
        if image and image.thumbnail:
            return format_html('<img src="{}" alt="" style="height:40px">', image.thumbnail.url)
        return "—"


@admin.register(Redirect)
class RedirectAdmin(admin.ModelAdmin):
    list_display = ("old_path", "new_path")
    search_fields = ("old_path", "new_path")


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request) -> bool:
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
```

- [ ] **Step 6: Группа «Менеджер»**

`catalog/roles.py`:
```python
from django.contrib.auth.models import Group, Permission
from django.db.models import Q

MANAGER_GROUP = "Менеджер"
MANAGER_MODELS = {
    "catalog": ["category", "product", "productspec", "productimage", "redirect", "sitesettings"],
    "orders": ["quoterequest", "quoteitem"],
}


def ensure_manager_group(**kwargs) -> None:
    """Идемпотентно выдаёт группе все права на модели каталога и заявок (вызывается после migrate)."""
    group, _ = Group.objects.get_or_create(name=MANAGER_GROUP)
    condition = Q()
    for app_label, models in MANAGER_MODELS.items():
        condition |= Q(content_type__app_label=app_label, content_type__model__in=models)
    group.permissions.set(Permission.objects.filter(condition))
```

`catalog/apps.py`:
```python
from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"
    verbose_name = "Каталог"

    def ready(self) -> None:
        from catalog.roles import ensure_manager_group

        post_migrate.connect(ensure_manager_group, dispatch_uid="catalog.ensure_manager_group")
```

- [ ] **Step 7: Запустить тесты**

Run: `uv run pytest`
Expected: все тесты проходят (`tests/test_catalog_admin.py`: `8 passed`).

- [ ] **Step 8: Ручная проверка редактора**

```bash
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```
Открыть `http://localhost:8000/manage-dev/catalog/product/add/`: у поля «Описание» отображается панель редактора (жирный, списки, заголовки, ссылка, таблица). Создать категорию и товар с описанием, содержащим жирный текст и список, сохранить, открыть снова — форматирование сохранилось.

- [ ] **Step 9: Commit**

```bash
git add catalog tests/conftest.py tests/test_catalog_admin.py
git commit -m "feat(catalog): add admin with rich text editor, login lockout and manager group"
```

---
### Task 6: Стили и макет для согласования

Спека требует согласовать макет главной и карточки товара **до** вёрстки шаблонов. Эта задача создаёт итоговый `static/css/site.css` и статический макет, который использует те же CSS-классы, что и шаблоны в Tasks 8 и 13.

**Files:**
- Create: `static/css/site.css`, `docs/design/mockup.html`

**Interfaces:**
- Produces: CSS-классы, которые используют шаблоны: `container, skip-link, visually-hidden, site-header, site-header__inner, logo, nav, cart-link, cart-count, breadcrumbs, page-head, btn, btn--primary, btn--whatsapp, btn--ghost, hero, hero__text, hero__actions, section, section__head, category-grid, category-card, category-card__name, category-card__count, product-grid, product-card, product-card__image, product-card__placeholder, product-card__body, product-card__name, product-card__model, product-card__price, price-on-request, product, product__gallery, product__main-image, product__thumbs, product__info, product__model, product__short, product__price, product__actions, qty, note, panel, specs, prose, features, contacts-list, quote-layout, quote-list, quote-item, quote-item__name, quote-item__remove, quote-empty, form, form__row, form__error, form__hp, notice, notice--error, notice--success, toast, site-footer, footer-grid`.

- [ ] **Step 1: Создать `static/css/site.css`**

```css
:root {
  --color-bg: #f5f6f8;
  --color-surface: #ffffff;
  --color-text: #1d232b;
  --color-muted: #5b6573;
  --color-border: #dde1e6;
  --color-accent: #c2410c;
  --color-accent-dark: #9a3412;
  --color-focus: #fdba74;
  --color-whatsapp: #15803d;
  --color-error: #b91c1c;
  --radius: 8px;
  --shadow: 0 1px 2px rgba(16, 24, 40, .06), 0 2px 6px rgba(16, 24, 40, .08);
  --container: 1200px;
  --font: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

*, *::before, *::after { box-sizing: border-box; }
[hidden] { display: none !important; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; font-family: var(--font); font-size: 16px; line-height: 1.6; color: var(--color-text); background: var(--color-bg); }
img { max-width: 100%; height: auto; display: block; }
a { color: var(--color-accent); }
a:hover { color: var(--color-accent-dark); }
h1, h2, h3 { line-height: 1.25; margin: 0 0 .5em; }
h1 { font-size: clamp(1.6rem, 1.2rem + 2vw, 2.4rem); }
h2 { font-size: clamp(1.3rem, 1.1rem + 1vw, 1.75rem); }
h3 { font-size: 1.15rem; }
:focus-visible { outline: 3px solid var(--color-focus); outline-offset: 2px; }

.container { width: 100%; max-width: var(--container); margin: 0 auto; padding-inline: 16px; }
.visually-hidden { position: absolute !important; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.skip-link { position: absolute; left: -9999px; }
.skip-link:focus { left: 16px; top: 8px; z-index: 100; background: var(--color-surface); padding: 8px 12px; }
main { padding-block: 24px 48px; }

/* Header */
.site-header { position: sticky; top: 0; z-index: 50; background: var(--color-surface); border-bottom: 1px solid var(--color-border); }
.site-header__inner { display: flex; align-items: center; gap: 20px; min-height: 64px; }
.logo { margin-right: auto; font-weight: 800; font-size: 1.1rem; color: var(--color-text); text-decoration: none; }
.logo span { color: var(--color-accent); }
.nav { display: flex; gap: 20px; }
.nav a { color: var(--color-text); text-decoration: none; font-weight: 500; }
.nav a:hover { color: var(--color-accent); }
.cart-link { display: inline-flex; align-items: center; gap: 8px; padding: 8px 14px; border: 1px solid var(--color-border); border-radius: 999px; color: var(--color-text); text-decoration: none; font-weight: 600; }
.cart-count { display: inline-flex; align-items: center; justify-content: center; min-width: 22px; height: 22px; padding: 0 6px; border-radius: 999px; background: var(--color-accent); color: #fff; font-size: .8rem; }
@media (max-width: 640px) {
  .site-header__inner { flex-wrap: wrap; gap: 8px 16px; padding-block: 8px; }
  .nav { order: 3; width: 100%; overflow-x: auto; }
}

/* Common blocks */
.breadcrumbs { margin-bottom: 16px; font-size: .9rem; color: var(--color-muted); }
.breadcrumbs ol { display: flex; flex-wrap: wrap; gap: 4px 8px; list-style: none; margin: 0; padding: 0; }
.breadcrumbs li + li::before { content: "/"; margin-right: 8px; color: var(--color-border); }
.breadcrumbs a { color: var(--color-muted); }
.page-head { margin-bottom: 24px; }
.page-head p { max-width: 760px; color: var(--color-muted); }
.section { margin-block: 40px; }
.section__head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px 16px; margin-bottom: 16px; }
.panel { margin-top: 24px; padding: clamp(16px, 3vw, 32px); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); }
.note { color: var(--color-muted); font-size: .95rem; }

.btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 12px 20px; border: 1px solid transparent; border-radius: var(--radius); font: inherit; font-weight: 600; text-decoration: none; cursor: pointer; transition: background-color .15s; }
.btn--primary { background: var(--color-accent); color: #fff; }
.btn--primary:hover { background: var(--color-accent-dark); color: #fff; }
.btn--whatsapp { background: var(--color-whatsapp); color: #fff; }
.btn--whatsapp:hover { background: #166534; color: #fff; }
.btn--ghost { background: transparent; border-color: var(--color-border); color: var(--color-text); }
.btn[disabled] { opacity: .5; cursor: not-allowed; }

/* Home */
.hero { margin-bottom: 32px; padding: clamp(24px, 5vw, 56px); border-radius: var(--radius); background: linear-gradient(135deg, #1d232b 0%, #2f3a47 100%); color: #fff; }
.hero__text { max-width: 640px; color: #d1d5db; font-size: 1.1rem; }
.hero__actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 20px; }
.hero .btn--ghost { border-color: #4b5563; color: #fff; }
.features { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin: 0; padding: 0; list-style: none; }
.features li { padding: 18px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); }
.features strong { display: block; margin-bottom: 4px; }

/* Catalog */
.category-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }
.category-card { display: flex; flex-direction: column; justify-content: space-between; min-height: 110px; padding: 18px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); color: var(--color-text); text-decoration: none; transition: border-color .15s, box-shadow .15s; }
.category-card:hover { border-color: var(--color-accent); box-shadow: var(--shadow); color: var(--color-text); }
.category-card__name { font-weight: 700; }
.category-card__count { color: var(--color-muted); font-size: .9rem; }
.product-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 20px; }
.product-card { display: flex; flex-direction: column; overflow: hidden; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); color: var(--color-text); text-decoration: none; transition: border-color .15s, box-shadow .15s; }
.product-card:hover { border-color: #c5cbd3; box-shadow: var(--shadow); color: var(--color-text); }
.product-card__image { display: flex; align-items: center; justify-content: center; aspect-ratio: 4 / 3; padding: 12px; background: #fff; border-bottom: 1px solid var(--color-border); }
.product-card__image img { max-height: 100%; object-fit: contain; }
.product-card__placeholder { color: var(--color-muted); font-size: .9rem; }
.product-card__body { display: flex; flex: 1; flex-direction: column; gap: 6px; padding: 14px 16px 18px; }
.product-card__name { font-weight: 600; line-height: 1.35; }
.product-card__model { color: var(--color-muted); font-size: .9rem; }
.product-card__price { margin-top: auto; font-weight: 700; }
.price-on-request { color: var(--color-muted); font-weight: 500; }

/* Product */
.product { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 32px; padding: clamp(16px, 3vw, 32px); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); }
@media (max-width: 860px) { .product { grid-template-columns: 1fr; } }
.product__main-image { display: flex; align-items: center; justify-content: center; aspect-ratio: 4 / 3; padding: 12px; background: #fff; border: 1px solid var(--color-border); border-radius: var(--radius); }
.product__main-image img { max-height: 100%; object-fit: contain; }
.product__thumbs { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.product__thumbs button { width: 72px; height: 72px; padding: 4px; background: #fff; border: 1px solid var(--color-border); border-radius: 6px; cursor: pointer; }
.product__thumbs button[aria-current="true"] { border-color: var(--color-accent); }
.product__thumbs img { width: 100%; height: 100%; object-fit: contain; }
.product__model { color: var(--color-muted); }
.product__short { color: var(--color-muted); font-size: 1.05rem; }
.product__price { margin-block: 16px; font-size: 1.5rem; font-weight: 800; }
.product__actions { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-block: 20px; }
.qty { display: inline-flex; align-items: center; overflow: hidden; border: 1px solid var(--color-border); border-radius: var(--radius); background: #fff; }
.qty input { width: 76px; padding: 11px 8px; border: 0; font: inherit; text-align: center; }
.specs { width: 100%; border-collapse: collapse; }
.specs th, .specs td { padding: 10px 12px; border-bottom: 1px solid var(--color-border); text-align: left; vertical-align: top; }
.specs th { width: 50%; color: var(--color-muted); font-weight: 500; }
.prose { max-width: 760px; }
.prose table { display: block; overflow-x: auto; width: 100%; margin-block: 16px; border-collapse: collapse; }
.prose th, .prose td { padding: 8px 10px; border: 1px solid var(--color-border); text-align: left; }
.prose th { background: var(--color-bg); }

/* Contacts */
.contacts-list { display: grid; gap: 14px; margin: 0; padding: 0; list-style: none; }
.contacts-list strong { display: block; color: var(--color-muted); font-weight: 500; font-size: .9rem; }

/* Quote */
.quote-layout { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 24px; align-items: start; }
@media (max-width: 860px) { .quote-layout { grid-template-columns: 1fr; } }
.quote-list { display: grid; gap: 12px; margin: 0; padding: 0; list-style: none; }
.quote-item { display: grid; grid-template-columns: 64px minmax(0, 1fr) auto auto; gap: 12px; align-items: center; padding: 12px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); }
.quote-item img { width: 64px; height: 64px; object-fit: contain; }
.quote-item__name { color: var(--color-text); font-weight: 600; text-decoration: none; }
.quote-item__remove { padding: 4px 10px; background: none; border: 0; color: var(--color-muted); font-size: 1.4rem; line-height: 1; cursor: pointer; }
@media (max-width: 520px) {
  .quote-item { grid-template-columns: 48px minmax(0, 1fr) auto; }
  .quote-item img { width: 48px; height: 48px; }
  .quote-item .qty { grid-column: 2; justify-self: start; }
}
.quote-empty { padding: 24px; background: var(--color-surface); border: 1px dashed var(--color-border); border-radius: var(--radius); color: var(--color-muted); text-align: center; }
.form { display: grid; gap: 16px; }
.form__row { display: grid; gap: 6px; }
.form__row label { font-weight: 600; }
.form input[type="text"], .form input[type="tel"] { width: 100%; padding: 12px; border: 1px solid var(--color-border); border-radius: var(--radius); font: inherit; }
.form__error { margin: 0; color: var(--color-error); font-size: .9rem; }
.form__hp { position: absolute; left: -10000px; width: 1px; height: 1px; overflow: hidden; }
.notice { padding: 12px 16px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); }
.notice--error { background: #fef2f2; border-color: #fecaca; color: var(--color-error); }
.notice--success { background: #f0fdf4; border-color: #bbf7d0; color: #14532d; }
.toast { position: fixed; left: 50%; bottom: 24px; z-index: 100; display: flex; align-items: center; gap: 12px; max-width: calc(100% - 32px); padding: 12px 18px; transform: translateX(-50%); background: var(--color-text); color: #fff; border-radius: var(--radius); box-shadow: var(--shadow); }
.toast a { color: var(--color-focus); }

/* Footer */
.site-footer { margin-top: 48px; padding-block: 32px; background: var(--color-text); color: #d1d5db; }
.site-footer h2 { font-size: 1rem; color: #fff; }
.site-footer a { color: #fff; }
.site-footer ul { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.footer-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 24px; }
```

- [ ] **Step 2: Создать макет `docs/design/mockup.html`**

```html
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Макет — Батыс Курылыс XXI</title>
  <link rel="stylesheet" href="../../static/css/site.css">
</head>
<body>
  <header class="site-header">
    <div class="container site-header__inner">
      <a class="logo" href="#">Батыс Курылыс <span>XXI</span></a>
      <nav class="nav" aria-label="Основное меню"><a href="#">Каталог</a><a href="#">Контакты</a></nav>
      <a class="cart-link" href="#quote">Запрос <span class="cart-count">2</span></a>
    </div>
  </header>

  <main class="container">
    <p class="note">Макет 1 из 2 — главная страница</p>
    <section class="hero">
      <h1>Гидравлический и трубный инструмент в Астане</h1>
      <p class="hero__text">Трубогибы, прессы, домкраты, маслостанции, съёмники подшипников и шинообрабатывающее оборудование. Подберём модель под задачу и подготовим коммерческое предложение.</p>
      <div class="hero__actions"><a class="btn btn--primary" href="#">Перейти в каталог</a><a class="btn btn--ghost" href="#">Написать в WhatsApp</a></div>
    </section>

    <section class="section">
      <div class="section__head"><h2>Категории</h2><a href="#">Весь каталог</a></div>
      <div class="category-grid">
        <a class="category-card" href="#"><span class="category-card__name">Трубогибы</span><span class="category-card__count">10 товаров</span></a>
        <a class="category-card" href="#"><span class="category-card__name">Съёмники подшипников гидравлические</span><span class="category-card__count">12 товаров</span></a>
        <a class="category-card" href="#"><span class="category-card__name">Маслостанции</span><span class="category-card__count">6 товаров</span></a>
        <a class="category-card" href="#"><span class="category-card__name">Домкраты</span><span class="category-card__count">2 товара</span></a>
      </div>
    </section>

    <section class="section">
      <div class="section__head"><h2>Популярные товары</h2></div>
      <div class="product-grid">
        <a class="product-card" href="#product">
          <div class="product-card__image"><span class="product-card__placeholder">Фото</span></div>
          <div class="product-card__body"><span class="product-card__name">Трубогиб ручной гидравлический ТПГ-2Б</span><span class="product-card__model">ТПГ-2Б</span><span class="product-card__price price-on-request">Цена по запросу</span></div>
        </a>
        <a class="product-card" href="#product">
          <div class="product-card__image"><span class="product-card__placeholder">Фото</span></div>
          <div class="product-card__body"><span class="product-card__name">Маслостанция МГС 700-0.8-Р-1</span><span class="product-card__model">МГС 700-0.8-Р-1</span><span class="product-card__price">150 000 ₸</span></div>
        </a>
        <a class="product-card" href="#product">
          <div class="product-card__image"><span class="product-card__placeholder">Фото</span></div>
          <div class="product-card__body"><span class="product-card__name">Гидравлический съёмник подшипников СГ-50</span><span class="product-card__model">СГ-50</span><span class="product-card__price price-on-request">Цена по запросу</span></div>
        </a>
      </div>
    </section>

    <section class="section">
      <ul class="features">
        <li><strong>Подбор модели</strong>Поможем выбрать инструмент под ваши трубы, нагрузки и условия работы.</li>
        <li><strong>Коммерческое предложение</strong>Соберите список в запросе — пришлём цены и сроки.</li>
        <li><strong>Поставка по Казахстану</strong>Организуем поставку в ваш город.</li>
      </ul>
    </section>

    <hr id="product">
    <p class="note">Макет 2 из 2 — карточка товара</p>
    <nav class="breadcrumbs" aria-label="Навигация"><ol><li><a href="#">Главная</a></li><li><a href="#">Каталог</a></li><li><a href="#">Трубогибы</a></li><li><span aria-current="page">ТПГ-2Б</span></li></ol></nav>
    <article class="product">
      <div class="product__gallery">
        <div class="product__main-image"><span class="product-card__placeholder">Главное фото</span></div>
        <div class="product__thumbs"><button type="button" aria-current="true">1</button><button type="button">2</button><button type="button">3</button></div>
      </div>
      <div class="product__info">
        <h1>Трубогиб ручной гидравлический ТПГ-2Б</h1>
        <p class="product__model">Модель: ТПГ-2Б</p>
        <p class="product__short">Переносной гидравлический трубогиб для водогазопроводных труб до 2".</p>
        <p class="product__price price-on-request">Цена по запросу</p>
        <div class="product__actions">
          <div class="qty"><label class="visually-hidden" for="qty">Количество</label><input id="qty" type="number" min="1" max="999" value="1"></div>
          <button type="button" class="btn btn--primary">Добавить в запрос</button>
          <a class="btn btn--whatsapp" href="#">Спросить в WhatsApp</a>
        </div>
        <p class="note">Добавьте товары в запрос — мы свяжемся с вами и пришлём коммерческое предложение.</p>
      </div>
    </article>
    <section class="panel">
      <h2>Характеристики</h2>
      <table class="specs"><tbody>
        <tr><th scope="row">Наибольшее усилие гидроцилиндра, тс</th><td>10</td></tr>
        <tr><th scope="row">Наибольший ход штока, мм</th><td>180</td></tr>
        <tr><th scope="row">Масса, кг</th><td>54</td></tr>
      </tbody></table>
    </section>
    <section class="panel prose">
      <h2>Описание</h2>
      <p>Текст описания товара: назначение, особенности, применение и комплектация.</p>
    </section>

    <hr id="quote">
    <p class="note">Бонус — страница запроса</p>
    <div class="quote-layout">
      <ul class="quote-list">
        <li class="quote-item"><span class="product-card__placeholder">Фото</span><a class="quote-item__name" href="#">Трубогиб ручной гидравлический ТПГ-2Б</a><div class="qty"><input type="number" value="1" aria-label="Количество"></div><button class="quote-item__remove" type="button" aria-label="Удалить">×</button></li>
      </ul>
      <form class="form panel">
        <div class="form__row"><label for="name">Имя</label><input id="name" type="text"></div>
        <div class="form__row"><label for="phone">Телефон</label><input id="phone" type="tel" placeholder="+7 777 305 4243"><p class="form__error">Укажите телефон в формате +7 XXX XXX XX XX.</p></div>
        <button class="btn btn--primary" type="button">Отправить запрос</button>
      </form>
    </div>
  </main>

  <footer class="site-footer">
    <div class="container footer-grid">
      <div><h2>Батыс Курылыс XXI</h2><p>Казахстан, г. Астана, ул. Керей Жанибек хандар, 50/3</p></div>
      <div><h2>Каталог</h2><ul><li><a href="#">Трубогибы</a></li><li><a href="#">Маслостанции</a></li></ul></div>
      <div><h2>Связаться</h2><ul><li><a href="#">WhatsApp +7 777 305 4243</a></li><li><a href="#">WhatsApp +7 777 377 3763</a></li></ul></div>
    </div>
  </footer>
</body>
</html>
```

- [ ] **Step 3: Проверить макет самостоятельно**

Открыть `docs/design/mockup.html` в браузере на ширине 1280 px и 360 px (DevTools → адаптивный режим). Проверить: нет горизонтальной прокрутки страницы на 360 px; кнопки и поля не выходят за экран; меню в шапке переносится на вторую строку.

- [ ] **Step 4: ⛔ CHECKPOINT — согласование с владельцем**

Показать владельцу `docs/design/mockup.html` (скриншоты на 1280 и 360 px или сам файл) и дождаться явного «ок». Правки владельца вносятся в `static/css/site.css` (цвета в `:root`, отступы, размеры шрифтов) и отражаются в макете. **Не переходить к Task 7, пока нет подтверждения.** Если владелец просит изменить структуру страниц (другие блоки на главной, другой порядок), обновить макет и соответствующие шаблоны в Tasks 8/13 до их выполнения.

- [ ] **Step 5: Commit**

```bash
git add static/css/site.css docs/design/mockup.html
git commit -m "feat: add site stylesheet and page mockup approved by owner"
```

---
### Task 7: SEO-хелперы и JSON-LD

**Files:**
- Create: `catalog/seo.py`, `catalog/templatetags/__init__.py`, `catalog/templatetags/seo_tags.py`
- Test: `tests/test_seo.py`

**Interfaces:**
- Consumes: `Product.displayed_price`, `Product.get_absolute_url()`, `Product.images`, `Category`, `SiteSettings.phone_list`, `SiteSettings.whatsapp_list`.
- Produces (`catalog.seo`):
  - `absolute_url(path: str) -> str`
  - `truncate(text: str, limit: int = 160) -> str`
  - `category_title(category, site_name: str) -> str`, `category_description(category) -> str`
  - `product_title(product, site_name: str) -> str`, `product_description(product) -> str`
  - `breadcrumb_ld(items: list[tuple[str, str]]) -> dict` — items: `(название, путь)`
  - `product_ld(product) -> dict`
  - `local_business_ld(site) -> dict`
- Produces (шаблоны): `{% load seo_tags %}` → `{% ld_json data %}` выводит `<script type="application/ld+json">…</script>` с экранированием `<`, `>`, `&`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_seo.py`:
```python
import json
from decimal import Decimal

import pytest
from django.template import Context, Template

from catalog import seo
from catalog.models import SiteSettings
from tests.factories import make_category, make_product

pytestmark = pytest.mark.django_db


def test_truncate_keeps_short_text_and_cuts_on_word_boundary():
    assert seo.truncate("  короткий   текст ") == "короткий текст"
    result = seo.truncate("слово " * 50, limit=30)
    assert len(result) <= 30
    assert result.endswith("…")
    assert not result.endswith(" …")


def test_category_title_and_description_defaults_and_overrides():
    category = make_category(name="Трубогибы", seo_text="<p>Гибка труб любых диаметров.</p>")
    assert seo.category_title(category, "Батыс Курылыс XXI") == "Трубогибы купить в Астане — Батыс Курылыс XXI"
    assert seo.category_description(category) == "Гибка труб любых диаметров."
    category.meta_title = "Свой заголовок"
    category.meta_description = "Своё описание"
    assert seo.category_title(category, "X") == "Свой заголовок"
    assert seo.category_description(category) == "Своё описание"


def test_category_description_fallback_without_text():
    category = make_category(name="Тиски", seo_text="")
    assert seo.category_description(category) == (
        "Тиски: каталог, характеристики и запрос коммерческого предложения."
    )


def test_product_title_and_description():
    product = make_product(name="Трубогиб ТПГ-2Б", short_description="Для труб до 2 дюймов.")
    assert seo.product_title(product, "Батыс Курылыс XXI") == "Трубогиб ТПГ-2Б купить в Астане — Батыс Курылыс XXI"
    assert seo.product_description(product) == "Для труб до 2 дюймов."
    product.short_description = ""
    product.description = "<p>Описание из редактора.</p>"
    assert seo.product_description(product) == "Описание из редактора."


def test_breadcrumb_ld():
    data = seo.breadcrumb_ld([("Главная", "/"), ("Каталог", "/catalog/")])
    assert data["@type"] == "BreadcrumbList"
    assert data["itemListElement"][1] == {
        "@type": "ListItem",
        "position": 2,
        "name": "Каталог",
        "item": "http://localhost:8000/catalog/",
    }


def test_product_ld_without_price_has_no_offers_and_no_brand():
    category = make_category(slug="pipe-benders")
    product = make_product(category=category, slug="tpg-2b", model_code="ТПГ-2Б", price=Decimal("1000"))
    data = seo.product_ld(product)
    assert data["@type"] == "Product"
    assert data["sku"] == "ТПГ-2Б"
    assert data["url"] == "http://localhost:8000/catalog/pipe-benders/tpg-2b/"
    assert "offers" not in data
    assert "brand" not in data


def test_product_ld_with_visible_price_has_offer_in_kzt():
    product = make_product(price=Decimal("150000"), show_price=True)
    offer = seo.product_ld(product)["offers"]
    assert offer["price"] == "150000"
    assert offer["priceCurrency"] == "KZT"


def test_local_business_ld_skips_empty_fields():
    site = SiteSettings.load()
    data = seo.local_business_ld(site)
    assert data["@type"] == "LocalBusiness"
    assert data["name"] == "Батыс Курылыс XXI"
    assert data["telephone"] == "+7 777 305 4243"
    assert "email" not in data
    assert "openingHours" not in data
    site.public_email = "info@prom-products.kz"
    site.working_hours = "Mo-Fr 09:00-18:00"
    data = seo.local_business_ld(site)
    assert data["email"] == "info@prom-products.kz"
    assert data["openingHours"] == "Mo-Fr 09:00-18:00"


def test_ld_json_tag_escapes_script_breakout():
    html = Template("{% load seo_tags %}{% ld_json data %}").render(Context({"data": {"name": "</script><b>"}}))
    assert html.startswith('<script type="application/ld+json">')
    assert "</script><b>" not in html
    payload = html.removeprefix('<script type="application/ld+json">').removesuffix("</script>")
    assert json.loads(payload) == {"name": "</script><b>"}
```

- [ ] **Step 2: Запустить — должны упасть**

Run: `uv run pytest tests/test_seo.py`
Expected: FAIL, `ImportError: cannot import name 'seo' from 'catalog'`.

- [ ] **Step 3: Реализация `catalog/seo.py`**

```python
from django.conf import settings
from django.utils.html import strip_tags


def absolute_url(path: str) -> str:
    return f"{settings.SITE_URL}{path}"


def truncate(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;:—-")
    return f"{cut}…"


def _plain(html: str) -> str:
    return " ".join(strip_tags(html or "").split())


def category_title(category, site_name: str) -> str:
    return category.meta_title or f"{category.name} купить в Астане — {site_name}"


def category_description(category) -> str:
    if category.meta_description:
        return category.meta_description
    text = _plain(category.seo_text)
    if text:
        return truncate(text)
    return f"{category.name}: каталог, характеристики и запрос коммерческого предложения."


def product_title(product, site_name: str) -> str:
    return product.meta_title or f"{product.name} купить в Астане — {site_name}"


def product_description(product) -> str:
    if product.meta_description:
        return product.meta_description
    return truncate(product.short_description or _plain(product.description))


def breadcrumb_ld(items: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": index, "name": name, "item": absolute_url(path)}
            for index, (name, path) in enumerate(items, start=1)
        ],
    }


def product_ld(product) -> dict:
    url = absolute_url(product.get_absolute_url())
    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "description": product_description(product),
        "url": url,
    }
    images = [absolute_url(image.image.url) for image in product.images.all() if image.image]
    if images:
        data["image"] = images
    if product.model_code:
        data["sku"] = product.model_code
    price = product.displayed_price
    if price is not None:
        data["offers"] = {
            "@type": "Offer",
            "price": str(price),
            "priceCurrency": "KZT",
            "availability": "https://schema.org/InStock",
            "url": url,
        }
    return data


def local_business_ld(site) -> dict:
    data = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": site.company_name,
        "url": settings.SITE_URL,
    }
    if site.address:
        data["address"] = {
            "@type": "PostalAddress",
            "streetAddress": site.address,
            "addressLocality": "Астана",
            "addressCountry": "KZ",
        }
    phones = site.phone_list + [item["display"] for item in site.whatsapp_list]
    if phones:
        data["telephone"] = phones[0]
    if site.public_email:
        data["email"] = site.public_email
    if site.working_hours:
        data["openingHours"] = site.working_hours
    if site.bin:
        data["taxID"] = site.bin
    if site.map_url:
        data["hasMap"] = site.map_url
    return data
```

- [ ] **Step 4: Реализация тега `ld_json`**

`catalog/templatetags/__init__.py`: пустой файл.

`catalog/templatetags/seo_tags.py`:
```python
import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_ESCAPES = {ord("<"): "\\u003C", ord(">"): "\\u003E", ord("&"): "\\u0026"}


@register.simple_tag
def ld_json(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False).translate(_ESCAPES)
    return mark_safe(f'<script type="application/ld+json">{payload}</script>')  # noqa: S308
```

- [ ] **Step 5: Запустить тесты**

Run: `uv run pytest tests/test_seo.py`
Expected: `9 passed`.

- [ ] **Step 6: Commit**

```bash
git add catalog/seo.py catalog/templatetags tests/test_seo.py
git commit -m "feat(catalog): add SEO titles, descriptions and JSON-LD helpers"
```

---
### Task 8: Публичные страницы каталога

**Files:**
- Create: `catalog/views.py`, `catalog/urls.py`, `templates/base.html`, `templates/404.html`, `templates/includes/breadcrumbs.html`, `templates/includes/product_card.html`, `templates/catalog/home.html`, `templates/catalog/index.html`, `templates/catalog/category.html`, `templates/catalog/product.html`, `templates/catalog/contacts.html`
- Modify: `config/urls.py`
- Delete: `templates/.gitkeep`
- Test: `tests/test_catalog_views.py`

**Interfaces:**
- Consumes: `catalog.seo.*` (Task 7), `SiteSettings.load()`, `Product.main_image`, `Product.displayed_price`, CSS-классы из Task 6, контекст `site`, `site_url`, `nav_categories` (Task 4).
- Produces:
  - URL names: `catalog:home` (`/`), `catalog:index` (`/catalog/`), `catalog:category` (`/catalog/<slug>/`), `catalog:product` (`/catalog/<category_slug>/<slug>/`), `catalog:contacts` (`/contacts/`).
  - `catalog.views.public_products() -> QuerySet[Product]` (активные товары активных категорий, с `category` и `images`).
  - `templates/base.html`: переменные `page_title`, `page_description`; блоки `title`, `robots`, `canonical`, `og_image`, `structured_data`, `content`. Подключает `static/js/cart.js` (файл появится в Task 14). В шапке — ссылка `/quote/` со счётчиком `<span class="cart-count" data-cart-count hidden>`.
  - Страница товара: контейнер `div.product__actions[data-product]` с атрибутами `data-id`, `data-name`, `data-url`, `data-thumb`; внутри `input[data-qty]` и `button[data-add-to-quote]`; миниатюры галереи `button[data-gallery-thumb][data-full][data-alt]`, главное фото `img[data-gallery-main]`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_catalog_views.py`:
```python
import json
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup

from catalog.models import ProductSpec
from tests.factories import make_category, make_product

pytestmark = pytest.mark.django_db


def soup(response) -> BeautifulSoup:
    return BeautifulSoup(response.content, "html.parser")


def ld_objects(response) -> list[dict]:
    return [json.loads(tag.string) for tag in soup(response).find_all("script", type="application/ld+json")]


@pytest.fixture
def catalog_data():
    pipe = make_category(name="Трубогибы", slug="pipe-benders", seo_text="<p>Гибка труб.</p>")
    make_category(name="Пустая", slug="empty")
    product = make_product(
        category=pipe,
        name="Трубогиб ТПГ-2Б",
        slug="tpg-2b",
        model_code="ТПГ-2Б",
        short_description="Для труб до 2 дюймов.",
        description="<p>Полное <strong>описание</strong>.</p>",
    )
    ProductSpec.objects.create(product=product, name="Масса, кг", value="54")
    return {"category": pipe, "product": product}


def test_home_lists_categories_with_products_and_featured(client, catalog_data):
    response = client.get("/")
    assert response.status_code == 200
    page = soup(response)
    names = [el.get_text() for el in page.select(".category-card__name")]
    assert names == ["Трубогибы"]
    assert "Трубогиб ТПГ-2Б" in page.select_one(".product-grid").get_text()
    assert any(obj["@type"] == "LocalBusiness" for obj in ld_objects(response))


def test_catalog_index(client, catalog_data):
    response = client.get("/catalog/")
    assert response.status_code == 200
    assert soup(response).h1.get_text() == "Каталог"
    assert "Трубогибы" in response.content.decode()


def test_category_page_seo(client, catalog_data):
    response = client.get("/catalog/pipe-benders/")
    page = soup(response)
    assert response.status_code == 200
    assert page.h1.get_text() == "Трубогибы"
    assert page.title.get_text() == "Трубогибы купить в Астане — Батыс Курылыс XXI"
    assert page.find("meta", attrs={"name": "description"})["content"] == "Гибка труб."
    assert page.find("link", rel="canonical")["href"] == "http://localhost:8000/catalog/pipe-benders/"
    assert "Трубогиб ТПГ-2Б" in page.select_one(".product-grid").get_text()
    assert any(obj["@type"] == "BreadcrumbList" for obj in ld_objects(response))


def test_product_page_content_and_seo(client, catalog_data):
    response = client.get("/catalog/pipe-benders/tpg-2b/")
    page = soup(response)
    assert response.status_code == 200
    assert page.h1.get_text() == "Трубогиб ТПГ-2Б"
    assert page.title.get_text() == "Трубогиб ТПГ-2Б купить в Астане — Батыс Курылыс XXI"
    assert page.find("meta", attrs={"name": "description"})["content"] == "Для труб до 2 дюймов."
    assert page.find("link", rel="canonical")["href"] == "http://localhost:8000/catalog/pipe-benders/tpg-2b/"
    assert page.select_one(".specs").get_text(" ", strip=True) == "Масса, кг 54"
    assert page.select_one(".prose strong").get_text() == "описание"
    assert "Цена по запросу" in page.select_one(".product__price").get_text()
    product_ld = next(obj for obj in ld_objects(response) if obj["@type"] == "Product")
    assert "offers" not in product_ld
    assert "ИНСТАН" not in response.content.decode()


def test_product_page_cart_and_whatsapp_hooks(client, catalog_data):
    response = client.get("/catalog/pipe-benders/tpg-2b/")
    page = soup(response)
    actions = page.select_one("[data-product]")
    assert actions["data-id"] == str(catalog_data["product"].pk)
    assert actions["data-name"] == "Трубогиб ТПГ-2Б"
    assert actions["data-url"] == "/catalog/pipe-benders/tpg-2b/"
    assert actions.select_one("[data-add-to-quote]") is not None
    assert actions.select_one("input[data-qty]")["max"] == "999"
    whatsapp = page.select_one("a.btn--whatsapp")["href"]
    assert whatsapp.startswith("https://wa.me/77773054243?text=")


def test_product_visible_price(client, catalog_data):
    product = catalog_data["product"]
    product.price = Decimal("150000")
    product.show_price = True
    product.save()
    response = client.get(product.get_absolute_url())
    price_text = soup(response).select_one(".product__price").get_text()
    assert "150" in price_text and "000" in price_text and "₸" in price_text
    product_ld = next(obj for obj in ld_objects(response) if obj["@type"] == "Product")
    assert product_ld["offers"]["price"] == "150000"


def test_product_under_wrong_category_redirects(client, catalog_data):
    make_category(slug="jacks")
    response = client.get("/catalog/jacks/tpg-2b/")
    assert response.status_code == 301
    assert response["Location"] == "/catalog/pipe-benders/tpg-2b/"


@pytest.mark.parametrize(
    "change",
    [
        lambda data: data["product"].__class__.objects.filter(pk=data["product"].pk).update(is_active=False),
        lambda data: data["category"].__class__.objects.filter(pk=data["category"].pk).update(is_active=False),
    ],
)
def test_inactive_product_or_category_is_404(client, catalog_data, change):
    change(catalog_data)
    response = client.get("/catalog/pipe-benders/tpg-2b/")
    assert response.status_code == 404
    assert "Страница не найдена" in response.content.decode()


def test_inactive_category_page_is_404(client, catalog_data):
    catalog_data["category"].__class__.objects.filter(pk=catalog_data["category"].pk).update(is_active=False)
    assert client.get("/catalog/pipe-benders/").status_code == 404


def test_contacts_page(client, catalog_data):
    response = client.get("/contacts/")
    assert response.status_code == 200
    text = response.content.decode()
    assert "Керей Жанибек хандар" in text
    assert "wa.me/77773773763" in text
```

- [ ] **Step 2: Запустить — должны упасть**

Run: `uv run pytest tests/test_catalog_views.py`
Expected: FAIL — `test_home_...` получает 404 (URL ещё нет).

- [ ] **Step 3: Views**

`catalog/views.py`:
```python
from urllib.parse import quote as urlquote

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from catalog import seo
from catalog.models import Category, Product, SiteSettings

HOME_CRUMB = ("Главная", "/")
CATALOG_CRUMB = ("Каталог", "/catalog/")


def public_products():
    return (
        Product.objects.filter(is_active=True, category__is_active=True)
        .select_related("category")
        .prefetch_related("images")
    )


def categories_with_products():
    return (
        Category.objects.filter(is_active=True)
        .annotate(product_count=Count("products", filter=Q(products__is_active=True)))
        .filter(product_count__gt=0)
    )


@require_GET
def home(request):
    site = SiteSettings.load()
    context = {
        "page_title": f"Гидравлический и трубный инструмент в Астане — {site.company_name}",
        "page_description": (
            "Трубогибы, прессы, домкраты, маслостанции, съёмники подшипников и шинообрабатывающее "
            "оборудование в Астане. Запрос коммерческого предложения онлайн."
        ),
        "categories": categories_with_products(),
        "featured": public_products()[:8],
        "local_business": seo.local_business_ld(site),
    }
    return render(request, "catalog/home.html", context)


@require_GET
def catalog_index(request):
    site = SiteSettings.load()
    breadcrumbs = [HOME_CRUMB, CATALOG_CRUMB]
    context = {
        "page_title": f"Каталог инструмента — {site.company_name}",
        "page_description": (
            "Каталог гидравлического и трубного инструмента: трубогибы, прессы, домкраты, маслостанции "
            "и другое оборудование. Цены и сроки — по запросу."
        ),
        "categories": categories_with_products(),
        "breadcrumbs": breadcrumbs,
        "breadcrumbs_ld": seo.breadcrumb_ld(breadcrumbs),
    }
    return render(request, "catalog/index.html", context)


@require_GET
def category_detail(request, slug: str):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    site = SiteSettings.load()
    breadcrumbs = [HOME_CRUMB, CATALOG_CRUMB, (category.name, category.get_absolute_url())]
    context = {
        "category": category,
        "products": public_products().filter(category=category),
        "page_title": seo.category_title(category, site.company_name),
        "page_description": seo.category_description(category),
        "breadcrumbs": breadcrumbs,
        "breadcrumbs_ld": seo.breadcrumb_ld(breadcrumbs),
    }
    return render(request, "catalog/category.html", context)


@require_GET
def product_detail(request, category_slug: str, slug: str):
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related("images", "specs"),
        slug=slug,
        is_active=True,
        category__is_active=True,
    )
    if product.category.slug != category_slug:
        return redirect(product.get_absolute_url(), permanent=True)

    site = SiteSettings.load()
    whatsapp_url = ""
    if site.whatsapp_list:
        text = f"Здравствуйте! Интересует {product.name}: {seo.absolute_url(product.get_absolute_url())}"
        whatsapp_url = f"https://wa.me/{site.whatsapp_list[0]['wa']}?text={urlquote(text)}"

    breadcrumbs = [
        HOME_CRUMB,
        CATALOG_CRUMB,
        (product.category.name, product.category.get_absolute_url()),
        (product.name, product.get_absolute_url()),
    ]
    context = {
        "product": product,
        "images": list(product.images.all()),
        "specs": list(product.specs.all()),
        "related": public_products().filter(category=product.category).exclude(pk=product.pk)[:4],
        "whatsapp_url": whatsapp_url,
        "page_title": seo.product_title(product, site.company_name),
        "page_description": seo.product_description(product),
        "breadcrumbs": breadcrumbs,
        "breadcrumbs_ld": seo.breadcrumb_ld(breadcrumbs),
        "product_ld": seo.product_ld(product),
    }
    return render(request, "catalog/product.html", context)


@require_GET
def contacts(request):
    site = SiteSettings.load()
    breadcrumbs = [HOME_CRUMB, ("Контакты", "/contacts/")]
    context = {
        "page_title": f"Контакты — {site.company_name}",
        "page_description": f"Адрес, телефоны и WhatsApp компании {site.company_name} в Астане.",
        "breadcrumbs": breadcrumbs,
        "breadcrumbs_ld": seo.breadcrumb_ld(breadcrumbs),
        "local_business": seo.local_business_ld(site),
    }
    return render(request, "catalog/contacts.html", context)
```

- [ ] **Step 4: URL-ы**

`catalog/urls.py`:
```python
from django.urls import path

from catalog import views

app_name = "catalog"

urlpatterns = [
    path("", views.home, name="home"),
    path("catalog/", views.catalog_index, name="index"),
    path("catalog/<slug:slug>/", views.category_detail, name="category"),
    path("catalog/<slug:category_slug>/<slug:slug>/", views.product_detail, name="product"),
    path("contacts/", views.contacts, name="contacts"),
]
```

`config/urls.py` (файл целиком):
```python
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("catalog.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

- [ ] **Step 5: Базовый шаблон и include-ы**

```bash
git rm -q templates/.gitkeep
```

`templates/base.html`:
```django
{% load static %}<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}{{ page_title|default:site.company_name }}{% endblock %}</title>
  <meta name="description" content="{{ page_description|default:'' }}">
  <meta name="robots" content="{% block robots %}index, follow{% endblock %}">
  <link rel="canonical" href="{% block canonical %}{{ site_url }}{{ request.path }}{% endblock %}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{{ site.company_name }}">
  <meta property="og:title" content="{{ page_title|default:site.company_name }}">
  <meta property="og:description" content="{{ page_description|default:'' }}">
  <meta property="og:url" content="{{ site_url }}{{ request.path }}">
  {% block og_image %}{% endblock %}
  <link rel="stylesheet" href="{% static 'css/site.css' %}">
  {% block structured_data %}{% endblock %}
  <script src="{% static 'js/cart.js' %}" defer></script>
</head>
<body>
  <a class="skip-link" href="#main">К содержимому</a>
  <header class="site-header">
    <div class="container site-header__inner">
      <a class="logo" href="/">{{ site.company_name }}</a>
      <nav class="nav" aria-label="Основное меню">
        <a href="/catalog/">Каталог</a>
        <a href="/contacts/">Контакты</a>
      </nav>
      <a class="cart-link" href="/quote/">Запрос <span class="cart-count" data-cart-count hidden>0</span></a>
    </div>
  </header>

  <main id="main" class="container">
    {% block content %}{% endblock %}
  </main>

  <footer class="site-footer">
    <div class="container footer-grid">
      <div>
        <h2>{{ site.company_name }}</h2>
        {% if site.address %}<p>{{ site.address }}</p>{% endif %}
        {% if site.bin %}<p>БИН {{ site.bin }}</p>{% endif %}
      </div>
      <div>
        <h2>Каталог</h2>
        <ul>
          {% for category in nav_categories %}
            <li><a href="{{ category.get_absolute_url }}">{{ category.name }}</a></li>
          {% endfor %}
        </ul>
      </div>
      <div>
        <h2>Связаться</h2>
        <ul>
          {% for phone in site.phone_list %}<li><a href="tel:{{ phone|cut:' ' }}">{{ phone }}</a></li>{% endfor %}
          {% for wa in site.whatsapp_list %}<li><a href="https://wa.me/{{ wa.wa }}" target="_blank" rel="noopener">WhatsApp {{ wa.display }}</a></li>{% endfor %}
          {% if site.public_email %}<li><a href="mailto:{{ site.public_email }}">{{ site.public_email }}</a></li>{% endif %}
        </ul>
      </div>
    </div>
  </footer>
</body>
</html>
```

`templates/includes/breadcrumbs.html`:
```django
<nav class="breadcrumbs" aria-label="Навигация">
  <ol>
    {% for name, path in breadcrumbs %}
      {% if forloop.last %}
        <li><span aria-current="page">{{ name }}</span></li>
      {% else %}
        <li><a href="{{ path }}">{{ name }}</a></li>
      {% endif %}
    {% endfor %}
  </ol>
</nav>
```

`templates/includes/product_card.html`:
```django
{% with image=product.main_image %}
<a class="product-card" href="{{ product.get_absolute_url }}">
  <div class="product-card__image">
    {% if image %}
      <img src="{{ image.thumbnail.url }}" alt="{{ image.alt }}" width="400" height="300" loading="lazy">
    {% else %}
      <span class="product-card__placeholder">Нет фото</span>
    {% endif %}
  </div>
  <div class="product-card__body">
    <span class="product-card__name">{{ product.name }}</span>
    {% if product.model_code %}<span class="product-card__model">{{ product.model_code }}</span>{% endif %}
    {% if product.displayed_price is not None %}
      <span class="product-card__price">{{ product.displayed_price|floatformat:"0g" }} ₸</span>
    {% else %}
      <span class="product-card__price price-on-request">Цена по запросу</span>
    {% endif %}
  </div>
</a>
{% endwith %}
```

`templates/404.html`:
```django
{% extends "base.html" %}
{% block title %}Страница не найдена — {{ site.company_name }}{% endblock %}
{% block robots %}noindex, follow{% endblock %}
{% block content %}
  <div class="page-head">
    <h1>Страница не найдена</h1>
    <p>Возможно, товар переименован или снят с продажи.</p>
  </div>
  <p><a class="btn btn--primary" href="/catalog/">Перейти в каталог</a></p>
{% endblock %}
```

- [ ] **Step 6: Шаблоны страниц каталога**

`templates/catalog/home.html`:
```django
{% extends "base.html" %}
{% load seo_tags %}
{% block structured_data %}{% ld_json local_business %}{% endblock %}
{% block content %}
  <section class="hero">
    <h1>Гидравлический и трубный инструмент в Астане</h1>
    <p class="hero__text">Трубогибы, прессы, домкраты, маслостанции, съёмники подшипников и шинообрабатывающее оборудование. Подберём модель под задачу и подготовим коммерческое предложение.</p>
    <div class="hero__actions">
      <a class="btn btn--primary" href="/catalog/">Перейти в каталог</a>
      {% with wa=site.whatsapp_list.0 %}
        {% if wa %}<a class="btn btn--ghost" href="https://wa.me/{{ wa.wa }}" target="_blank" rel="noopener">Написать в WhatsApp</a>{% endif %}
      {% endwith %}
    </div>
  </section>

  <section class="section">
    <div class="section__head"><h2>Категории</h2><a href="/catalog/">Весь каталог</a></div>
    <div class="category-grid">
      {% for category in categories %}
        <a class="category-card" href="{{ category.get_absolute_url }}">
          <span class="category-card__name">{{ category.name }}</span>
          <span class="category-card__count">Товаров: {{ category.product_count }}</span>
        </a>
      {% endfor %}
    </div>
  </section>

  {% if featured %}
    <section class="section">
      <div class="section__head"><h2>Популярные товары</h2></div>
      <div class="product-grid">
        {% for product in featured %}{% include "includes/product_card.html" %}{% endfor %}
      </div>
    </section>
  {% endif %}

  <section class="section">
    <ul class="features">
      <li><strong>Подбор модели</strong>Поможем выбрать инструмент под ваши трубы, нагрузки и условия работы.</li>
      <li><strong>Коммерческое предложение</strong>Соберите список в запросе — пришлём цены и сроки.</li>
      <li><strong>Поставка по Казахстану</strong>Организуем поставку в ваш город.</li>
    </ul>
  </section>
{% endblock %}
```

`templates/catalog/index.html`:
```django
{% extends "base.html" %}
{% load seo_tags %}
{% block structured_data %}{% ld_json breadcrumbs_ld %}{% endblock %}
{% block content %}
  {% include "includes/breadcrumbs.html" %}
  <div class="page-head">
    <h1>Каталог</h1>
    <p>Выберите категорию, добавьте нужные модели в запрос — мы пришлём коммерческое предложение.</p>
  </div>
  <div class="category-grid">
    {% for category in categories %}
      <a class="category-card" href="{{ category.get_absolute_url }}">
        <span class="category-card__name">{{ category.name }}</span>
        <span class="category-card__count">Товаров: {{ category.product_count }}</span>
      </a>
    {% endfor %}
  </div>
{% endblock %}
```

`templates/catalog/category.html`:
```django
{% extends "base.html" %}
{% load seo_tags %}
{% block structured_data %}{% ld_json breadcrumbs_ld %}{% endblock %}
{% block content %}
  {% include "includes/breadcrumbs.html" %}
  <div class="page-head"><h1>{{ category.name }}</h1></div>
  {% if products %}
    <div class="product-grid">
      {% for product in products %}{% include "includes/product_card.html" %}{% endfor %}
    </div>
  {% else %}
    <p class="quote-empty">В этой категории пока нет товаров.</p>
  {% endif %}
  {% if category.seo_text %}
    <section class="panel prose">{{ category.seo_text|safe }}</section>
  {% endif %}
{% endblock %}
```

`templates/catalog/product.html`:
```django
{% extends "base.html" %}
{% load seo_tags %}
{% block og_image %}{% if images %}<meta property="og:image" content="{{ site_url }}{{ images.0.image.url }}">{% endif %}{% endblock %}
{% block structured_data %}{% ld_json product_ld %}{% ld_json breadcrumbs_ld %}{% endblock %}
{% block content %}
  {% include "includes/breadcrumbs.html" %}
  <article class="product">
    <div class="product__gallery">
      <div class="product__main-image">
        {% if images %}
          <img src="{{ images.0.image.url }}" alt="{{ images.0.alt }}" width="800" height="600" fetchpriority="high" data-gallery-main>
        {% else %}
          <span class="product-card__placeholder">Нет фото</span>
        {% endif %}
      </div>
      {% if images|length > 1 %}
        <div class="product__thumbs">
          {% for image in images %}
            <button type="button" data-gallery-thumb data-full="{{ image.image.url }}" data-alt="{{ image.alt }}" aria-label="Фото {{ forloop.counter }}"{% if forloop.first %} aria-current="true"{% endif %}>
              <img src="{{ image.thumbnail.url }}" alt="" width="64" height="64" loading="lazy">
            </button>
          {% endfor %}
        </div>
      {% endif %}
    </div>

    <div class="product__info">
      <h1>{{ product.name }}</h1>
      {% if product.model_code %}<p class="product__model">Модель: {{ product.model_code }}</p>{% endif %}
      {% if product.short_description %}<p class="product__short">{{ product.short_description }}</p>{% endif %}
      {% if product.displayed_price is not None %}
        <p class="product__price">{{ product.displayed_price|floatformat:"0g" }} ₸</p>
      {% else %}
        <p class="product__price price-on-request">Цена по запросу</p>
      {% endif %}
      <div class="product__actions" data-product data-id="{{ product.pk }}" data-name="{{ product.name }}" data-url="{{ product.get_absolute_url }}" data-thumb="{% if images %}{{ images.0.thumbnail.url }}{% endif %}">
        <div class="qty">
          <label class="visually-hidden" for="qty-{{ product.pk }}">Количество</label>
          <input id="qty-{{ product.pk }}" type="number" inputmode="numeric" min="1" max="999" value="1" data-qty>
        </div>
        <button type="button" class="btn btn--primary" data-add-to-quote>Добавить в запрос</button>
        {% if whatsapp_url %}<a class="btn btn--whatsapp" href="{{ whatsapp_url }}" target="_blank" rel="noopener">Спросить в WhatsApp</a>{% endif %}
      </div>
      <p class="note">Добавьте товары в запрос — мы свяжемся с вами и пришлём коммерческое предложение.</p>
    </div>
  </article>

  {% if specs %}
    <section class="panel">
      <h2>Характеристики</h2>
      <table class="specs">
        <tbody>
          {% for spec in specs %}<tr><th scope="row">{{ spec.name }}</th><td>{{ spec.value }}</td></tr>{% endfor %}
        </tbody>
      </table>
    </section>
  {% endif %}

  {% if product.description %}
    <section class="panel prose">
      <h2>Описание</h2>
      {{ product.description|safe }}
    </section>
  {% endif %}

  {% if related %}
    <section class="section">
      <div class="section__head"><h2>Похожие товары</h2></div>
      <div class="product-grid">
        {% for product in related %}{% include "includes/product_card.html" %}{% endfor %}
      </div>
    </section>
  {% endif %}
{% endblock %}
```

`templates/catalog/contacts.html`:
```django
{% extends "base.html" %}
{% load seo_tags %}
{% block structured_data %}{% ld_json local_business %}{% ld_json breadcrumbs_ld %}{% endblock %}
{% block content %}
  {% include "includes/breadcrumbs.html" %}
  <div class="page-head"><h1>Контакты</h1></div>
  <section class="panel">
    <ul class="contacts-list">
      {% if site.address %}<li><strong>Адрес</strong>{{ site.address }}{% if site.map_url %} · <a href="{{ site.map_url }}" target="_blank" rel="noopener">на карте</a>{% endif %}</li>{% endif %}
      {% for phone in site.phone_list %}<li><strong>Телефон</strong><a href="tel:{{ phone|cut:' ' }}">{{ phone }}</a></li>{% endfor %}
      {% for wa in site.whatsapp_list %}<li><strong>WhatsApp</strong><a href="https://wa.me/{{ wa.wa }}" target="_blank" rel="noopener">{{ wa.display }}</a></li>{% endfor %}
      {% if site.public_email %}<li><strong>Email</strong><a href="mailto:{{ site.public_email }}">{{ site.public_email }}</a></li>{% endif %}
      {% if site.working_hours %}<li><strong>Часы работы</strong>{{ site.working_hours }}</li>{% endif %}
      {% if site.bin %}<li><strong>БИН</strong>{{ site.bin }}</li>{% endif %}
    </ul>
  </section>
{% endblock %}
```

- [ ] **Step 7: Запустить тесты**

Run: `uv run pytest tests/test_catalog_views.py`
Expected: `11 passed`.

- [ ] **Step 8: Ручная проверка**

```bash
uv run python manage.py runserver
```
Через админку создать категорию и товар с фото, открыть `/`, `/catalog/`, страницу категории и товара на 1280 и 360 px. Вид совпадает с согласованным макетом (Task 6); в консоли браузера допускается только 404 на `cart.js` (файл появится в Task 14).

- [ ] **Step 9: Commit**

```bash
git add catalog config/urls.py templates tests/test_catalog_views.py
git commit -m "feat(catalog): add server-rendered home, catalog, product and contacts pages"
```

---
### Task 9: Sitemap и robots.txt

**Files:**
- Create: `catalog/sitemaps.py`
- Modify: `catalog/views.py` (добавить `robots_txt`), `config/urls.py`
- Test: `tests/test_sitemap_robots.py`

**Interfaces:**
- Consumes: `Category`, `Product`.
- Produces: `catalog.sitemaps.SITEMAPS: dict[str, type[Sitemap]]`; view `catalog.views.robots_txt`; URL names `sitemap`, `robots`.

> Спека §8 (уточнено): `robots.txt` **не** содержит `Disallow` для админки — иначе в публичном файле раскрывается секретный `ADMIN_URL`. Админка не индексируется, так как требует входа и нигде не ссылается.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_sitemap_robots.py`:
```python
import pytest
from django.conf import settings

from tests.factories import make_category, make_product

pytestmark = pytest.mark.django_db


def test_sitemap_contains_only_public_pages(client):
    active = make_category(slug="pipe-benders")
    hidden = make_category(slug="hidden", is_active=False)
    make_category(slug="empty")
    make_product(category=active, slug="tpg-2b")
    make_product(category=active, slug="old-model", is_active=False)
    make_product(category=hidden, slug="in-hidden")

    response = client.get("/sitemap.xml")
    body = response.content.decode()

    assert response.status_code == 200
    assert "/catalog/pipe-benders/</loc>" in body
    assert "/catalog/pipe-benders/tpg-2b/</loc>" in body
    assert "/contacts/</loc>" in body
    assert "<lastmod>" in body
    assert "old-model" not in body
    assert "hidden" not in body
    assert "/catalog/empty/" not in body


def test_robots_txt(client):
    response = client.get("/robots.txt")
    body = response.content.decode()
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    assert "User-agent: *" in body
    assert "Disallow: /quote/" in body
    assert "Sitemap: http://localhost:8000/sitemap.xml" in body
    assert settings.ADMIN_URL not in body
```

- [ ] **Step 2: Запустить — должны упасть**

Run: `uv run pytest tests/test_sitemap_robots.py`
Expected: FAIL, 404 на `/sitemap.xml`.

- [ ] **Step 3: Реализация sitemap**

`catalog/sitemaps.py`:
```python
from django.contrib.sitemaps import Sitemap
from django.db.models import Max, Q

from catalog.models import Category, Product


class StaticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return ["/", "/catalog/", "/contacts/"]

    def location(self, item: str) -> str:
        return item


class CategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return (
            Category.objects.filter(is_active=True)
            .annotate(last_modified=Max("products__updated_at", filter=Q(products__is_active=True)))
            .filter(last_modified__isnull=False)
        )

    def lastmod(self, obj):
        return obj.last_modified


class ProductSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return Product.objects.filter(is_active=True, category__is_active=True).select_related("category")

    def lastmod(self, obj):
        return obj.updated_at


SITEMAPS = {"static": StaticSitemap, "categories": CategorySitemap, "products": ProductSitemap}
```

- [ ] **Step 4: Реализация robots.txt**

В `catalog/views.py` добавить импорты в начало файла:
```python
from django.conf import settings
from django.http import HttpResponse
```

И в конец файла:
```python
@require_GET
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /quote/",
        "",
        f"Sitemap: {settings.SITE_URL}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")
```

`config/urls.py` (файл целиком):
```python
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from catalog.sitemaps import SITEMAPS
from catalog.views import robots_txt

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("robots.txt", robots_txt, name="robots"),
    path("", include("catalog.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

- [ ] **Step 5: Запустить тесты**

Run: `uv run pytest tests/test_sitemap_robots.py`
Expected: `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add catalog config/urls.py tests/test_sitemap_robots.py
git commit -m "feat(catalog): add sitemap.xml and robots.txt"
```

---

### Task 10: Модели заявок и валидация

**Files:**
- Create: `orders/models.py`, `orders/services.py`
- Create (generated): `orders/migrations/0001_initial.py`
- Test: `tests/test_orders_services.py`

**Interfaces:**
- Consumes: `Product` (активность товара и категории).
- Produces:
  - `QuoteRequest(name, phone, status, admin_note, email_sent, source_ip, created_at)`; `QuoteRequest.Status` с `NEW="new"`, `IN_PROGRESS="in_progress"`, `CLOSED="closed"`; related name позиций `items`.
  - `QuoteItem(request, product: Product | None, product_name, quantity)`.
  - `orders.services.MAX_ITEMS = 50`, `MAX_QTY = 999`.
  - `orders.services.normalize_phone(raw: str | None) -> str | None`.
  - `orders.services.ItemsError(ValueError)`.
  - `orders.services.parse_items(raw: str | None) -> list[tuple[Product, int]]` — бросает `ItemsError` с текстом для пользователя.

> Уточнение к спеке §6: кроме `8…`, `7…`, `+7…` принимается и 10-значный номер, начинающийся с `7` (`777 305 4243`), — так пользователи часто вводят казахстанские номера.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_orders_services.py`:
```python
import json

import pytest
from django.contrib.auth.models import Group

from catalog.roles import MANAGER_GROUP
from orders.services import ItemsError, normalize_phone, parse_items
from tests.factories import make_category, make_product


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+7 777 305 42 43", "+77773054243"),
        ("87773054243", "+77773054243"),
        ("7 (777) 305-42-43", "+77773054243"),
        ("777 305 4243", "+77773054243"),
        ("+7 7172 00 00 00", "+77172000000"),
    ],
)
def test_normalize_phone_valid(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "12345", "+1 202 555 0100", "99773054243", "8777305424", "+7777305424311"])
def test_normalize_phone_invalid(raw):
    assert normalize_phone(raw) is None


def items(*pairs) -> str:
    return json.dumps([{"id": pid, "qty": qty} for pid, qty in pairs])


@pytest.mark.django_db
def test_parse_items_returns_products_with_quantities_in_input_order():
    first, second = make_product(), make_product()
    assert parse_items(items((second.pk, 2), (first.pk, 1))) == [(second, 2), (first, 1)]


@pytest.mark.django_db
def test_parse_items_sums_duplicates_and_caps_at_999():
    product = make_product()
    assert parse_items(items((product.pk, 3), (product.pk, 4))) == [(product, 7)]
    assert parse_items(items((product.pk, 600), (product.pk, 600))) == [(product, 999)]


@pytest.mark.django_db
def test_parse_items_drops_unknown_and_inactive_products():
    active = make_product()
    inactive = make_product(is_active=False)
    in_hidden_category = make_product(category=make_category(is_active=False))
    result = parse_items(items((active.pk, 1), (inactive.pk, 1), (in_hidden_category.pk, 1), (999999, 1)))
    assert result == [(active, 1)]


@pytest.mark.django_db
def test_parse_items_error_when_nothing_available():
    with pytest.raises(ItemsError, match="Корзина пуста или товары недоступны"):
        parse_items(items((999999, 1)))


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (None, "Некорректный список товаров"),
        ("not json", "Некорректный список товаров"),
        ("{}", "от 1 до 50 позиций"),
        ("[]", "от 1 до 50 позиций"),
        (json.dumps([{"id": i, "qty": 1} for i in range(51)]), "от 1 до 50 позиций"),
        (json.dumps([{"id": "1", "qty": 1}]), "Некорректный список товаров"),
        (json.dumps([{"id": 1, "qty": True}]), "Некорректный список товаров"),
        (json.dumps([{"id": 1, "qty": 0}]), "от 1 до 999"),
        (json.dumps([{"id": 1, "qty": 1000}]), "от 1 до 999"),
        (json.dumps([1, 2]), "Некорректный список товаров"),
    ],
)
def test_parse_items_rejects_bad_payload(raw, message):
    with pytest.raises(ItemsError, match=message):
        parse_items(raw)


@pytest.mark.django_db
def test_manager_group_has_orders_permissions():
    codenames = set(Group.objects.get(name=MANAGER_GROUP).permissions.values_list("codename", flat=True))
    assert {"change_quoterequest", "view_quoteitem"} <= codenames
```

- [ ] **Step 2: Запустить — должны упасть**

Run: `uv run pytest tests/test_orders_services.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'orders.services'`.

- [ ] **Step 3: Модели**

`orders/models.py`:
```python
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from catalog.models import Product


class QuoteRequest(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Новая"
        IN_PROGRESS = "in_progress", "В работе"
        CLOSED = "closed", "Закрыта"

    name = models.CharField("Имя", max_length=100)
    phone = models.CharField("Телефон", max_length=16)
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    admin_note = models.TextField("Заметка менеджера", blank=True)
    email_sent = models.BooleanField("Письмо отправлено", default=False)
    source_ip = models.GenericIPAddressField("IP", null=True, blank=True)
    created_at = models.DateTimeField("Создана", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "заявка"
        verbose_name_plural = "заявки"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Заявка №{self.pk} — {self.name}"


class QuoteItem(models.Model):
    request = models.ForeignKey(QuoteRequest, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", verbose_name="Товар"
    )
    product_name = models.CharField("Название на момент заявки", max_length=255)
    quantity = models.PositiveIntegerField(
        "Количество", validators=[MinValueValidator(1), MaxValueValidator(999)]
    )

    class Meta:
        verbose_name = "позиция"
        verbose_name_plural = "позиции"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product_name} × {self.quantity}"
```

- [ ] **Step 4: Сервисы валидации**

`orders/services.py`:
```python
import json
import re

from catalog.models import Product

MAX_ITEMS = 50
MAX_QTY = 999


class ItemsError(ValueError):
    """Ошибка в списке позиций; текст показывается пользователю."""


def normalize_phone(raw: str | None) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10 and digits.startswith("7"):
        digits = "7" + digits
    elif len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if len(digits) != 11 or digits[0] != "7":
        return None
    return f"+{digits}"


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_items(raw: str | None) -> list[tuple[Product, int]]:
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ItemsError("Некорректный список товаров.") from exc

    if not isinstance(data, list) or not 1 <= len(data) <= MAX_ITEMS:
        raise ItemsError(f"В заявке должно быть от 1 до {MAX_ITEMS} позиций.")

    quantities: dict[int, int] = {}
    for entry in data:
        if not isinstance(entry, dict) or not _is_int(entry.get("id")) or not _is_int(entry.get("qty")):
            raise ItemsError("Некорректный список товаров.")
        if not 1 <= entry["qty"] <= MAX_QTY:
            raise ItemsError(f"Количество должно быть от 1 до {MAX_QTY}.")
        quantities[entry["id"]] = quantities.get(entry["id"], 0) + entry["qty"]

    products = Product.objects.filter(pk__in=quantities, is_active=True, category__is_active=True).in_bulk()
    result = [(products[pk], min(qty, MAX_QTY)) for pk, qty in quantities.items() if pk in products]
    if not result:
        raise ItemsError("Корзина пуста или товары недоступны.")
    return result
```

- [ ] **Step 5: Миграция и тесты**

```bash
uv run python manage.py makemigrations orders
uv run pytest tests/test_orders_services.py
```
Expected: создана `orders/migrations/0001_initial.py`; `27 passed`.

- [ ] **Step 6: Commit**

```bash
git add orders tests/test_orders_services.py
git commit -m "feat(orders): add quote request models, phone normalization and items validation"
```

---
### Task 11: Админка заявок

**Files:**
- Create: `orders/admin.py`
- Test: `tests/test_orders_admin.py`

**Interfaces:**
- Consumes: `QuoteRequest`, `QuoteItem` (Task 10), фикстура `superuser` (Task 5).
- Produces: URL `admin:orders_quoterequest_change` (используется в письме, Task 12); действия `mark_in_progress`, `mark_closed`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_orders_admin.py`:
```python
import pytest
from django.conf import settings

from orders.models import QuoteItem, QuoteRequest
from tests.factories import make_product

pytestmark = pytest.mark.django_db

URL = f"/{settings.ADMIN_URL}orders/quoterequest/"


@pytest.fixture
def quote():
    product = make_product(name="Домкрат ДА5")
    request = QuoteRequest.objects.create(name="Иван", phone="+77773054243")
    QuoteItem.objects.create(request=request, product=product, product_name=product.name, quantity=3)
    return request


def test_changelist_shows_request(client, superuser, quote):
    client.force_login(superuser)
    response = client.get(URL)
    body = response.content.decode()
    assert response.status_code == 200
    assert "Иван" in body
    assert 'href="tel:+77773054243"' in body


def test_change_page_shows_items_read_only(client, superuser, quote):
    client.force_login(superuser)
    response = client.get(f"{URL}{quote.pk}/change/")
    body = response.content.decode()
    assert response.status_code == 200
    assert "Домкрат ДА5" in body
    assert 'name="items-0-quantity"' not in body


def test_requests_cannot_be_added_in_admin(client, superuser):
    client.force_login(superuser)
    assert client.get(f"{URL}add/").status_code == 403


@pytest.mark.parametrize(
    ("action", "status"),
    [("mark_in_progress", QuoteRequest.Status.IN_PROGRESS), ("mark_closed", QuoteRequest.Status.CLOSED)],
)
def test_status_actions(client, superuser, quote, action, status):
    client.force_login(superuser)
    response = client.post(URL, {"action": action, "_selected_action": [quote.pk]})
    assert response.status_code == 302
    quote.refresh_from_db()
    assert quote.status == status
```

- [ ] **Step 2: Запустить — должны упасть**

Run: `uv run pytest tests/test_orders_admin.py`
Expected: FAIL — changelist отвечает 404 (модель не зарегистрирована).

- [ ] **Step 3: Реализация**

`orders/admin.py`:
```python
from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from orders.models import QuoteItem, QuoteRequest


class QuoteItemInline(admin.TabularInline):
    model = QuoteItem
    extra = 0
    can_delete = False
    fields = ("product_name", "quantity", "product_link")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None) -> bool:
        return False

    @admin.display(description="Товар на сайте")
    def product_link(self, obj: QuoteItem) -> str:
        if obj.product_id and obj.product:
            return format_html('<a href="{}" target="_blank" rel="noopener">открыть</a>', obj.product.get_absolute_url())
        return "удалён"


@admin.register(QuoteRequest)
class QuoteRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "name", "phone_link", "items_count", "status", "email_sent")
    list_display_links = ("id", "name")
    list_editable = ("status",)
    list_filter = ("status", "email_sent", ("created_at", admin.DateFieldListFilter))
    search_fields = ("name", "phone")
    fields = ("created_at", "name", "phone", "status", "admin_note", "email_sent", "source_ip")
    readonly_fields = ("created_at", "name", "phone", "email_sent", "source_ip")
    inlines = (QuoteItemInline,)
    actions = ("mark_in_progress", "mark_closed")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_items_count=Count("items"))

    def has_add_permission(self, request) -> bool:
        return False

    @admin.display(description="Телефон", ordering="phone")
    def phone_link(self, obj: QuoteRequest) -> str:
        return format_html('<a href="tel:{}">{}</a>', obj.phone, obj.phone)

    @admin.display(description="Позиций", ordering="_items_count")
    def items_count(self, obj: QuoteRequest) -> int:
        return obj._items_count

    @admin.action(description="Отметить «В работе»")
    def mark_in_progress(self, request, queryset) -> None:
        queryset.update(status=QuoteRequest.Status.IN_PROGRESS)

    @admin.action(description="Отметить «Закрыта»")
    def mark_closed(self, request, queryset) -> None:
        queryset.update(status=QuoteRequest.Status.CLOSED)
```

- [ ] **Step 4: Запустить тесты**

Run: `uv run pytest tests/test_orders_admin.py`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add orders/admin.py tests/test_orders_admin.py
git commit -m "feat(orders): add quote requests admin with statuses and read-only items"
```

---

### Task 12: Создание заявки и письмо администратору

**Files:**
- Create: `orders/notifications.py`
- Modify: `orders/services.py` (файл целиком ниже — добавлена `create_quote`)
- Test: `tests/test_orders_notifications.py`

**Interfaces:**
- Consumes: `SiteSettings.load().notification_email`, `settings.ADMIN_EMAIL`, `settings.SITE_URL`, URL `admin:orders_quoterequest_change`, `parse_items` результат `list[tuple[Product, int]]`.
- Produces:
  - `orders.services.create_quote(name: str, phone: str, items: list[tuple[Product, int]], source_ip: str | None) -> QuoteRequest` — сохраняет в транзакции и планирует письмо через `transaction.on_commit`.
  - `orders.notifications.send_quote_notification(request_id: int) -> bool` — `True`, если письмо ушло (и выставлен `email_sent=True`).

- [ ] **Step 1: Написать падающие тесты**

`tests/test_orders_notifications.py`:
```python
import logging

import pytest
from django.core import mail

from catalog.models import SiteSettings
from orders import notifications
from orders.models import QuoteRequest
from orders.services import create_quote
from tests.factories import make_category, make_product

pytestmark = pytest.mark.django_db


@pytest.fixture
def recipient():
    site = SiteSettings.load()
    site.notification_email = "sales@example.com"
    site.save()
    return site.notification_email


@pytest.fixture
def products():
    category = make_category(slug="jacks")
    return (
        make_product(category=category, name="Домкрат ДА5", slug="da-5"),
        make_product(category=category, name="Домкрат ДГ", slug="dg"),
    )


def test_create_quote_saves_items_and_sends_email(
    recipient, products, django_capture_on_commit_callbacks, settings
):
    first, second = products
    with django_capture_on_commit_callbacks(execute=True):
        quote = create_quote("Иван", "+77773054243", [(first, 2), (second, 1)], "203.0.113.5")

    quote.refresh_from_db()
    assert quote.status == QuoteRequest.Status.NEW
    assert quote.source_ip == "203.0.113.5"
    assert quote.email_sent is True
    assert [(i.product_name, i.quantity) for i in quote.items.all()] == [("Домкрат ДА5", 2), ("Домкрат ДГ", 1)]

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["sales@example.com"]
    assert message.subject == f"Заявка №{quote.pk} — Иван"
    assert "+77773054243" in message.body
    assert "Домкрат ДА5 — 2 шт. http://localhost:8000/catalog/jacks/da-5/" in message.body
    assert f"http://localhost:8000/{settings.ADMIN_URL}orders/quoterequest/{quote.pk}/change/" in message.body


def test_email_not_sent_before_commit(recipient, products, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        create_quote("Иван", "+77773054243", [(products[0], 1)], None)
    assert len(callbacks) == 1
    assert mail.outbox == []


def test_fallback_to_admin_email_setting(settings, products, django_capture_on_commit_callbacks):
    settings.ADMIN_EMAIL = "fallback@example.com"
    with django_capture_on_commit_callbacks(execute=True):
        create_quote("Иван", "+77773054243", [(products[0], 1)], None)
    assert mail.outbox[0].to == ["fallback@example.com"]


def test_no_recipient_logs_error_and_keeps_request(settings, products, caplog, django_capture_on_commit_callbacks):
    settings.ADMIN_EMAIL = ""
    with caplog.at_level(logging.ERROR, logger="orders.notifications"):
        with django_capture_on_commit_callbacks(execute=True):
            quote = create_quote("Иван", "+77773054243", [(products[0], 1)], None)
    quote.refresh_from_db()
    assert quote.email_sent is False
    assert mail.outbox == []
    assert "no notification recipient" in caplog.text


def test_smtp_failure_keeps_request_unsent(recipient, products, monkeypatch, caplog, django_capture_on_commit_callbacks):
    def broken_send_mail(**kwargs):
        raise OSError("SMTP down")

    monkeypatch.setattr(notifications, "send_mail", broken_send_mail)
    with caplog.at_level(logging.ERROR, logger="orders.notifications"):
        with django_capture_on_commit_callbacks(execute=True):
            quote = create_quote("Иван", "+77773054243", [(products[0], 1)], None)
    quote.refresh_from_db()
    assert QuoteRequest.objects.filter(pk=quote.pk).exists()
    assert quote.email_sent is False
    assert "failed to send notification" in caplog.text


def test_deleted_product_still_listed_by_snapshot_name(recipient, products, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=False):
        quote = create_quote("Иван", "+77773054243", [(products[0], 4)], None)
    products[0].delete()
    assert notifications.send_quote_notification(quote.pk) is True
    assert "Домкрат ДА5 — 4 шт." in mail.outbox[0].body
```

- [ ] **Step 2: Запустить — должны упасть**

Run: `uv run pytest tests/test_orders_notifications.py`
Expected: FAIL, `ImportError: cannot import name 'notifications' from 'orders'`.

- [ ] **Step 3: Реализация уведомления**

`orders/notifications.py`:
```python
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from catalog.models import SiteSettings
from orders.models import QuoteRequest

logger = logging.getLogger(__name__)


def send_quote_notification(request_id: int) -> bool:
    quote = QuoteRequest.objects.prefetch_related("items__product__category").get(pk=request_id)
    recipient = SiteSettings.load().notification_email or settings.ADMIN_EMAIL
    if not recipient:
        logger.error("Quote %s: no notification recipient configured", quote.pk)
        return False

    lines = [f"Имя: {quote.name}", f"Телефон: {quote.phone}", "", "Позиции:"]
    for item in quote.items.all():
        link = f" {settings.SITE_URL}{item.product.get_absolute_url()}" if item.product else ""
        lines.append(f"- {item.product_name} — {item.quantity} шт.{link}")
    admin_link = settings.SITE_URL + reverse("admin:orders_quoterequest_change", args=[quote.pk])
    lines += ["", f"Открыть заявку в админке: {admin_link}"]

    try:
        send_mail(
            subject=f"Заявка №{quote.pk} — {quote.name}",
            message="\n".join(lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Quote %s: failed to send notification", quote.pk)
        return False

    QuoteRequest.objects.filter(pk=quote.pk).update(email_sent=True)
    return True
```

- [ ] **Step 4: Добавить `create_quote`**

`orders/services.py` (файл целиком):
```python
import json
import re

from django.db import transaction

from catalog.models import Product
from orders.models import QuoteItem, QuoteRequest

MAX_ITEMS = 50
MAX_QTY = 999


class ItemsError(ValueError):
    """Ошибка в списке позиций; текст показывается пользователю."""


def normalize_phone(raw: str | None) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10 and digits.startswith("7"):
        digits = "7" + digits
    elif len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if len(digits) != 11 or digits[0] != "7":
        return None
    return f"+{digits}"


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_items(raw: str | None) -> list[tuple[Product, int]]:
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ItemsError("Некорректный список товаров.") from exc

    if not isinstance(data, list) or not 1 <= len(data) <= MAX_ITEMS:
        raise ItemsError(f"В заявке должно быть от 1 до {MAX_ITEMS} позиций.")

    quantities: dict[int, int] = {}
    for entry in data:
        if not isinstance(entry, dict) or not _is_int(entry.get("id")) or not _is_int(entry.get("qty")):
            raise ItemsError("Некорректный список товаров.")
        if not 1 <= entry["qty"] <= MAX_QTY:
            raise ItemsError(f"Количество должно быть от 1 до {MAX_QTY}.")
        quantities[entry["id"]] = quantities.get(entry["id"], 0) + entry["qty"]

    products = Product.objects.filter(pk__in=quantities, is_active=True, category__is_active=True).in_bulk()
    result = [(products[pk], min(qty, MAX_QTY)) for pk, qty in quantities.items() if pk in products]
    if not result:
        raise ItemsError("Корзина пуста или товары недоступны.")
    return result


def create_quote(
    name: str, phone: str, items: list[tuple[Product, int]], source_ip: str | None
) -> QuoteRequest:
    from orders.notifications import send_quote_notification

    with transaction.atomic():
        quote = QuoteRequest.objects.create(name=name, phone=phone, source_ip=source_ip)
        QuoteItem.objects.bulk_create(
            [QuoteItem(request=quote, product=product, product_name=product.name, quantity=qty) for product, qty in items]
        )
        transaction.on_commit(lambda: send_quote_notification(quote.pk))
    return quote
```

- [ ] **Step 5: Запустить тесты**

Run: `uv run pytest tests/test_orders_notifications.py tests/test_orders_services.py`
Expected: `6 passed` + `27 passed`.

- [ ] **Step 6: Commit**

```bash
git add orders tests/test_orders_notifications.py
git commit -m "feat(orders): create quote requests atomically and email admin after commit"
```

---
### Task 13: Страница запроса и приём заявки

**Files:**
- Create: `orders/forms.py`, `orders/views.py`, `orders/urls.py`, `templates/orders/quote.html`, `templates/orders/thanks.html`
- Modify: `config/urls.py`
- Test: `tests/test_quote_view.py`

**Interfaces:**
- Consumes: `normalize_phone`, `parse_items`, `ItemsError`, `create_quote` (Tasks 10, 12), `SiteSettings`.
- Produces:
  - URL names `orders:quote` (`/quote/`), `orders:thanks` (`/quote/thanks/`).
  - `orders.forms.QuoteForm` с полями `name`, `phone`, `items` (hidden), `website` (honeypot); метод `is_spam() -> bool`.
  - `orders.views.client_ip(request) -> str | None`, `RATE_LIMIT = 5`, `RATE_WINDOW_SECONDS = 3600`.
  - Разметка для `cart.js` (Task 14): `ul[data-quote-list]`, `p[data-quote-empty]`, `form[data-quote-form]` со скрытым `input[name="items"]`, `button[data-quote-submit]`; на странице «спасибо» — `div[data-cart-clear]`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_quote_view.py`:
```python
import json

import pytest
from bs4 import BeautifulSoup
from django.core import mail

from orders.models import QuoteRequest
from tests.factories import make_product

pytestmark = pytest.mark.django_db


@pytest.fixture
def product():
    return make_product(name="Трубогиб ТПГ-2Б")


def payload(product, **overrides) -> dict:
    data = {
        "name": "Иван",
        "phone": "8 777 305 42 43",
        "items": json.dumps([{"id": product.pk, "qty": 2}]),
        "website": "",
    }
    data.update(overrides)
    return data


def test_get_renders_form_with_noindex(client):
    response = client.get("/quote/")
    page = BeautifulSoup(response.content, "html.parser")
    assert response.status_code == 200
    assert page.find("meta", attrs={"name": "robots"})["content"] == "noindex, follow"
    assert page.select_one("form[data-quote-form] input[name='items']") is not None
    assert page.select_one("[data-quote-list]") is not None


def test_valid_submission_creates_request_and_redirects(client, product, django_capture_on_commit_callbacks, settings):
    settings.ADMIN_EMAIL = "sales@example.com"
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post("/quote/", payload(product))
    quote = QuoteRequest.objects.get()
    assert response.status_code == 302
    assert response["Location"] == f"/quote/thanks/?id={quote.pk}"
    assert quote.phone == "+77773054243"
    assert quote.source_ip == "127.0.0.1"
    assert [(i.product_name, i.quantity) for i in quote.items.all()] == [("Трубогиб ТПГ-2Б", 2)]
    assert len(mail.outbox) == 1


def test_forwarded_ip_is_stored(client, product):
    client.post("/quote/", payload(product), HTTP_X_FORWARDED_FOR="203.0.113.7")
    assert QuoteRequest.objects.get().source_ip == "203.0.113.7"


def test_garbage_forwarded_ip_is_ignored(client, product):
    client.post("/quote/", payload(product), HTTP_X_FORWARDED_FOR="not-an-ip")
    assert QuoteRequest.objects.get().source_ip is None


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"phone": "12345"}, "Укажите телефон в формате +7 XXX XXX XX XX."),
        ({"name": "И"}, "Имя слишком короткое."),
        ({"name": "Иван\nBcc: x@example.com"}, "Имя содержит недопустимые символы."),
        ({"items": ""}, "Добавьте товары в запрос."),
        ({"items": json.dumps([{"id": 999999, "qty": 1}])}, "Корзина пуста или товары недоступны."),
    ],
)
def test_invalid_submission_shows_error(client, product, overrides, error):
    response = client.post("/quote/", payload(product, **overrides))
    assert response.status_code == 200
    assert error in response.content.decode()
    assert QuoteRequest.objects.count() == 0


def test_honeypot_pretends_success_without_saving(client, product):
    response = client.post("/quote/", payload(product, website="https://spam.example"))
    assert response.status_code == 302
    assert response["Location"] == "/quote/thanks/"
    assert QuoteRequest.objects.count() == 0
    assert mail.outbox == []


def test_sixth_submission_within_hour_is_rejected(client, product):
    for _ in range(5):
        assert client.post("/quote/", payload(product)).status_code == 302
    response = client.post("/quote/", payload(product))
    assert response.status_code == 200
    assert "Слишком много заявок" in response.content.decode()
    assert QuoteRequest.objects.count() == 5


def test_rate_limit_is_per_ip(client, product):
    for _ in range(5):
        client.post("/quote/", payload(product), HTTP_X_FORWARDED_FOR="203.0.113.1")
    response = client.post("/quote/", payload(product), HTTP_X_FORWARDED_FOR="203.0.113.2")
    assert response.status_code == 302


def test_thanks_page(client):
    response = client.get("/quote/thanks/?id=42")
    body = response.content.decode()
    assert response.status_code == 200
    assert "№42" in body
    assert "data-cart-clear" in body
    assert "№" not in client.get("/quote/thanks/?id=abc").content.decode()
```

- [ ] **Step 2: Запустить — должны упасть**

Run: `uv run pytest tests/test_quote_view.py`
Expected: FAIL — `/quote/` отвечает 404.

- [ ] **Step 3: Форма**

`orders/forms.py`:
```python
import re

from django import forms

from orders.services import ItemsError, normalize_phone, parse_items


class QuoteForm(forms.Form):
    name = forms.CharField(
        label="Имя",
        min_length=2,
        max_length=100,
        error_messages={
            "required": "Укажите имя.",
            "min_length": "Имя слишком короткое.",
            "max_length": "Имя слишком длинное.",
        },
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    phone = forms.CharField(
        label="Телефон",
        max_length=32,
        error_messages={"required": "Укажите телефон."},
        widget=forms.TextInput(attrs={"type": "tel", "autocomplete": "tel", "placeholder": "+7 777 305 4243"}),
    )
    items = forms.CharField(required=False, widget=forms.HiddenInput)
    website = forms.CharField(
        required=False, label="Сайт", widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"})
    )

    def clean_name(self) -> str:
        name = self.cleaned_data["name"]
        if re.search(r"[\x00-\x1f\x7f]", name):
            raise forms.ValidationError("Имя содержит недопустимые символы.")
        return name

    def clean_phone(self) -> str:
        phone = normalize_phone(self.cleaned_data["phone"])
        if phone is None:
            raise forms.ValidationError("Укажите телефон в формате +7 XXX XXX XX XX.")
        return phone

    def clean_items(self):
        raw = self.cleaned_data.get("items")
        if not raw:
            raise forms.ValidationError("Добавьте товары в запрос.")
        try:
            return parse_items(raw)
        except ItemsError as exc:
            raise forms.ValidationError(str(exc)) from exc

    def is_spam(self) -> bool:
        return bool(self.data.get("website", "").strip())
```

- [ ] **Step 4: Views и URL-ы**

`orders/views.py`:
```python
import ipaddress

from django.core.cache import cache
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from catalog.models import SiteSettings
from orders.forms import QuoteForm
from orders.services import create_quote

RATE_LIMIT = 5
RATE_WINDOW_SECONDS = 3600


def client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    candidate = forwarded.split(",")[-1].strip() if forwarded else request.META.get("REMOTE_ADDR", "")
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def _rate_key(ip: str | None) -> str:
    return f"quote-rate:{ip or 'unknown'}"


def _is_rate_limited(ip: str | None) -> bool:
    return cache.get(_rate_key(ip), 0) >= RATE_LIMIT


def _register_submission(ip: str | None) -> None:
    key = _rate_key(ip)
    if cache.add(key, 1, RATE_WINDOW_SECONDS):
        return
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, RATE_WINDOW_SECONDS)


@require_http_methods(["GET", "POST"])
def quote(request):
    if request.method == "POST":
        form = QuoteForm(request.POST)
        if form.is_spam():
            return redirect("orders:thanks")
        ip = client_ip(request)
        if _is_rate_limited(ip):
            form.add_error(None, "Слишком много заявок. Попробуйте позже или напишите нам в WhatsApp.")
        elif form.is_valid():
            quote_request = create_quote(
                form.cleaned_data["name"], form.cleaned_data["phone"], form.cleaned_data["items"], ip
            )
            _register_submission(ip)
            return redirect(f"{reverse('orders:thanks')}?id={quote_request.pk}")
    else:
        form = QuoteForm()

    site = SiteSettings.load()
    context = {
        "form": form,
        "page_title": f"Запрос коммерческого предложения — {site.company_name}",
        "page_description": "Список товаров для запроса коммерческого предложения.",
    }
    return render(request, "orders/quote.html", context)


@require_GET
def thanks(request):
    quote_id = request.GET.get("id", "")
    site = SiteSettings.load()
    context = {
        "quote_id": quote_id if quote_id.isdigit() else None,
        "page_title": f"Запрос отправлен — {site.company_name}",
    }
    return render(request, "orders/thanks.html", context)
```

`orders/urls.py`:
```python
from django.urls import path

from orders import views

app_name = "orders"

urlpatterns = [
    path("", views.quote, name="quote"),
    path("thanks/", views.thanks, name="thanks"),
]
```

`config/urls.py` (файл целиком):
```python
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from catalog.sitemaps import SITEMAPS
from catalog.views import robots_txt

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("robots.txt", robots_txt, name="robots"),
    path("quote/", include("orders.urls")),
    path("", include("catalog.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

- [ ] **Step 5: Шаблоны**

`templates/orders/quote.html`:
```django
{% extends "base.html" %}
{% block robots %}noindex, follow{% endblock %}
{% block content %}
  <div class="page-head">
    <h1>Запрос коммерческого предложения</h1>
    <p>Проверьте список и оставьте контакты — мы свяжемся с вами и пришлём цены и сроки поставки.</p>
  </div>
  <div class="quote-layout">
    <div>
      <ul class="quote-list" data-quote-list></ul>
      <p class="quote-empty" data-quote-empty>В запросе пока нет товаров. <a href="/catalog/">Перейти в каталог</a></p>
      <noscript><p class="notice notice--error">Для работы списка включите JavaScript или напишите нам в WhatsApp.</p></noscript>
    </div>

    <form method="post" action="/quote/" class="form panel" data-quote-form novalidate>
      {% csrf_token %}
      {% if form.non_field_errors or form.items.errors %}
        <div class="notice notice--error" role="alert">
          {% for error in form.non_field_errors %}<p>{{ error }}</p>{% endfor %}
          {% for error in form.items.errors %}<p>{{ error }}</p>{% endfor %}
        </div>
      {% endif %}
      <div class="form__row">
        <label for="{{ form.name.id_for_label }}">Имя</label>
        {{ form.name }}
        {% for error in form.name.errors %}<p class="form__error">{{ error }}</p>{% endfor %}
      </div>
      <div class="form__row">
        <label for="{{ form.phone.id_for_label }}">Телефон</label>
        {{ form.phone }}
        {% for error in form.phone.errors %}<p class="form__error">{{ error }}</p>{% endfor %}
      </div>
      <div class="form__hp" aria-hidden="true">
        <label for="{{ form.website.id_for_label }}">Сайт</label>
        {{ form.website }}
      </div>
      {{ form.items }}
      <button type="submit" class="btn btn--primary" data-quote-submit>Отправить запрос</button>
      <p class="note">Нажимая кнопку, вы соглашаетесь на обработку имени и телефона для ответа на запрос.</p>
    </form>
  </div>
{% endblock %}
```

`templates/orders/thanks.html`:
```django
{% extends "base.html" %}
{% block robots %}noindex, follow{% endblock %}
{% block content %}
  <div data-cart-clear hidden></div>
  <section class="panel">
    <h1>Спасибо! Запрос отправлен</h1>
    {% if quote_id %}<p>Номер вашей заявки: <strong>№{{ quote_id }}</strong>.</p>{% endif %}
    <p>Мы свяжемся с вами по указанному телефону.</p>
    {% with wa=site.whatsapp_list.0 %}
      {% if wa %}<p>Срочный вопрос? <a class="btn btn--whatsapp" href="https://wa.me/{{ wa.wa }}" target="_blank" rel="noopener">Написать в WhatsApp</a></p>{% endif %}
    {% endwith %}
    <p><a href="/catalog/">Вернуться в каталог</a></p>
  </section>
{% endblock %}
```

- [ ] **Step 6: Запустить тесты**

Run: `uv run pytest`
Expected: все тесты проходят (`tests/test_quote_view.py`: `13 passed`).

- [ ] **Step 7: Commit**

```bash
git add orders config/urls.py templates/orders tests/test_quote_view.py
git commit -m "feat(orders): add quote page with validation, honeypot and per-IP rate limit"
```

---

### Task 14: Корзина на JavaScript

**Files:**
- Create: `static/js/cart.js`
- Delete: `static/.gitkeep`
- Test: `tests/test_static_assets.py`

**Interfaces:**
- Consumes: разметка из Task 8 (`[data-product]`, `[data-qty]`, `[data-add-to-quote]`, `[data-gallery-thumb]`, `[data-gallery-main]`, `[data-cart-count]`) и Task 13 (`[data-quote-list]`, `[data-quote-empty]`, `[data-quote-form] [name="items"]`, `[data-quote-submit]`, `[data-cart-clear]`).
- Produces: `localStorage["quote_cart"]` — массив `{id: number, name: string, url: string, thumb: string, qty: number}`; значение скрытого поля `items` — `[{"id": number, "qty": number}]`.

- [ ] **Step 1: Написать падающий тест**

`tests/test_static_assets.py`:
```python
import pytest
from django.contrib.staticfiles import finders


@pytest.mark.parametrize("path", ["css/site.css", "js/cart.js"])
def test_static_assets_exist(path):
    assert finders.find(path) is not None


def test_cart_script_uses_agreed_contract():
    source = open(finders.find("js/cart.js"), encoding="utf-8").read()
    for marker in [
        '"quote_cart"', "[data-add-to-quote]", "[data-quote-list]", '[name="items"]',
        "[data-cart-count]", "[data-cart-clear]", "[data-gallery-thumb]",
    ]:
        assert marker in source
    assert "innerHTML" not in source
```

- [ ] **Step 2: Запустить — должен упасть**

Run: `uv run pytest tests/test_static_assets.py`
Expected: FAIL — `finders.find("js/cart.js")` возвращает `None`.

- [ ] **Step 3: Реализация**

```bash
git rm -q static/.gitkeep
```

`static/js/cart.js`:
```javascript
(function () {
  "use strict";

  var STORAGE_KEY = "quote_cart";
  var MAX_QTY = 999;
  var MAX_ITEMS = 50;
  var toastTimer = null;

  function isValidItem(item) {
    return item && Number.isInteger(item.id) && Number.isInteger(item.qty) && typeof item.name === "string";
  }

  function readCart() {
    try {
      var data = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "[]");
      return Array.isArray(data) ? data.filter(isValidItem) : [];
    } catch (error) {
      return [];
    }
  }

  function writeCart(items) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch (error) {
      // Приватный режим или переполнение хранилища: корзина не сохранится между страницами.
    }
    render();
  }

  function clampQty(value) {
    var qty = parseInt(value, 10);
    if (isNaN(qty) || qty < 1) return 1;
    return Math.min(qty, MAX_QTY);
  }

  function safePath(url) {
    return typeof url === "string" && url.charAt(0) === "/" && url.charAt(1) !== "/" ? url : "";
  }

  function addItem(product, qty) {
    var items = readCart();
    var existing = items.find(function (item) { return item.id === product.id; });
    if (existing) {
      existing.qty = clampQty(existing.qty + qty);
    } else {
      if (items.length >= MAX_ITEMS) {
        showToast("В запросе уже " + MAX_ITEMS + " позиций — отправьте его или удалите лишнее.", false);
        return;
      }
      items.push({ id: product.id, name: product.name, url: product.url, thumb: product.thumb, qty: clampQty(qty) });
    }
    writeCart(items);
    showToast("Добавлено в запрос.", true);
  }

  function setQty(id, qty) {
    var items = readCart();
    items.forEach(function (item) {
      if (item.id === id) item.qty = clampQty(qty);
    });
    writeCart(items);
  }

  function removeItem(id) {
    writeCart(readCart().filter(function (item) { return item.id !== id; }));
  }

  function showToast(message, withLink) {
    var toast = document.querySelector(".toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.className = "toast";
      toast.setAttribute("role", "status");
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    if (withLink) {
      var link = document.createElement("a");
      link.href = "/quote/";
      link.textContent = "Перейти к запросу";
      toast.appendChild(link);
    }
    toast.hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () { toast.hidden = true; }, 3500);
  }

  function renderItem(item) {
    var li = document.createElement("li");
    li.className = "quote-item";

    var thumb = safePath(item.thumb);
    if (thumb) {
      var img = document.createElement("img");
      img.src = thumb;
      img.alt = "";
      img.width = 64;
      img.height = 64;
      li.appendChild(img);
    } else {
      var placeholder = document.createElement("span");
      placeholder.className = "product-card__placeholder";
      placeholder.textContent = "Нет фото";
      li.appendChild(placeholder);
    }

    var name = document.createElement("a");
    name.className = "quote-item__name";
    name.href = safePath(item.url) || "#";
    name.textContent = item.name;
    li.appendChild(name);

    var qtyWrap = document.createElement("div");
    qtyWrap.className = "qty";
    var input = document.createElement("input");
    input.type = "number";
    input.min = "1";
    input.max = String(MAX_QTY);
    input.value = String(item.qty);
    input.setAttribute("aria-label", "Количество: " + item.name);
    input.addEventListener("change", function () { setQty(item.id, input.value); });
    qtyWrap.appendChild(input);
    li.appendChild(qtyWrap);

    var remove = document.createElement("button");
    remove.type = "button";
    remove.className = "quote-item__remove";
    remove.setAttribute("aria-label", "Удалить: " + item.name);
    remove.textContent = "×";
    remove.addEventListener("click", function () { removeItem(item.id); });
    li.appendChild(remove);

    return li;
  }

  function render() {
    var items = readCart();
    var count = items.length;

    document.querySelectorAll("[data-cart-count]").forEach(function (badge) {
      badge.textContent = String(count);
      badge.hidden = count === 0;
    });

    var list = document.querySelector("[data-quote-list]");
    if (!list) return;
    list.replaceChildren.apply(list, items.map(renderItem));

    var empty = document.querySelector("[data-quote-empty]");
    if (empty) empty.hidden = count > 0;

    var field = document.querySelector('[data-quote-form] [name="items"]');
    if (field) {
      field.value = JSON.stringify(items.map(function (item) { return { id: item.id, qty: item.qty }; }));
    }

    var submit = document.querySelector("[data-quote-submit]");
    if (submit) submit.disabled = count === 0;
  }

  document.addEventListener("click", function (event) {
    var addButton = event.target.closest("[data-add-to-quote]");
    if (addButton) {
      var container = addButton.closest("[data-product]");
      if (!container) return;
      var qtyInput = container.querySelector("[data-qty]");
      addItem(
        {
          id: parseInt(container.dataset.id, 10),
          name: container.dataset.name || "",
          url: container.dataset.url || "",
          thumb: container.dataset.thumb || ""
        },
        clampQty(qtyInput ? qtyInput.value : 1)
      );
      return;
    }

    var galleryThumb = event.target.closest("[data-gallery-thumb]");
    if (galleryThumb) {
      var main = document.querySelector("[data-gallery-main]");
      if (main && safePath(galleryThumb.dataset.full)) {
        main.src = galleryThumb.dataset.full;
        main.alt = galleryThumb.dataset.alt || "";
      }
      document.querySelectorAll("[data-gallery-thumb]").forEach(function (button) {
        button.setAttribute("aria-current", button === galleryThumb ? "true" : "false");
      });
    }
  });

  window.addEventListener("storage", function (event) {
    if (event.key === STORAGE_KEY) render();
  });

  document.addEventListener("DOMContentLoaded", function () {
    if (document.querySelector("[data-cart-clear]")) {
      try {
        window.localStorage.removeItem(STORAGE_KEY);
      } catch (error) {
        // Хранилище недоступно — очищать нечего.
      }
    }
    var form = document.querySelector("[data-quote-form]");
    if (form) form.addEventListener("submit", render);
    render();
  });
})();
```

- [ ] **Step 4: Запустить тесты и проверить синтаксис**

```bash
uv run pytest tests/test_static_assets.py
node --check static/js/cart.js
```
Expected: `3 passed`; `node --check` без вывода. Если Node не установлен — пропустить команду и выполнить ручную проверку ниже (синтаксическая ошибка сразу видна в консоли браузера).

- [ ] **Step 5: Ручной чек-лист корзины (спека §11)**

```bash
uv run python manage.py runserver
```
В браузере (консоль DevTools открыта, ошибок быть не должно), с товаром, созданным в админке:
1. На странице товара ввести количество 2 → «Добавить в запрос» → появляется уведомление, счётчик в шапке = 1.
2. Повторно добавить тот же товар с количеством 3 → счётчик остаётся 1; на `/quote/` количество = 5.
3. На `/quote/` изменить количество на 7 → обновить страницу → 7 сохранилось; ввести 0 → становится 1; ввести 5000 → становится 999.
4. Удалить позицию → показывается «В запросе пока нет товаров», кнопка отправки неактивна, счётчик скрыт.
5. Добавить товар, отправить форму с телефоном `12345` → ошибка у поля телефона, список товаров на месте.
6. Отправить с корректным телефоном → страница «Спасибо» с номером заявки; счётчик в шапке исчез; в консоли `runserver` напечатано письмо.
7. На странице товара с несколькими фото клик по миниатюре меняет главное фото.
8. Повторить шаги 1–6 в DevTools на ширине 360 px: нет горизонтальной прокрутки, кнопки доступны.

- [ ] **Step 6: Commit**

```bash
git add static tests/test_static_assets.py
git commit -m "feat: add localStorage quote cart and product gallery script"
```

---
### Task 15: Снимок старых данных и черновик контента

Скачивает каталог со старого сайта в `legacy/`, раскладывает его по новой структуре (дубли объединены, названия очищены, slug назначены), скачивает фото и пишет черновик `content/catalog.draft.yaml` с исходными текстами и таблицами для последующего переписывания (Task 17).

**Files:**
- Create: `scripts/__init__.py`, `scripts/fetch_legacy.py`, `scripts/prepare_catalog.py`, `legacy/categories.json`, `legacy/products.json`, `content/catalog.draft.yaml`, `content/images/**`, `content/images/_report.txt`
- Test: `tests/test_prepare_catalog.py`

**Interfaces:**
- Produces (`scripts.prepare_catalog`):
  - `CATEGORIES: list[tuple[str, str, str]]` — (старое имя, slug, новое имя), в порядке сортировки.
  - `PRODUCTS: list[dict]` — ключи `slug`, `legacy_ids`, `model_code`, необязательный `name`.
  - `REMOVED_LEGACY_IDS: dict[int, str]` — старый id → slug категории, куда уходит текст.
  - `clean_name(name: str) -> str`, `html_to_text(html: str | None) -> str`, `extract_tables(html: str | None) -> list[dict]` (`{"heading": str, "rows": list[list[str]]}`), `extract_image_urls(record: dict) -> list[str]`, `build_draft(categories: list[dict], products: list[dict]) -> dict`.
  - Формат черновика — тот же, что у `content/catalog.yaml` (Task 16), плюс поля `source_text`, `source_tables`, `source_image_urls`.

- [ ] **Step 1: Скачать снимок старых данных**

`scripts/__init__.py`: пустой файл.

`scripts/fetch_legacy.py`:
```python
"""Скачивает снимок каталога со старого сайта prom-products.kz в legacy/."""

import json
import urllib.request
from pathlib import Path

BASE_URL = "https://prom-products.kz/api"
OUT_DIR = Path(__file__).resolve().parent.parent / "legacy"


def fetch(name: str) -> list[dict]:
    request = urllib.request.Request(f"{BASE_URL}/{name}", headers={"User-Agent": "promproduct-migration/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    for name in ("categories", "products"):
        data = fetch(name)
        path = OUT_DIR / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{name}: {len(data)} записей → {path}")


if __name__ == "__main__":
    main()
```

```bash
uv run python scripts/fetch_legacy.py
```
Expected: `categories: 147 записей`, `products: 58 записей`. Если в песочнице нет сети — запустить из обычного терминала. Проверить кодировку: `uv run python -c "import json;print(json.load(open('legacy/products.json',encoding='utf-8'))[0]['name'])"` печатает читаемый русский текст.

- [ ] **Step 2: Написать падающие тесты**

`tests/test_prepare_catalog.py`:
```python
import json
from pathlib import Path

import pytest

from scripts.prepare_catalog import (
    CATEGORIES,
    PRODUCTS,
    REMOVED_LEGACY_IDS,
    build_draft,
    clean_name,
    extract_image_urls,
    extract_tables,
    html_to_text,
)

LEGACY = Path(__file__).resolve().parent.parent / "legacy"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Гидравлический cъемник подшипников СГ-5Н ", "Гидравлический съёмник подшипников СГ-5Н"),
        ("Электрический пресс ИНСТАН ПГГ-15ЭП", "Электрический пресс ПГГ-15ЭП"),
        ("Трубогиб ручной гидравлический INSTAN ТПГ-2Б", "Трубогиб ручной гидравлический ТПГ-2Б"),
        ("Шиногибы гидравлические ШГГ\nдля гибки токоведущих шин", "Шиногибы гидравлические ШГГ для гибки токоведущих шин"),
        ("Съемник подшипников", "Съёмник подшипников"),
    ],
)
def test_clean_name(raw, expected):
    assert clean_name(raw) == expected


def test_html_to_text_collapses_whitespace_and_entities():
    assert html_to_text("<p>Труба&nbsp;2&quot;</p>\n<p>  ГОСТ 3262-75 </p>") == 'Труба 2" ГОСТ 3262-75'
    assert html_to_text(None) == ""


def test_extract_tables_takes_innermost_tables_with_heading():
    html = """
    <table><tr><td>
      <h2>2. ТЕХНИЧЕСКИЕ ХАРАКТЕРИСТИКИ</h2>
      <table>
        <tr><td>Параметр</td><td>Значение</td></tr>
        <tr><td>Масса, кг</td><td>54</td></tr>
        <tr><td></td><td></td></tr>
      </table>
    </td></tr></table>
    """
    assert extract_tables(html) == [
        {"heading": "2. ТЕХНИЧЕСКИЕ ХАРАКТЕРИСТИКИ", "rows": [["Параметр", "Значение"], ["Масса, кг", "54"]]}
    ]


def test_extract_image_urls_dedupes_and_resolves_relative():
    record = {
        "pic_url": "https://instan.spb.ru/images/a.jpg",
        "description": '<img src="https://instan.spb.ru/images/a.jpg"><img src="/images/b.gif">',
    }
    assert extract_image_urls(record) == [
        "https://instan.spb.ru/images/a.jpg",
        "https://instan.spb.ru/images/b.gif",
    ]


def test_mapping_is_consistent():
    slugs = [p["slug"] for p in PRODUCTS]
    assert len(slugs) == 50
    assert len(set(slugs)) == 50
    legacy_ids = [i for p in PRODUCTS for i in p["legacy_ids"]]
    assert len(legacy_ids) == len(set(legacy_ids)) == 57
    assert not set(legacy_ids) & set(REMOVED_LEGACY_IDS)
    assert len(CATEGORIES) == 21


def test_build_draft_rejects_unmapped_legacy_product():
    with pytest.raises(ValueError, match="9999"):
        build_draft([], [{"id": 9999, "name": "X", "description": "", "pic_url": None, "category": None}])


@pytest.mark.skipif(not (LEGACY / "products.json").exists(), reason="legacy snapshot not downloaded")
def test_build_draft_on_real_snapshot():
    categories = json.loads((LEGACY / "categories.json").read_text(encoding="utf-8"))
    products = json.loads((LEGACY / "products.json").read_text(encoding="utf-8"))
    draft = build_draft(categories, products)

    assert len(draft["categories"]) == 21
    assert len(draft["products"]) == 50
    category_slugs = {c["slug"] for c in draft["categories"]}
    assert {p["category"] for p in draft["products"]} <= category_slugs
    assert next(c for c in draft["categories"] if c["slug"] == "machines")["is_active"] is False

    by_slug = {p["slug"]: p for p in draft["products"]}
    assert by_slug["sg-5n"]["legacy_ids"] == [34, 44]
    assert by_slug["da-5-50"]["name"] == "Домкраты автономные гидравлические с низким подхватом ДА5–ДА50"
    assert by_slug["pgg-15ep"]["name"] == "Электрический пресс ПГГ-15ЭП"
    assert "Масса, кг" in json.dumps(by_slug["tpg-2b"]["source_tables"], ensure_ascii=False)
    for product in draft["products"]:
        assert "инстан" not in product["name"].lower()
        assert "\n" not in product["name"]
        assert product["needs_review"] == (not product["source_text"])
        assert product["short_description"] == "" and product["description"] == ""
```

- [ ] **Step 3: Запустить — должны упасть**

Run: `uv run pytest tests/test_prepare_catalog.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'scripts.prepare_catalog'`.

- [ ] **Step 4: Реализация `scripts/prepare_catalog.py`**

```python
"""Готовит content/catalog.draft.yaml и content/images/ из снимка legacy/.

Запуск: uv run python scripts/prepare_catalog.py [--skip-images]
"""

import argparse
import json
import re
import urllib.request
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin

import yaml
from bs4 import BeautifulSoup
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
LEGACY_DIR = ROOT / "legacy"
CONTENT_DIR = ROOT / "content"
IMAGES_DIR = CONTENT_DIR / "images"
SOURCE_BASE_URL = "https://instan.spb.ru/"

# (имя категории в старой БД, slug, новое имя) — в порядке сортировки
CATEGORIES = [
    ("Трубогиб", "pipe-benders", "Трубогибы"),
    ("Опрессовочный насос", "pressure-test-pumps", "Опрессовочные насосы"),
    ("Опрессовщики", "pressure-testers", "Опрессовщики"),
    ("Тиски", "vises", "Тиски"),
    ("Труборез", "pipe-cutters", "Труборезы"),
    ("Головки резьбонарезные трубные", "pipe-threading-dies", "Головки резьбонарезные трубные"),
    ("Пресс гидравлический", "hydraulic-presses", "Прессы гидравлические"),
    ("Маслостанции", "hydraulic-power-units", "Маслостанции"),
    ("Гидроцилиндры", "hydraulic-cylinders", "Гидроцилиндры"),
    ("Съемники подшипников гидравлические", "hydraulic-bearing-pullers", "Съёмники подшипников гидравлические"),
    ("Домкраты", "jacks", "Домкраты"),
    ("Лебедка", "winches", "Лебёдки"),
    ("Шинообрабатывающие станки", "busbar-machines", "Шинообрабатывающие станки"),
    ("Шиногибы", "busbar-benders", "Шиногибы"),
    ("Шинодыры", "busbar-punches", "Шинодыры"),
    ("Шинорезы", "busbar-cutters", "Шинорезы"),
    ("Уголкорезы гидравлические", "angle-cutters", "Уголкорезы гидравлические"),
    ("Разгонщик фланцев", "flange-spreaders", "Разгонщики фланцев"),
    ("Арматурогибы", "rebar-benders", "Арматурогибы"),
    ("Тросорезы", "cable-cutters", "Тросорезы"),
    ("Станок", "machines", "Станки"),
]
INACTIVE_CATEGORY_SLUGS = {"machines"}

# Товар-серия удаляется, его текст уходит в SEO-текст категории (спека §9, таблица дублей)
REMOVED_LEGACY_IDS = {26: "hydraulic-bearing-pullers"}

PRODUCTS = [
    {"slug": "tr-1", "legacy_ids": [62], "model_code": "ТР-1"},
    {"slug": "tr-25u", "legacy_ids": [61], "model_code": "ТР-25У"},
    {"slug": "tpg-1b", "legacy_ids": [1], "model_code": "ТПГ-1Б"},
    {"slug": "tpg-1-25b", "legacy_ids": [9], "model_code": "ТПГ-1,25Б"},
    {"slug": "tpg-2b", "legacy_ids": [10], "model_code": "ТПГ-2Б"},
    {"slug": "tpg-3b", "legacy_ids": [11], "model_code": "ТПГ-3Б"},
    {"slug": "tpg-2ep", "legacy_ids": [12], "model_code": "ТПГ-2ЭП"},
    {"slug": "tpg-3ep", "legacy_ids": [13], "model_code": "ТПГ-3ЭП"},
    {"slug": "tg-3ep", "legacy_ids": [14], "model_code": "ТГ-3ЭП"},
    {"slug": "tem-76x50", "legacy_ids": [60], "model_code": "ТЭМ-76х50"},
    {"slug": "ogs-30", "legacy_ids": [15], "model_code": "ОГС-30"},
    {"slug": "ogs-40", "legacy_ids": [2], "model_code": "ОГС-40"},
    {"slug": "ogs-25ep-3", "legacy_ids": [63], "model_code": "ОГС-25ЭП-3"},
    {"slug": "ogs-60-ep-6", "legacy_ids": [64], "model_code": "ОГС-60-ЭП-6"},
    {"slug": "tt-3", "legacy_ids": [17], "model_code": "ТТ-3"},
    {"slug": "tr-2", "legacy_ids": [18], "model_code": "ТР-2"},
    {"slug": "pipe-threading-die-heads", "legacy_ids": [22], "model_code": ""},
    {"slug": "pgg-10", "legacy_ids": [20], "model_code": "ПГГ-10"},
    {"slug": "pgg-15ep", "legacy_ids": [21], "model_code": "ПГГ-15ЭП"},
    {"slug": "mgs-630-0-8-r-1", "legacy_ids": [4], "model_code": "МГС 630-0.8-Р-1"},
    {"slug": "mgs-630-0-8p-r-1", "legacy_ids": [5], "model_code": "МГС 630-0.8П-Р-1"},
    {"slug": "mgs-700-0-8-r-1", "legacy_ids": [3], "model_code": "МГС 700-0.8-Р-1"},
    {"slug": "mgs-700-0-8p-e-1", "legacy_ids": [6], "model_code": "МГС 700-0.8П-Э-1"},
    {"slug": "mgs-700-0-7p-e-1", "legacy_ids": [7], "model_code": "МГС 700-0.7П-Э-1"},
    {"slug": "mgs-700-0-8p-e-3", "legacy_ids": [8], "model_code": "МГС 700-0.8П-Э-3"},
    {"slug": "spring-return-cylinders", "legacy_ids": [27], "model_code": ""},
    {"slug": "sg-5", "legacy_ids": [28], "model_code": "СГ-5"},
    {"slug": "sg-10", "legacy_ids": [29], "model_code": "СГ-10"},
    {"slug": "sg-15", "legacy_ids": [30], "model_code": "СГ-15"},
    {"slug": "sg-20", "legacy_ids": [31], "model_code": "СГ-20"},
    {"slug": "sg-30", "legacy_ids": [32], "model_code": "СГ-30"},
    {"slug": "sg-50", "legacy_ids": [33], "model_code": "СГ-50"},
    {"slug": "sg-5n", "legacy_ids": [34, 44], "model_code": "СГ-5Н"},
    {"slug": "sg-10n", "legacy_ids": [38, 43], "model_code": "СГ-10Н"},
    {"slug": "sg-20n", "legacy_ids": [42, 48], "model_code": "СГ-20Н"},
    {"slug": "sg-30n", "legacy_ids": [41, 47], "model_code": "СГ-30Н"},
    {"slug": "sg-50n", "legacy_ids": [40, 46], "model_code": "СГ-50Н"},
    {"slug": "sg-100n", "legacy_ids": [39, 45], "model_code": "СГ-100Н"},
    {
        "slug": "da-5-50",
        "legacy_ids": [23, 24],
        "model_code": "ДА5–ДА50",
        "name": "Домкраты автономные гидравлические с низким подхватом ДА5–ДА50",
    },
    {"slug": "dg-dn-dp", "legacy_ids": [25], "model_code": "ДГ, ДН, ДП"},
    {"slug": "lr-1-2", "legacy_ids": [19], "model_code": "ЛР-1,2"},
    {"slug": "sshg", "legacy_ids": [49], "model_code": "СШГ"},
    {"slug": "shgg", "legacy_ids": [52], "model_code": "ШГГ"},
    {"slug": "shdg-31n-35n", "legacy_ids": [53], "model_code": "ШДГ-31Н, ШДГ-35Н, ППГ-50Н"},
    {"slug": "shrg-150n-200n", "legacy_ids": [54], "model_code": "ШРГ-150Н, ШРГ-200Н"},
    {"slug": "hydraulic-angle-cutter", "legacy_ids": [55], "model_code": ""},
    {"slug": "rfv-rfg", "legacy_ids": [56], "model_code": "РФВ, РФГ"},
    {"slug": "ag-25n-32n-40n", "legacy_ids": [57], "model_code": "АГ-25Н, АГ-32Н, АГ-40Н"},
    {"slug": "tsrg-20a", "legacy_ids": [59], "model_code": "ТСРГ-20А"},
    {"slug": "tsrg-30-48", "legacy_ids": [58], "model_code": "ТСРГ-30, ТСРГ-48"},
]

CYRILLIC = "А-Яа-яЁё"


def clean_name(name: str) -> str:
    text = " ".join(name.split())
    text = re.sub(rf"(?<=[{CYRILLIC}])c|c(?=[{CYRILLIC}])", "с", text)
    text = re.sub(rf"(?<=[{CYRILLIC}])C|C(?=[{CYRILLIC}])", "С", text)
    text = re.sub(r"\b(?:ИНСТАН|INSTAN)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"([Сс])ъемник", r"\1ъёмник", text)
    return " ".join(text.split())


def html_to_text(html: str | None) -> str:
    if not html:
        return ""
    return " ".join(BeautifulSoup(html, "html.parser").get_text(" ").split())


def extract_tables(html: str | None) -> list[dict]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    tables = []
    for table in soup.find_all("table"):
        if table.find("table"):
            continue
        rows = []
        for tr in table.find_all("tr"):
            cells = [" ".join(cell.get_text(" ").split()) for cell in tr.find_all(["td", "th"])]
            if any(cells):
                rows.append(cells)
        if rows:
            heading_tag = table.find_previous(["h2", "h3", "h4"])
            heading = " ".join(heading_tag.get_text(" ").split()) if heading_tag else ""
            tables.append({"heading": heading, "rows": rows})
    return tables


def extract_image_urls(record: dict) -> list[str]:
    urls = []
    if record.get("pic_url"):
        urls.append(record["pic_url"])
    if record.get("description"):
        for img in BeautifulSoup(record["description"], "html.parser").find_all("img"):
            if img.get("src"):
                urls.append(urljoin(SOURCE_BASE_URL, img["src"]))
    return list(dict.fromkeys(urls))


def build_draft(categories: list[dict], products: list[dict]) -> dict:
    by_id = {p["id"]: p for p in products}
    mapped_ids = {i for entry in PRODUCTS for i in entry["legacy_ids"]}
    unknown = sorted(set(by_id) - mapped_ids - set(REMOVED_LEGACY_IDS))
    if unknown:
        raise ValueError(f"Legacy products without mapping: {unknown}")
    missing = sorted((mapped_ids | set(REMOVED_LEGACY_IDS)) - set(by_id))
    if missing:
        raise ValueError(f"Mapped legacy ids not found in snapshot: {missing}")

    slug_by_old_name = {old: slug for old, slug, _ in CATEGORIES}
    category_texts: dict[str, list[str]] = {slug: [] for _, slug, _ in CATEGORIES}
    for legacy_id, slug in REMOVED_LEGACY_IDS.items():
        text = html_to_text(by_id[legacy_id]["description"])
        if text:
            category_texts[slug].append(text)

    draft_categories = [
        {
            "slug": slug,
            "name": name,
            "sort_order": (index + 1) * 10,
            "is_active": slug not in INACTIVE_CATEGORY_SLUGS,
            "meta_title": "",
            "meta_description": "",
            "seo_text": "",
            "source_text": "\n\n".join(category_texts[slug]),
        }
        for index, (_, slug, name) in enumerate(CATEGORIES)
    ]

    draft_products = []
    sort_counters: dict[str, int] = {}
    for entry in PRODUCTS:
        records = [by_id[i] for i in entry["legacy_ids"]]
        primary = max(records, key=lambda r: len(r.get("description") or ""))
        category_name = (primary.get("category") or {}).get("name")
        category_slug = slug_by_old_name[category_name]
        sort_counters[category_slug] = sort_counters.get(category_slug, 0) + 10
        texts = list(dict.fromkeys(t for t in (html_to_text(r.get("description")) for r in records) if t))
        image_urls = list(dict.fromkeys(url for r in records for url in extract_image_urls(r)))
        draft_products.append(
            {
                "slug": entry["slug"],
                "legacy_ids": entry["legacy_ids"],
                "category": category_slug,
                "name": entry.get("name") or clean_name(primary["name"]),
                "model_code": entry["model_code"],
                "sort_order": sort_counters[category_slug],
                "is_active": True,
                "needs_review": not texts,
                "short_description": "",
                "description": "",
                "meta_title": "",
                "meta_description": "",
                "specs": [],
                "images": [],
                "source_text": "\n\n---\n\n".join(texts),
                "source_tables": [t for r in records for t in extract_tables(r.get("description"))],
                "source_image_urls": image_urls,
            }
        )
    return {"categories": draft_categories, "products": draft_products}


def download_image(url: str, destination: Path) -> str | None:
    """Скачивает и конвертирует фото в WebP. Возвращает текст ошибки или None."""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (promproduct-migration)"})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
        with Image.open(BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source)
            has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
            image = image.convert("RGBA" if has_alpha else "RGB")
            image.thumbnail((1600, 1600))
            destination.parent.mkdir(parents=True, exist_ok=True)
            image.save(destination, "WEBP", quality=85, method=6)
        return None
    except Exception as exc:  # noqa: BLE001 — любая ошибка попадает в отчёт
        return f"{type(exc).__name__}: {exc}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-images", action="store_true")
    args = parser.parse_args()

    categories = json.loads((LEGACY_DIR / "categories.json").read_text(encoding="utf-8"))
    products = json.loads((LEGACY_DIR / "products.json").read_text(encoding="utf-8"))
    draft = build_draft(categories, products)

    report = []
    if not args.skip_images:
        for product in draft["products"]:
            for index, url in enumerate(product["source_image_urls"], start=1):
                relative = f"{product['slug']}/{index}.webp"
                error = download_image(url, IMAGES_DIR / relative)
                if error:
                    report.append(f"FAIL {product['slug']} {url} — {error}")
                else:
                    product["images"].append({"file": relative, "alt": product["name"]})
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        (IMAGES_DIR / "_report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")

    CONTENT_DIR.mkdir(exist_ok=True)
    (CONTENT_DIR / "catalog.draft.yaml").write_text(
        yaml.safe_dump(draft, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8"
    )
    print(f"Категорий: {len(draft['categories'])}, товаров: {len(draft['products'])}, ошибок фото: {len(report)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Запустить тесты**

Run: `uv run pytest tests/test_prepare_catalog.py`
Expected: `11 passed`.

- [ ] **Step 6: Сгенерировать черновик и фото**

```bash
uv run python scripts/prepare_catalog.py
```
Expected: `Категорий: 21, товаров: 50, ошибок фото: N`. Открыть `content/images/_report.txt` — перечислены недоступные фото. Просмотреть папки `content/images/*/` и в `content/images/_report.txt` дописать строки `LOGO <slug>/<N>.webp` для фото, на которых виден логотип производителя (спека §9 п.6) — такие фото в Task 17 не включаются в `images`.

- [ ] **Step 7: Commit**

```bash
git add scripts legacy content tests/test_prepare_catalog.py
git commit -m "chore(content): snapshot legacy catalog and generate content draft with images"
```

---

### Task 16: Команда `import_catalog`

**Files:**
- Create: `catalog/management/__init__.py`, `catalog/management/commands/__init__.py`, `catalog/management/commands/import_catalog.py`
- Test: `tests/test_import_catalog.py`

**Interfaces:**
- Consumes: модели каталога (Tasks 3–4).
- Produces: `python manage.py import_catalog [--content PATH] [--images-dir PATH]`. Формат `content/catalog.yaml`:

```yaml
categories:
  - slug: pipe-benders          # обязательно, из спеки §5
    name: Трубогибы             # обязательно
    sort_order: 10
    is_active: true
    meta_title: ""              # ≤60 или пусто
    meta_description: "..."     # ≤160
    seo_text: |                 # HTML из allowlist
      <p>...</p>
products:
  - slug: tpg-2b                # обязательно, уникально
    legacy_ids: [10]            # старые id (для переноса заявок, Task 18)
    category: pipe-benders      # slug категории из этого файла
    name: Трубогиб ручной гидравлический ТПГ-2Б
    model_code: ТПГ-2Б
    sort_order: 50
    is_active: true
    needs_review: false         # true — текст написан без исходного описания
    short_description: "..."
    description: |
      <p>...</p>
    meta_title: "..."
    meta_description: "..."
    specs:                      # [название, значение]
      - ["Масса, кг", "54"]
    images:                     # пути относительно content/images/
      - {file: tpg-2b/1.webp, alt: Трубогиб ручной гидравлический ТПГ-2Б}
```

Поведение: категории и товары ищутся по `slug` (`update_or_create`); характеристики и фото товара пересоздаются; поля `price` и `show_price` **не трогаются** (цены из админки сохраняются); отсутствующие файлы фото пропускаются и перечисляются в отчёте; неизвестная категория товара → `CommandError`, изменения откатываются.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_import_catalog.py`:
```python
from decimal import Decimal
from io import BytesIO, StringIO

import pytest
import yaml
from django.core.management import CommandError, call_command
from PIL import Image

from catalog.models import Category, Product, ProductImage, ProductSpec

pytestmark = pytest.mark.django_db


@pytest.fixture
def content(tmp_path):
    images_dir = tmp_path / "images"
    (images_dir / "tpg-2b").mkdir(parents=True)
    buffer = BytesIO()
    Image.new("RGB", (800, 600), "gray").save(buffer, "WEBP")
    (images_dir / "tpg-2b" / "1.webp").write_bytes(buffer.getvalue())

    data = {
        "categories": [
            {"slug": "pipe-benders", "name": "Трубогибы", "sort_order": 10, "is_active": True,
             "meta_title": "", "meta_description": "Трубогибы", "seo_text": "<p>Текст</p>"},
        ],
        "products": [
            {"slug": "tpg-2b", "legacy_ids": [10], "category": "pipe-benders", "name": "Трубогиб ТПГ-2Б",
             "model_code": "ТПГ-2Б", "sort_order": 10, "is_active": True, "needs_review": True,
             "short_description": "Кратко", "description": "<p>Описание</p>", "meta_title": "",
             "meta_description": "Описание", "specs": [["Масса, кг", "54"], ["Ход штока, мм", "180"]],
             "images": [{"file": "tpg-2b/1.webp", "alt": "Трубогиб"}, {"file": "tpg-2b/missing.webp", "alt": "X"}]},
        ],
    }
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return {"path": path, "images_dir": images_dir, "data": data}


def run(content) -> str:
    out = StringIO()
    call_command("import_catalog", content=str(content["path"]), images_dir=str(content["images_dir"]), stdout=out)
    return out.getvalue()


def test_import_creates_catalog(content):
    output = run(content)
    product = Product.objects.get(slug="tpg-2b")
    assert product.category.slug == "pipe-benders"
    assert product.description == "<p>Описание</p>"
    assert [(s.name, s.value) for s in product.specs.all()] == [("Масса, кг", "54"), ("Ход штока, мм", "180")]
    assert product.images.count() == 1
    assert product.images.get().alt == "Трубогиб"
    assert "tpg-2b/missing.webp" in output
    assert "Требуют вычитки: 1" in output


def test_import_is_idempotent(content, media_root):
    run(content)
    run(content)
    assert Category.objects.count() == 1
    assert Product.objects.count() == 1
    assert ProductSpec.objects.count() == 2
    assert ProductImage.objects.count() == 1
    assert len(list((media_root / "products" / "tpg-2b").glob("*.webp"))) == 1


def test_reimport_updates_text_but_keeps_price(content):
    run(content)
    Product.objects.filter(slug="tpg-2b").update(price=Decimal("86300"), show_price=True)
    content["data"]["products"][0]["name"] = "Трубогиб гидравлический ТПГ-2Б"
    content["path"].write_text(yaml.safe_dump(content["data"], allow_unicode=True), encoding="utf-8")
    run(content)
    product = Product.objects.get(slug="tpg-2b")
    assert product.name == "Трубогиб гидравлический ТПГ-2Б"
    assert product.price == Decimal("86300")
    assert product.show_price is True


def test_unknown_category_fails_without_changes(content):
    content["data"]["products"][0]["category"] = "nope"
    content["path"].write_text(yaml.safe_dump(content["data"], allow_unicode=True), encoding="utf-8")
    with pytest.raises(CommandError, match="nope"):
        run(content)
    assert Category.objects.count() == 0
```

- [ ] **Step 2: Запустить — должны упасть**

Run: `uv run pytest tests/test_import_catalog.py`
Expected: FAIL, `CommandError: Unknown command: 'import_catalog'`.

- [ ] **Step 3: Реализация**

`catalog/management/__init__.py`, `catalog/management/commands/__init__.py`: пустые файлы.

`catalog/management/commands/import_catalog.py`:
```python
from collections import Counter
from pathlib import Path

import yaml
from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Category, Product, ProductImage, ProductSpec

CATEGORY_FIELDS = ("name", "seo_text", "meta_title", "meta_description", "sort_order", "is_active")
PRODUCT_FIELDS = (
    "name", "model_code", "short_description", "description",
    "meta_title", "meta_description", "sort_order", "is_active",
)


class Command(BaseCommand):
    help = "Загружает категории и товары из content/catalog.yaml (повторный запуск обновляет записи)."

    def add_arguments(self, parser):
        parser.add_argument("--content", default=str(Path(settings.BASE_DIR) / "content" / "catalog.yaml"))
        parser.add_argument("--images-dir", default=str(Path(settings.BASE_DIR) / "content" / "images"))

    def handle(self, *args, **options):
        content_path = Path(options["content"])
        images_dir = Path(options["images_dir"])
        if not content_path.exists():
            raise CommandError(f"Файл не найден: {content_path}")
        data = yaml.safe_load(content_path.read_text(encoding="utf-8"))

        stats: Counter = Counter()
        missing_images: list[str] = []

        with transaction.atomic():
            categories = {}
            for entry in data["categories"]:
                defaults = {field: entry[field] for field in CATEGORY_FIELDS if field in entry}
                category, created = Category.objects.update_or_create(slug=entry["slug"], defaults=defaults)
                categories[category.slug] = category
                stats["categories_created" if created else "categories_updated"] += 1

            for entry in data["products"]:
                category = categories.get(entry["category"])
                if category is None:
                    raise CommandError(f"Товар {entry['slug']}: неизвестная категория {entry['category']}")
                defaults = {field: entry[field] for field in PRODUCT_FIELDS if field in entry}
                defaults["category"] = category
                product, created = Product.objects.update_or_create(slug=entry["slug"], defaults=defaults)
                stats["products_created" if created else "products_updated"] += 1

                product.specs.all().delete()
                ProductSpec.objects.bulk_create(
                    [
                        ProductSpec(product=product, name=str(name), value=str(value), sort_order=index)
                        for index, (name, value) in enumerate(entry.get("specs", []))
                    ]
                )

                product.images.all().delete()
                for index, image in enumerate(entry.get("images", [])):
                    path = images_dir / image["file"]
                    if not path.exists():
                        missing_images.append(image["file"])
                        continue
                    with path.open("rb") as handle:
                        ProductImage.objects.create(
                            product=product,
                            image=File(handle, name=path.name),
                            alt=image.get("alt", ""),
                            sort_order=index,
                        )

                if entry.get("needs_review"):
                    stats["needs_review"] += 1

        self.stdout.write(
            f"Категорий: создано {stats['categories_created']}, обновлено {stats['categories_updated']}\n"
            f"Товаров: создано {stats['products_created']}, обновлено {stats['products_updated']}\n"
            f"Требуют вычитки: {stats['needs_review']}"
        )
        if missing_images:
            self.stdout.write("Не найдены фото:\n" + "\n".join(f"  {name}" for name in missing_images))
```

- [ ] **Step 4: Запустить тесты**

Run: `uv run pytest tests/test_import_catalog.py`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add catalog/management tests/test_import_catalog.py
git commit -m "feat(catalog): add idempotent import_catalog command"
```

---
### Task 17: Переписанный контент `content/catalog.yaml`

Контентная задача: из черновика `content/catalog.draft.yaml` написать уникальные тексты для 50 товаров и 21 категории. Корректность проверяет тест: структура, длины, разрешённый HTML, отсутствие упоминаний производителя и — главное — **ни одного числа, которого нет в исходных данных**.

**Files:**
- Create: `content/catalog.yaml`
- Test: `tests/test_content_file.py`

**Interfaces:**
- Consumes: `content/catalog.draft.yaml`, `content/images/`, `content/images/_report.txt` (Task 15); формат YAML из Task 16; `catalog.sanitize.ALLOWED_TAGS`.
- Produces: `content/catalog.yaml` — 21 категория, 50 товаров; вход для `import_catalog` (Task 16) и таблица `legacy_ids` для `import_legacy_requests` (Task 18).

**Правила написания (обязательны):**
1. Русский язык, деловой тон, без превосходных степеней («лучший», «уникальный»), без обещаний, которых нет в исходнике (сроки, гарантия, наличие на складе, скидки).
2. Производитель не упоминается ни в каком виде. Фразы исходника от лица производителя («наше предприятие производит…») не переносятся.
3. Все числа (в характеристиках, описаниях, meta) берутся **только** из исходного текста и таблиц этого товара или из его названия/модели. Нельзя пересчитывать единицы, округлять или добавлять «типовые» значения. Если числа нет в источнике — писать без числа.
4. Товар: `short_description` 20–300 символов; `description` — 150–300 слов (для `needs_review: true` — 60–300), структура: абзац о назначении → `<h3>` «Особенности» или «Как устроен» → `<h3>Комплектация</h3>` списком (если есть в исходнике) → абзац о поставке по Казахстану и запросе КП. Таблица моделей серии (несколько колонок в `source_tables`) переносится в `description` как `<table><thead>…</thead><tbody>…</tbody></table>` со значениями из источника.
5. `specs` — пары «название с единицей измерения, значение» из двухколоночных таблиц характеристик источника; таблицу комплектности в `specs` не переносить.
6. `meta_title` ≤ 60 символов, обязательно (шаблон по умолчанию длиннее 60); `meta_description` 70–160 символов.
7. HTML — только теги `p, br, strong, em, ul, ol, li, h2, h3, h4, a, table, thead, tbody, tr, th, td`, без атрибутов (кроме `href` у `a`).
8. Нет смешения латиницы и кириллицы внутри слова; писать «съёмник», не «cъемник».
9. `images` — из черновика, кроме фото с пометкой `LOGO` в `content/images/_report.txt`.
10. Поля `source_text`, `source_tables`, `source_image_urls` в итоговый файл не попадают.
11. Категория: `seo_text` 100–200 слов (у неактивной `machines` — может быть пустым): что это за инструмент, для каких работ, чем отличаются модели в категории, на что смотреть при выборе, призыв добавить модели в запрос. Для `hydraulic-bearing-pullers` использовать `source_text` категории (текст удалённой серии).

**Пример готового товара** (все числа есть в исходнике `legacy` id 10):

```yaml
  - slug: tpg-2b
    legacy_ids: [10]
    category: pipe-benders
    name: Трубогиб ручной гидравлический ТПГ-2Б
    model_code: ТПГ-2Б
    sort_order: 50
    is_active: true
    needs_review: false
    short_description: Переносной ручной гидравлический трубогиб для водогазопроводных труб до 2" без электропитания.
    description: |
      <p>Трубогиб ТПГ-2Б — переносной ручной гидравлический трубогиб для гибки водогазопроводных труб по ГОСТ 3262-75 и круглого проката, прочность которого не превышает прочности трубы 2" (условный проход 50 мм). Инструмент не требует электропитания, поэтому подходит для работы прямо на объекте: при монтаже систем отопления и водоснабжения, газопроводов и технологических трубопроводов.</p>
      <h3>Как устроен</h3>
      <p>Силовая часть трубогиба — гидроцилиндр со встроенным ручным насосом. Труба укладывается на поворотные упоры, закреплённые между верхней и нижней траверсами, а шток гидроцилиндра через гибочный шаблон изгибает её до нужного угла. Радиус гибки задаётся сменным шаблоном под диаметр трубы, поэтому один инструмент закрывает весь ряд типоразмеров из комплекта. Все детали хранятся и перевозятся в транспортировочном ящике.</p>
      <h3>Комплектация</h3>
      <ul>
      <li>гидроцилиндр в сборе;</li>
      <li>верхняя и нижняя траверсы;</li>
      <li>поворотные упоры;</li>
      <li>гибочные шаблоны: 7 шт. в комплектации до 2" или 6 шт. в комплектации до 1.5";</li>
      <li>переходная втулка;</li>
      <li>транспортировочный ящик и руководство по эксплуатации.</li>
      </ul>
      <p>Поставляем трубогиб ТПГ-2Б по Казахстану. Добавьте его в запрос — подготовим коммерческое предложение с ценой и сроком поставки.</p>
    meta_title: Трубогиб гидравлический ТПГ-2Б купить в Астане
    meta_description: 'Ручной гидравлический трубогиб ТПГ-2Б для труб до 2": усилие 10 тс, шаблоны в комплекте. Цена и поставка по Казахстану — по запросу.'
    specs:
      - ["Наибольшее усилие гидроцилиндра, тс", "10"]
      - ["Наибольший ход штока, мм", "180"]
      - ["Усилие на рукоятке при максимальной нагрузке, кгс", "40"]
      - ["Масса, кг", "54"]
      - ["Габариты транспортировочного ящика, мм", "205×275×680"]
      - ["Шаблоны: диаметр трубы / радиус гибки, мм", "3/8\"/50, 1/2\"/65, 3/4\"/80, 1\"/100, 1.25\"/135, 1.5\"/150, 2\"/200"]
    images:
      - {file: tpg-2b/1.webp, alt: Трубогиб ручной гидравлический ТПГ-2Б}
```

**Пример готовой категории:**

```yaml
  - slug: pipe-benders
    name: Трубогибы
    sort_order: 10
    is_active: true
    meta_title: Трубогибы гидравлические купить в Астане
    meta_description: Ручные гидравлические и электрические трубогибы в Астане. Подбор модели под задачу и коммерческое предложение по запросу.
    seo_text: |
      <p>Трубогибы предназначены для холодной гибки стальных водогазопроводных труб и круглого проката при монтаже систем отопления, водоснабжения, газоснабжения и технологических трубопроводов. В каталоге представлены ручные гидравлические трубогибы для работы на объекте без электропитания, модели с электрической насосной станцией для регулярной гибки в цеху, ручные трубогибы для тонкостенных труб и трёхвалковый электромеханический трубогиб.</p>
      <p>При выборе трубогиба учитывайте наибольший диаметр трубы, толщину стенки, нужный радиус гибки и объём работ. Для разовых монтажных работ обычно достаточно ручной модели, при ежедневной нагрузке удобнее трубогиб с электроприводом. Если сомневаетесь, добавьте несколько подходящих моделей в запрос — мы перезвоним, уточним задачу и подготовим коммерческое предложение.</p>
```

**Пакеты товаров (по одному коммиту на пакет):**
- A (14): `tr-1, tr-25u, tpg-1b, tpg-1-25b, tpg-2b, tpg-3b, tpg-2ep, tpg-3ep, tg-3ep, tem-76x50, ogs-30, ogs-40, ogs-25ep-3, ogs-60-ep-6`
- B (19): `mgs-630-0-8-r-1, mgs-630-0-8p-r-1, mgs-700-0-8-r-1, mgs-700-0-8p-e-1, mgs-700-0-7p-e-1, mgs-700-0-8p-e-3, spring-return-cylinders, sg-5, sg-10, sg-15, sg-20, sg-30, sg-50, sg-5n, sg-10n, sg-20n, sg-30n, sg-50n, sg-100n`
- C (8): `tt-3, tr-2, pipe-threading-die-heads, pgg-10, pgg-15ep, da-5-50, dg-dn-dp, lr-1-2`
- D (9): `sshg, shgg, shdg-31n-35n, shrg-150n-200n, hydraulic-angle-cutter, rfv-rfg, ag-25n-32n-40n, tsrg-20a, tsrg-30-48`

- [ ] **Step 1: Написать тест валидации контента**

`tests/test_content_file.py`:
```python
import json
import re
from pathlib import Path

import pytest
import yaml
from bs4 import BeautifulSoup

from catalog.sanitize import ALLOWED_TAGS

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content" / "catalog.yaml"
LEGACY = ROOT / "legacy" / "products.json"
IMAGES = ROOT / "content" / "images"

SPEC_CATEGORY_SLUGS = {
    "pipe-benders", "pressure-test-pumps", "vises", "pipe-cutters", "winches", "hydraulic-presses",
    "pipe-threading-dies", "hydraulic-power-units", "hydraulic-cylinders", "hydraulic-bearing-pullers",
    "jacks", "busbar-machines", "busbar-benders", "busbar-punches", "busbar-cutters", "angle-cutters",
    "flange-spreaders", "rebar-benders", "cable-cutters", "pressure-testers", "machines",
}
REMOVED_LEGACY = {26: "hydraulic-bearing-pullers"}
PRODUCT_KEYS = {
    "slug", "legacy_ids", "category", "name", "model_code", "sort_order", "is_active", "needs_review",
    "short_description", "description", "meta_title", "meta_description", "specs", "images",
}
CATEGORY_KEYS = {"slug", "name", "sort_order", "is_active", "meta_title", "meta_description", "seo_text"}
DRAFT_KEYS = {"source_text", "source_tables", "source_image_urls"}
NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
MIXED_SCRIPT_RE = re.compile(r"[А-Яа-яЁё][A-Za-z]|[A-Za-z][А-Яа-яЁё]")
FORBIDDEN_RE = re.compile(r"инстан|instan", re.IGNORECASE)


@pytest.fixture(scope="module")
def content() -> dict:
    return yaml.safe_load(CONTENT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def legacy() -> dict[int, dict]:
    return {p["id"]: p for p in json.loads(LEGACY.read_text(encoding="utf-8"))}


def plain(html: str | None) -> str:
    return " ".join(BeautifulSoup(html or "", "html.parser").get_text(" ").split())


def numbers(text: str) -> set[str]:
    return {n.replace(",", ".") for n in NUMBER_RE.findall(text or "")}


def source_numbers(records: list[dict]) -> set[str]:
    return set().union(*(numbers(r["name"] + " " + plain(r.get("description"))) for r in records)) if records else set()


def html_errors(value: str, where: str) -> list[str]:
    errors = []
    for tag in BeautifulSoup(value or "", "html.parser").find_all(True):
        if tag.name not in ALLOWED_TAGS:
            errors.append(f"{where}: тег <{tag.name}> запрещён")
        allowed_attrs = {"href"} if tag.name == "a" else set()
        if set(tag.attrs) - allowed_attrs:
            errors.append(f"{where}: атрибуты {sorted(tag.attrs)} у <{tag.name}> запрещены")
    return errors


def text_errors(text: str, where: str) -> list[str]:
    errors = []
    if FORBIDDEN_RE.search(text):
        errors.append(f"{where}: упоминание производителя")
    if MIXED_SCRIPT_RE.search(text):
        errors.append(f"{where}: смешение латиницы и кириллицы: {MIXED_SCRIPT_RE.search(text).group()!r}")
    return errors


def product_errors(product: dict, legacy: dict[int, dict]) -> list[str]:
    slug = product.get("slug", "?")
    errors = []
    if missing := PRODUCT_KEYS - set(product):
        return [f"{slug}: нет полей {sorted(missing)}"]
    if leftovers := DRAFT_KEYS & set(product):
        errors.append(f"{slug}: остались поля черновика {sorted(leftovers)}")
    if product["category"] not in SPEC_CATEGORY_SLUGS:
        errors.append(f"{slug}: неизвестная категория {product['category']}")
    records = [legacy[i] for i in product["legacy_ids"] if i in legacy]
    if len(records) != len(product["legacy_ids"]):
        errors.append(f"{slug}: legacy_ids не найдены в снимке")

    if not 20 <= len(product["short_description"]) <= 300:
        errors.append(f"{slug}: short_description {len(product['short_description'])} символов (нужно 20–300)")
    word_count = len(plain(product["description"]).split())
    min_words = 60 if product["needs_review"] else 150
    if not min_words <= word_count <= 300:
        errors.append(f"{slug}: description {word_count} слов (нужно {min_words}–300)")
    if not 0 < len(product["meta_title"]) <= 60:
        errors.append(f"{slug}: meta_title {len(product['meta_title'])} символов (нужно 1–60)")
    if not 70 <= len(product["meta_description"]) <= 160:
        errors.append(f"{slug}: meta_description {len(product['meta_description'])} символов (нужно 70–160)")
    errors += html_errors(product["description"], f"{slug}.description")

    spec_texts = []
    for spec in product["specs"]:
        if not (isinstance(spec, list) and len(spec) == 2 and all(str(part).strip() for part in spec)):
            errors.append(f"{slug}: характеристика {spec!r} должна быть парой непустых строк")
            continue
        spec_texts += [str(spec[0]), str(spec[1])]

    written = " ".join(
        [product["name"], product["short_description"], plain(product["description"]),
         product["meta_title"], product["meta_description"], *spec_texts]
    )
    errors += text_errors(written, slug)

    allowed_numbers = source_numbers(records) | numbers(product["name"] + " " + product["model_code"])
    if invented := numbers(written) - allowed_numbers:
        errors.append(f"{slug}: числа не из источника: {sorted(invented)}")

    for image in product["images"]:
        if not (IMAGES / image["file"]).exists():
            errors.append(f"{slug}: нет файла {image['file']}")
        if not image.get("alt"):
            errors.append(f"{slug}: пустой alt у {image['file']}")
    return errors


def test_products_are_valid(content, legacy):
    errors = []
    slugs = [p.get("slug") for p in content["products"]]
    if len(slugs) != len(set(slugs)):
        errors.append("повторяющиеся slug товаров")
    for product in content["products"]:
        errors += product_errors(product, legacy)
    assert not errors, "\n".join(errors)


def test_categories_are_valid(content, legacy):
    errors = []
    for category in content["categories"]:
        slug = category.get("slug", "?")
        if missing := CATEGORY_KEYS - set(category):
            errors.append(f"{slug}: нет полей {sorted(missing)}")
            continue
        if slug not in SPEC_CATEGORY_SLUGS:
            errors.append(f"{slug}: slug не из спеки")
        if category["is_active"]:
            words = len(plain(category["seo_text"]).split())
            if not 100 <= words <= 200:
                errors.append(f"{slug}: seo_text {words} слов (нужно 100–200)")
            if not 0 < len(category["meta_title"]) <= 60:
                errors.append(f"{slug}: meta_title {len(category['meta_title'])} символов (нужно 1–60)")
            if not 70 <= len(category["meta_description"]) <= 160:
                errors.append(f"{slug}: meta_description {len(category['meta_description'])} символов")
        errors += html_errors(category["seo_text"], f"{slug}.seo_text")
        written = " ".join([category["name"], plain(category["seo_text"]), category["meta_title"], category["meta_description"]])
        errors += text_errors(written, slug)
        legacy_ids = [i for p in content["products"] if p["category"] == slug for i in p["legacy_ids"]]
        legacy_ids += [i for i, target in REMOVED_LEGACY.items() if target == slug]
        records = [legacy[i] for i in legacy_ids if i in legacy]
        if invented := numbers(written) - source_numbers(records):
            errors.append(f"{slug}: числа не из источника: {sorted(invented)}")
    assert not errors, "\n".join(errors)


def test_catalog_is_complete(content, legacy):
    assert {c["slug"] for c in content["categories"]} == SPEC_CATEGORY_SLUGS
    assert len(content["products"]) == 50
    covered = {i for p in content["products"] for i in p["legacy_ids"]}
    assert covered == set(legacy) - set(REMOVED_LEGACY)
```

- [ ] **Step 2: Создать пустой файл и проверить, что тест полноты падает**

`content/catalog.yaml`:
```yaml
categories: []
products: []
```

Run: `uv run pytest tests/test_content_file.py`
Expected: `test_products_are_valid` и `test_categories_are_valid` — PASS (пустые списки); `test_catalog_is_complete` — FAIL.

- [ ] **Step 3: Пакет A — написать 14 товаров**

Для каждого slug из пакета A: взять запись из `content/catalog.draft.yaml`, прочитать `source_text` и `source_tables`, написать поля по правилам 1–10 и примеру `tpg-2b`, добавить запись в `products:` файла `content/catalog.yaml` (без полей `source_*`).

Run: `uv run pytest tests/test_content_file.py -k "not complete"`
Expected: PASS. При ошибке «числа не из источника» — убрать или исправить число (правило 3), не добавлять его в источник.

```bash
git add content/catalog.yaml tests/test_content_file.py
git commit -m "content: rewrite pipe benders and pressure testing products"
```

- [ ] **Step 4: Пакет B — 19 товаров**

Тот же порядок действий для пакета B. У моделей СГ-…Н, объединённых из двух записей, `source_text` содержит оба исходника через `---`: писать один текст, не дублируя.

Run: `uv run pytest tests/test_content_file.py -k "not complete"` → PASS.

```bash
git add content/catalog.yaml
git commit -m "content: rewrite hydraulic power units, cylinders and bearing pullers"
```

- [ ] **Step 5: Пакет C — 8 товаров**

Для `da-5-50` таблицу моделей ДА5…ДА50 из `source_tables` перенести в `description` как `<table>` (правило 4).

Run: `uv run pytest tests/test_content_file.py -k "not complete"` → PASS.

```bash
git add content/catalog.yaml
git commit -m "content: rewrite vises, cutters, threading dies, presses, jacks and winches"
```

- [ ] **Step 6: Пакет D — 9 товаров**

Run: `uv run pytest tests/test_content_file.py -k "not complete"` → PASS.

```bash
git add content/catalog.yaml
git commit -m "content: rewrite busbar, angle, flange, rebar and cable tools"
```

- [ ] **Step 7: 21 категория**

Написать `categories:` по правилу 11 и примеру `pipe-benders`; `sort_order`, `name`, `is_active` взять из черновика.

Run: `uv run pytest tests/test_content_file.py`
Expected: `3 passed`.

- [ ] **Step 8: Загрузить локально и просмотреть**

```bash
uv run python manage.py import_catalog
uv run python manage.py runserver
```
Expected: `Категорий: создано 21…`, `Товаров: создано 50…`, список `Не найдены фото` пуст. Открыть 5 случайных товаров и 3 категории: текст читается, таблицы не ломают вёрстку на 360 px.

- [ ] **Step 9: Commit**

```bash
git add content/catalog.yaml
git commit -m "content: rewrite category SEO texts"
```

---

### Task 18: Перенос старых заявок

**Files:**
- Create: `orders/management/__init__.py`, `orders/management/commands/__init__.py`, `orders/management/commands/import_legacy_requests.py`
- Test: `tests/test_import_legacy_requests.py`

**Interfaces:**
- Consumes: `content/catalog.yaml` (поле `legacy_ids`), `normalize_phone`, `QuoteRequest`, `QuoteItem`, `Product`.
- Produces: `python manage.py import_legacy_requests DUMP --date YYYY-MM-DD [--content PATH]`. `DUMP` — вывод `pg_dump --data-only --table=public.request` (plain SQL с блоком `COPY`). Повторный запуск не создаёт дублей (метка `legacy:<id>` в начале `admin_note`). `created_at` = полночь `--date` (Asia/Almaty) + старый id в секундах — сохраняет порядок старых заявок.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_import_legacy_requests.py`:
```python
import json
from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo

import pytest
import yaml
from django.core.management import CommandError, call_command

from orders.models import QuoteRequest
from tests.factories import make_product

pytestmark = pytest.mark.django_db


def copy_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")


@pytest.fixture
def files(tmp_path):
    items = [
        {"id": 10, "name": "Трубогиб ручной гидравлический ИНСТАН ТПГ-2Б", "price": 86300.0},
        {"id": 10, "name": "Трубогиб ручной гидравлический ИНСТАН ТПГ-2Б", "price": 86300.0},
        {"id": 999, "name": "Снятый товар", "price": 0.0},
    ]
    rows = [
        ["7", "Иван\\Петров", "8 777 305 42 43", json.dumps(items, ensure_ascii=False)],
        ["8", "Без телефона", "12", "[]"],
    ]
    dump = "\n".join(
        [
            "SET statement_timeout = 0;",
            "COPY public.request (id, customer_name, customer_phone, product_list) FROM stdin;",
            *["\t".join(copy_escape(v) for v in row) for row in rows],
            "\\.",
            "",
        ]
    )
    dump_path = tmp_path / "request.sql"
    dump_path.write_text(dump, encoding="utf-8")
    content_path = tmp_path / "catalog.yaml"
    content_path.write_text(
        yaml.safe_dump({"categories": [], "products": [{"slug": "tpg-2b", "legacy_ids": [10]}]}, allow_unicode=True),
        encoding="utf-8",
    )
    return {"dump": dump_path, "content": content_path}


def run(files) -> str:
    out = StringIO()
    call_command(
        "import_legacy_requests", str(files["dump"]), date="2025-06-01", content=str(files["content"]), stdout=out
    )
    return out.getvalue()


def test_imports_requests_as_closed_with_grouped_items(files):
    product = make_product(slug="tpg-2b")
    output = run(files)

    quote = QuoteRequest.objects.get(admin_note__startswith="legacy:7 ")
    assert quote.name == "Иван\\Петров"
    assert quote.phone == "+77773054243"
    assert quote.status == QuoteRequest.Status.CLOSED
    assert quote.email_sent is True
    assert quote.created_at == datetime(2025, 6, 1, 0, 0, 7, tzinfo=ZoneInfo("Asia/Almaty"))
    items = [(i.product_id, i.product_name, i.quantity) for i in quote.items.all()]
    assert items == [
        (product.pk, "Трубогиб ручной гидравлический ИНСТАН ТПГ-2Б", 2),
        (None, "Снятый товар", 1),
    ]
    assert "Импортировано: 2" in output


def test_unparseable_phone_kept_as_is(files):
    run(files)
    assert QuoteRequest.objects.get(admin_note__startswith="legacy:8 ").phone == "12"


def test_second_run_skips_existing(files):
    run(files)
    output = run(files)
    assert QuoteRequest.objects.count() == 2
    assert "Пропущено (уже импортированы): 2" in output


def test_missing_copy_block_is_error(files):
    files["dump"].write_text("SELECT 1;\n", encoding="utf-8")
    with pytest.raises(CommandError, match="COPY"):
        run(files)
```

- [ ] **Step 2: Запустить — должны упасть**

Run: `uv run pytest tests/test_import_legacy_requests.py`
Expected: FAIL, `Unknown command: 'import_legacy_requests'`.

- [ ] **Step 3: Реализация**

`orders/management/__init__.py`, `orders/management/commands/__init__.py`: пустые файлы.

`orders/management/commands/import_legacy_requests.py`:
```python
import json
import re
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Product
from orders.models import QuoteItem, QuoteRequest
from orders.services import MAX_QTY, normalize_phone

COPY_RE = re.compile(r"^COPY (?:public\.)?request \(([^)]*)\) FROM stdin;$")
ESCAPES = {"t": "\t", "n": "\n", "r": "\r", "\\": "\\"}


def unescape_copy(value: str) -> str | None:
    if value == r"\N":
        return None
    return re.sub(r"\\(.)", lambda m: ESCAPES.get(m.group(1), m.group(1)), value)


def parse_copy_rows(text: str) -> list[dict]:
    columns = None
    rows = []
    for line in text.splitlines():
        if columns is None:
            match = COPY_RE.match(line.strip())
            if match:
                columns = [column.strip() for column in match.group(1).split(",")]
            continue
        if line == r"\.":
            break
        rows.append(dict(zip(columns, (unescape_copy(v) for v in line.split("\t")), strict=True)))
    if columns is None:
        raise CommandError("В дампе не найден блок COPY для таблицы request")
    return rows


class Command(BaseCommand):
    help = "Переносит заявки из pg_dump старой таблицы request как закрытые."

    def add_arguments(self, parser):
        parser.add_argument("dump")
        parser.add_argument("--date", required=True, type=date.fromisoformat)
        parser.add_argument("--content", default=str(Path(settings.BASE_DIR) / "content" / "catalog.yaml"))

    def handle(self, *args, **options):
        rows = parse_copy_rows(Path(options["dump"]).read_text(encoding="utf-8"))
        content = yaml.safe_load(Path(options["content"]).read_text(encoding="utf-8"))
        slug_by_legacy_id = {i: p["slug"] for p in content["products"] for i in p.get("legacy_ids", [])}
        products = Product.objects.in_bulk(set(slug_by_legacy_id.values()), field_name="slug")
        base_time = datetime.combine(options["date"], time(0), tzinfo=ZoneInfo(settings.TIME_ZONE))

        imported = skipped = 0
        with transaction.atomic():
            for row in rows:
                legacy_id = int(row["id"])
                marker = f"legacy:{legacy_id} "
                if QuoteRequest.objects.filter(admin_note__startswith=marker).exists():
                    skipped += 1
                    continue

                raw_phone = row.get("customer_phone") or ""
                quote = QuoteRequest.objects.create(
                    name=(row.get("customer_name") or "Без имени")[:100],
                    phone=normalize_phone(raw_phone) or raw_phone[:16],
                    status=QuoteRequest.Status.CLOSED,
                    email_sent=True,
                    admin_note=f"{marker}Перенесено со старого сайта.",
                    created_at=base_time + timedelta(seconds=legacy_id),
                )

                try:
                    entries = json.loads(row.get("product_list") or "[]")
                except ValueError:
                    entries = []
                counts: Counter = Counter()
                names: dict[int, str] = {}
                for entry in entries:
                    if isinstance(entry, dict) and isinstance(entry.get("id"), int):
                        counts[entry["id"]] += 1
                        names.setdefault(entry["id"], str(entry.get("name") or f"Товар #{entry['id']}"))
                QuoteItem.objects.bulk_create(
                    [
                        QuoteItem(
                            request=quote,
                            product=products.get(slug_by_legacy_id.get(old_id)),
                            product_name=names[old_id][:255],
                            quantity=min(count, MAX_QTY),
                        )
                        for old_id, count in counts.items()
                    ]
                )
                imported += 1

        self.stdout.write(f"Импортировано: {imported}\nПропущено (уже импортированы): {skipped}")
```

- [ ] **Step 4: Запустить тесты**

Run: `uv run pytest tests/test_import_legacy_requests.py`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add orders/management tests/test_import_legacy_requests.py
git commit -m "feat(orders): add import of legacy quote requests from pg_dump"
```

---
### Task 19: Docker, настройки продакшена и инструкция по деплою

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `deploy/entrypoint.sh`, `deploy/backup.sh`, `deploy/Caddyfile.example`, `deploy/DEPLOY.md`
- Modify: `compose.yml` (добавить сервис `web`)
- Test: `tests/test_deploy_settings.py`

**Interfaces:**
- Consumes: все предыдущие задачи; команды `import_catalog`, `import_legacy_requests`.
- Produces: образ `web` (gunicorn на `:8000` внутри контейнера, наружу `127.0.0.1:${WEB_PORT:-8001}`); `deploy/DEPLOY.md` — пошаговая инструкция для владельца.

> Спека §3 (уточнено): `collectstatic` выполняется при сборке образа, а не в entrypoint — статика неизменна для образа, а контейнер работает от непривилегированного пользователя.

- [ ] **Step 1: Написать падающий тест**

`tests/test_deploy_settings.py`:
```python
import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_production_settings_pass_deploy_checks():
    env = {
        **os.environ,
        "DEBUG": "False",
        "SECRET_KEY": secrets.token_urlsafe(64),
        "ALLOWED_HOSTS": "prom-products.kz",
        "CSRF_TRUSTED_ORIGINS": "https://prom-products.kz",
        "SITE_URL": "https://prom-products.kz",
        "ADMIN_URL": "panel-test/",
    }
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        cwd=ROOT, env=env, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_deploy_files_exist_with_lf_endings():
    for name in ["Dockerfile", ".dockerignore", "deploy/entrypoint.sh", "deploy/backup.sh",
                 "deploy/Caddyfile.example", "deploy/DEPLOY.md"]:
        path = ROOT / name
        assert path.exists(), name
        if name.endswith(".sh"):
            assert b"\r\n" not in path.read_bytes(), f"{name} must use LF line endings"


def test_compose_binds_web_to_localhost_only():
    compose = (ROOT / "compose.yml").read_text(encoding="utf-8")
    assert '"127.0.0.1:${WEB_PORT:-8001}:8000"' in compose
    assert "5432:5432" not in compose
```

- [ ] **Step 2: Запустить — должны упасть**

Run: `uv run pytest tests/test_deploy_settings.py`
Expected: `test_production_settings_pass_deploy_checks` — PASS (настройки готовы с Task 1), остальные два — FAIL (файлов нет). Если первый тест падает, вывод покажет, какую проверку `security.*` поправить в `config/settings.py`.

- [ ] **Step 3: Dockerfile и .dockerignore**

Узнать версию uv: `uv --version` (например, `uv 0.8.17`) и подставить её в `ARG UV_VERSION`.

`Dockerfile`:
```dockerfile
FROM python:3.12-slim

ARG UV_VERSION=0.8.17
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
    && mkdir -p /app/media \
    && chown app /app/media
USER app

EXPOSE 8000
ENTRYPOINT ["sh", "/app/deploy/entrypoint.sh"]
```

`.dockerignore`:
```
.git
.venv
.env
media
staticfiles
.pytest_cache
.ruff_cache
**/__pycache__
docs
tests
*.sql
*.dump
```

- [ ] **Step 4: Entrypoint и compose**

`deploy/entrypoint.sh`:
```sh
#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py createcachetable

exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 60 \
    --access-logfile -
```

`compose.yml` (файл целиком):
```yaml
services:
  db:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-promproduct}
      POSTGRES_USER: ${POSTGRES_USER:-promproduct}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in .env}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      retries: 10

  web:
    build: .
    restart: unless-stopped
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "127.0.0.1:${WEB_PORT:-8001}:8000"
    volumes:
      - ./media:/app/media

volumes:
  pgdata:
```

- [ ] **Step 5: Бэкапы и Caddy**

`deploy/backup.sh`:
```sh
#!/bin/sh
# Ежесуточный бэкап: БД (pg_dump custom) + медиа. Хранение 14 дней.
set -eu

APP_DIR=/opt/promproduct
BACKUP_DIR=/var/backups/promproduct
KEEP_DAYS=14
STAMP=$(date +%Y%m%d-%H%M%S)

mkdir -p "$BACKUP_DIR"
cd "$APP_DIR"

docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
    > "$BACKUP_DIR/db-$STAMP.dump"
tar -czf "$BACKUP_DIR/media-$STAMP.tar.gz" -C "$APP_DIR" media

find "$BACKUP_DIR" -type f -mtime +"$KEEP_DAYS" -delete
echo "Backup $STAMP done"
```

`deploy/Caddyfile.example`:
```caddy
# Общий блок нового сайта. Путь к media — каталог проекта на сервере.
(promproduct_app) {
	encode zstd gzip
	handle_path /media/* {
		root * /opt/promproduct/media
		file_server
	}
	handle {
		reverse_proxy 127.0.0.1:8001
	}
}

# ЭТАП 1 — стенд. Хеш пароля: caddy hash-password --plaintext 'пароль'
new.prom-products.kz {
	basic_auth {
		preview ВСТАВИТЬ_ХЕШ_ИЗ_caddy_hash-password
	}
	header X-Robots-Tag "noindex, nofollow"
	import promproduct_app
}

# ЭТАП 2 — после переключения: заменить блок стенда и старый блок prom-products.kz на эти три
# prom-products.kz {
# 	import promproduct_app
# }
# www.prom-products.kz {
# 	redir https://prom-products.kz{uri} permanent
# }
# new.prom-products.kz {
# 	redir https://prom-products.kz{uri} permanent
# }
```

- [ ] **Step 6: Инструкция `deploy/DEPLOY.md`**

````markdown
# Деплой prom-products.kz

Все команды выполняются на сервере `93.115.14.68` под пользователем с правами на Docker.
Проект размещается в `/opt/promproduct`.

## 0. Подготовка (один раз)

1. Отозвать старый пароль приложения Gmail (Google-аккаунт → Безопасность → Пароли приложений) и создать новый.
2. В DNS домена добавить A-запись `new.prom-products.kz` → `93.115.14.68`.
3. Проверить Docker: `docker compose version`.
4. Узнать, как запущен Caddy: `systemctl status caddy` (служба) или `docker ps | grep -i caddy` (контейнер).
   Если Caddy в контейнере — каталог `/opt/promproduct/media` нужно примонтировать в него по тому же пути.

## 1. Код и настройки

```sh
sudo mkdir -p /opt/promproduct && sudo chown "$USER" /opt/promproduct
git clone <адрес репозитория: git remote get-url origin на рабочем компьютере> /opt/promproduct
cd /opt/promproduct
git checkout rewrite
cp .env.example .env
mkdir -p media && sudo chown 1000:1000 media
```

Сгенерировать секреты:
```sh
openssl rand -base64 48 | tr -d '\n=/+' ; echo   # SECRET_KEY
openssl rand -hex 24                             # POSTGRES_PASSWORD
openssl rand -hex 6                              # суффикс адреса админки
```

Заполнить `.env`:
```dotenv
DEBUG=False
SECRET_KEY=<первая строка>
ALLOWED_HOSTS=prom-products.kz,new.prom-products.kz
CSRF_TRUSTED_ORIGINS=https://prom-products.kz,https://new.prom-products.kz
SITE_URL=https://new.prom-products.kz
ADMIN_URL=panel-<суффикс>/
POSTGRES_DB=promproduct
POSTGRES_USER=promproduct
POSTGRES_PASSWORD=<вторая строка>
DATABASE_URL=postgres://promproduct:<вторая строка>@db:5432/promproduct
CACHE_BACKEND=django.core.cache.backends.db.DatabaseCache
CACHE_LOCATION=django_cache
EMAIL_URL=submission://<логин>%40gmail.com:<новый пароль приложения без пробелов>@smtp.gmail.com:587
DEFAULT_FROM_EMAIL=<логин>@gmail.com
ADMIN_EMAIL=<почта для заявок>
MEDIA_ROOT=/app/media
WEB_PORT=8001
```
Адрес админки (`ADMIN_URL`) никому не публиковать.

## 2. Запуск стенда

```sh
docker compose up -d --build
docker compose ps                    # db — healthy, web — running
docker compose logs web --tail 50    # без ошибок, строка "Listening at: http://0.0.0.0:8000"
curl -sI http://127.0.0.1:8001/ | head -1   # HTTP/1.1 200 OK
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py import_catalog
```
Последняя команда печатает `Категорий: создано 21`, `Товаров: создано 50`, пустой список «Не найдены фото».

## 3. Caddy для стенда

1. Сделать копию: `sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak-$(date +%F)`.
2. Получить хеш пароля стенда: `caddy hash-password --plaintext '<пароль для просмотра>'`.
3. Добавить в `/etc/caddy/Caddyfile` блоки `(promproduct_app)` и `new.prom-products.kz` из `deploy/Caddyfile.example` (ЭТАП 1), подставив хеш. В Caddy старше 2.8 директива называется `basicauth`.
4. `caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy`
5. Открыть `https://new.prom-products.kz` — запрашивается логин `preview` и пароль, сайт открывается.

## 4. Проверка стенда (до переключения)

- [ ] Админка `https://new.prom-products.kz/panel-<суффикс>/`: в «Настройки сайта» указать email для заявок, телефоны, часы работы (`Mo-Fr 09:00-18:00`), БИН, ссылку на 2GIS.
- [ ] Создать группу пользователей не нужно — группа «Менеджер» уже есть; менеджеру создать пользователя со статусом «Персонал» и добавить в группу.
- [ ] Внести цены (₸) и включить «Показывать цену» там, где нужно.
- [ ] **Вычитка контента специалистом (блокирующий шаг):** пройти все 50 товаров и 21 категорию; правки вносить в админке. Если найдены ошибки в характеристиках — исправить в админке и сообщить разработчику, чтобы поправить `content/catalog.yaml`.
- [ ] Чек-лист корзины: добавить товар, повторно добавить, изменить количество, удалить, отправить с неверным телефоном (ошибка), отправить корректно → письмо пришло на указанный email, заявка есть в админке.
- [ ] На телефоне (ширина ~360 px): главная, категория, товар, запрос — без горизонтальной прокрутки.
- [ ] Chrome DevTools → Lighthouse → Mobile → страница товара: Performance ≥ 90, SEO ≥ 90 (предупреждение SEO о `noindex` на стенде ожидаемо).

## 5. Переключение домена

```sh
cd /opt/promproduct
# 1. Дамп старых заявок (контейнер старой БД называется postgresql-db)
docker exec postgresql-db pg_dump -U appuser -d appdb --data-only --table=public.request > legacy_requests.sql
docker compose cp legacy_requests.sql web:/tmp/legacy_requests.sql
docker compose exec web python manage.py import_legacy_requests /tmp/legacy_requests.sql --date $(date +%F)

# 2. Основной домен в настройках
sed -i 's#^SITE_URL=.*#SITE_URL=https://prom-products.kz#' .env
docker compose up -d
```

3. В `/etc/caddy/Caddyfile` удалить старый блок `prom-products.kz` (тот, что проксирует на старые контейнеры) и блок стенда, вставить три блока ЭТАПА 2 из `deploy/Caddyfile.example`.
4. `caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy`
5. Проверить: `curl -sI https://prom-products.kz/ | head -1` → `200`; `curl -sI https://www.prom-products.kz/ | grep -i location` → `https://prom-products.kz/`; `curl -s https://prom-products.kz/robots.txt` содержит `Sitemap: https://prom-products.kz/sitemap.xml`.
6. Остановить старые контейнеры (не удалять): `docker stop promproduct-app frontend postgresql-db`.

**Откат (в течение 7 дней):** вернуть `Caddyfile` из копии `Caddyfile.bak-…`, `docker start postgresql-db promproduct-app frontend`, `sudo systemctl reload caddy`.

Через 7 дней без проблем: `docker rm promproduct-app frontend postgresql-db` (volume старой БД оставить ещё на месяц).

## 6. Бэкапы

```sh
chmod +x /opt/promproduct/deploy/backup.sh
sudo mkdir -p /var/backups/promproduct
/opt/promproduct/deploy/backup.sh              # проверить, что появились db-*.dump и media-*.tar.gz
( crontab -l 2>/dev/null; echo "30 3 * * * /opt/promproduct/deploy/backup.sh >> /var/log/promproduct-backup.log 2>&1" ) | crontab -
```

Восстановление:
```sh
cd /opt/promproduct
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < /var/backups/promproduct/db-<дата>.dump
sudo tar -xzf /var/backups/promproduct/media-<дата>.tar.gz -C /opt/promproduct
```

## 7. Обновление кода

```sh
cd /opt/promproduct && git pull && docker compose up -d --build
```
**Не запускать `import_catalog` после запуска сайта** без необходимости: команда перезаписывает тексты и фото товаров из `content/catalog.yaml` (цены сохраняются), правки из админки будут потеряны.

## 8. После запуска (SEO-чек-лист)

- [ ] Google Search Console: подтвердить домен, отправить `https://prom-products.kz/sitemap.xml`.
- [ ] Яндекс Вебмастер: то же самое.
- [ ] Google Business Profile на адрес в Астане с сайтом и телефонами.
- [ ] Карточка компании в 2GIS со ссылкой на сайт.
- [ ] Ссылки на сайт с satu.kz и отраслевых каталогов.
- [ ] Через 2–4 недели проверить в Search Console отчёт «Страницы»: все 50 товаров проиндексированы.
````

- [ ] **Step 7: Запустить тесты и линтер**

```bash
uv run pytest
uv run ruff check .
```
Expected: все тесты проходят; ruff без ошибок.

- [ ] **Step 8: Проверить сборку образа локально**

```bash
docker compose build web
docker run --rm --env-file .env -e DEBUG=False -e ALLOWED_HOSTS=localhost --entrypoint python promproduct-web manage.py check --deploy
```
Expected: сборка успешна (`collectstatic` без ошибок); `check --deploy` выводит `System check identified no issues`. Имя образа `promproduct-web` — по имени каталога проекта; если отличается, взять из `docker compose images`.

- [ ] **Step 9: Commit**

```bash
git add Dockerfile .dockerignore compose.yml deploy tests/test_deploy_settings.py
git commit -m "chore(deploy): add Docker image, compose web service, backups and deployment guide"
```

---

## Проверка покрытия спеки

| Раздел спеки | Задачи |
|---|---|
| §1 Цель, проблемы старой версии | 1 (удаление кода), 5 (защищённая админка), 2 (XSS), 3/19 (нет seed при старте), 8 (SEO-страницы), 10–14 (количество, заявка) |
| §2 Решения | Global Constraints; 3–4 (`show_price`), 8 (английские URL), 12 (email), 19 (Docker + Caddy) |
| §3 Архитектура | 1, 19 |
| §4 Модель данных | 2, 3, 4, 10 |
| §5 Страницы и slug | 8, 9, 13, 15 (slug) |
| §6 Корзина и заявка | 10, 12, 13, 14 |
| §7 Админка | 5, 11 |
| §8 SEO, визуальный стиль | 6 (макет + согласование), 7, 8, 9, 19 (Lighthouse в DEPLOY.md) |
| §9 Контент и импорт, старые заявки | 15, 16, 17, 18 |
| §10 Безопасность | 1 (настройки, .gitignore), 2, 5 (axes), 13 (rate limit, honeypot), 19 (check --deploy) |
| §11 Тестирование | тесты в каждой задаче; ручной чек-лист — 14 и DEPLOY.md |
| §12 Деплой и переключение | 19 (DEPLOY.md) |
