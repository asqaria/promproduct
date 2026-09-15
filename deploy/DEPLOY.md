# Деплой prom-products.kz

Все команды выполняются на сервере `93.115.14.68` под пользователем с правами на Docker.
Проект размещается в `/opt/promproduct`.

## 0. Подготовка (один раз)

1. Отозвать старый пароль приложения Gmail (Google-аккаунт → Безопасность → Пароли приложений) и создать новый.
2. В DNS домена добавить A-запись `new.prom-products.kz` → `93.115.14.68`.
3. Проверить Docker: `docker compose version`.
4. Узнать, как запущен Caddy — от этого зависят команды в §3 и §5:
   - **Служба на хосте:** `systemctl status caddy` — если найдена, конфиг лежит в `/etc/caddy/Caddyfile`, применяется через `sudo systemctl reload caddy`.
   - **Контейнер:** `docker ps | grep -i caddy` (обычно называется `caddy`) — если так:
     - Путь к Caddyfile на хосте: `docker inspect caddy --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'`. Редактировать файл по пути `{{.Source}}` на хосте — в контейнере он смонтирован в `{{.Destination}}` (обычно `/etc/caddy/Caddyfile`).
     - Валидация и применение — командами внутри контейнера: `docker exec caddy caddy validate --config /etc/caddy/Caddyfile` и `docker exec caddy caddy reload --config /etc/caddy/Caddyfile` (systemd в контейнере нет).
     - Каталог `/opt/promproduct/media` нужно примонтировать в контейнер Caddy по тому же пути (добавить том в его конфигурацию — `docker-compose.yml` или `docker run` — и пересоздать контейнер Caddy).
     - Контейнеру Caddy нужен доступ к `web`: изнутри контейнера `127.0.0.1:8001` указывает на сам контейнер, а не на хост, где слушает `web`. Проверить, что уже настроено: `docker inspect caddy --format '{{.HostConfig.ExtraHosts}}'`.
       - Если там уже есть `host.docker.internal:host-gateway` — в Caddyfile проксировать на `host.docker.internal:8001`.
       - Если пусто — либо пересоздать контейнер Caddy с `--add-host host.docker.internal:host-gateway` и проксировать на тот же адрес, либо (без пересоздания Caddy) узнать адрес моста Docker: `docker network inspect bridge --format '{{(index .IPAM.Config 0).Gateway}}'` и проксировать на `<адрес-моста>:8001`.
       - Если у Caddy есть свой `docker-compose.yml`, который можно подключить к сети проекта (`docker network connect <сеть_проекта> caddy`; имя сети — `docker compose ps --format '{{.Networks}}'` в `/opt/promproduct`), проще всего проксировать прямо на `web:8000` по имени сервиса — тогда `host.docker.internal`/адрес моста не нужны.

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

Хеш пароля стенда — общий для обоих вариантов ниже:
```sh
caddy hash-password --plaintext '<пароль для просмотра>'
```
Если Caddy в контейнере и на хосте нет бинарника `caddy` — выполнить ту же команду внутри контейнера: `docker exec caddy caddy hash-password --plaintext '<пароль для просмотра>'`.

Блоки `(promproduct_app)` и `new.prom-products.kz` берутся из `deploy/Caddyfile.example` (ЭТАП 1), с подставленным хешем; в Caddy старше 2.8 директива называется `basicauth`. Адрес прокси `127.0.0.1:8001` в примере подходит только для Caddy-службы на хосте — для Caddy в контейнере вместо него подставить адрес из §0.4 (`host.docker.internal:8001`, адрес моста или `web:8000`).

**Caddy — служба на хосте:**
1. Копия: `sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak-$(date +%F)`.
2. Добавить блоки в `/etc/caddy/Caddyfile`.
3. `caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy`

**Caddy — контейнер:**
1. Копия: `sudo cp <путь к Caddyfile на хосте из §0.4> <тот же путь>.bak-$(date +%F)`.
2. Добавить блоки в этот файл (адрес прокси — см. выше).
3. `docker exec caddy caddy validate --config /etc/caddy/Caddyfile && docker exec caddy caddy reload --config /etc/caddy/Caddyfile`

Открыть `https://new.prom-products.kz` — запрашивается логин `preview` и пароль, сайт открывается.

## 4. Проверка стенда (до переключения)

- [ ] Админка `https://new.prom-products.kz/panel-<суффикс>/`: в «Настройки сайта» указать email для заявок, телефоны, часы работы (`Mo-Fr 09:00-18:00`), БИН, ссылку на 2GIS.
- [ ] Создать группу пользователей не нужно — группа «Менеджер» уже есть; менеджеру создать пользователя со статусом «Персонал» и добавить в группу.
- [ ] Внести цены (₸) и включить «Показывать цену» там, где нужно.
- [ ] **Вычитка контента специалистом (блокирующий шаг):** пройти все 50 товаров и 21 категорию; правки вносить в админке. Если найдены ошибки в характеристиках — исправить в админке и сообщить разработчику, чтобы поправить `content/catalog.yaml`.
- [ ] В первую очередь вычитать 20 товаров с пометкой `needs_review: true` в `content/catalog.yaml` (источники по ним были скудные), и отдельно перепроверить три фото `ag-25n-32n-40n` и текст категории «Тиски» на непроверенное утверждение «закалённая сталь лучше переносит постоянную нагрузку».
- [ ] Чек-лист корзины: добавить товар, повторно добавить, изменить количество, удалить, отправить с неверным телефоном (ошибка), отправить корректно → письмо пришло на указанный email, заявка есть в админке.
- [ ] На телефоне (ширина ~360 px): главная, категория, товар, запрос — без горизонтальной прокрутки.
- [ ] Chrome DevTools → Lighthouse → Mobile → страница товара: Performance ≥ 90, SEO ≥ 90 (предупреждение SEO о `noindex` на стенде ожидаемо).
- [ ] **Ручной чек-лист в браузере** (`uv run python manage.py runserver` локально или на стенде; консоль DevTools без ошибок, с товарами, созданными в админке):
  - [ ] 1. На главной нажать «В запрос» у карточки → уведомление; позиция появилась в правой панели; счётчик в мобильной панели = 1 (проверить на ширине < 1100 px).
  - [ ] 2. Повторно добавить тот же товар со страницы товара с количеством 3 → в панели одна позиция, количество 4.
  - [ ] 3. В панели изменить количество на 7 → перейти на другую страницу → 7 сохранилось; ввести 0 → 1; ввести 5000 → 999.
  - [ ] 4. Удалить позицию → «В запросе пока нет товаров», кнопка «Отправить запрос» неактивна, счётчик скрыт.
  - [ ] 5. Добавить товар, отправить форму из панели с телефоном `12345` → открывается `/quote/` с сообщением «Заявка не отправлена» и ошибкой у поля телефона в панели; список товаров на месте.
  - [ ] 6. Отправить с корректным телефоном → страница «Спасибо» с номером заявки; панель пуста; в консоли `runserver` напечатано письмо.
  - [ ] 7. На ширине 360 px: кнопка «Категории» открывает меню слева, фон затемняется; клик по фону и клавиша Escape закрывают меню; фокус возвращается на кнопку. Ссылка «Запрос» прокручивает к панели. Нет горизонтальной прокрутки.
  - [ ] 8. На ширине 1280 px: три колонки, левое меню и правая панель остаются на месте при прокрутке длинной главной.
  - [ ] 9. На странице товара с несколькими фото клик по миниатюре меняет главное фото.

## 5. Переключение домена

Порядок ниже важен: дамп заявок со старого сайта снимается **после** переключения Caddy на новый сайт, а не до. Пока Caddy проксирует `prom-products.kz` на старый стек, старый сайт продолжает принимать заявки — если снять дамп раньше, заявка, отправленная в промежутке между дампом и остановкой старого сайта, не попадёт ни в дамп, ни в новую БД и будет потеряна безвозвратно. Дамп становится окончательным только тогда, когда старый сайт уже не обслуживает трафик.

1. Основной домен в настройках и пересоздать `web`:
   ```sh
   cd /opt/promproduct
   sed -i 's#^SITE_URL=.*#SITE_URL=https://prom-products.kz#' .env
   docker compose up -d
   ```
2. Переключить Caddy на новый сайт: в конфиге (`/etc/caddy/Caddyfile` для службы на хосте или в файле из §0.4 для контейнера) удалить старый блок `prom-products.kz` (тот, что проксирует на старые контейнеры, включая старый admin API под `/api/` — после переключения он не должен обслуживаться) и блок стенда, вставить три блока ЭТАПА 2 из `deploy/Caddyfile.example` (адрес прокси в `(promproduct_app)` — как в §3, свой для каждой топологии Caddy).
   - Служба на хосте: `caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy`
   - Контейнер: `docker exec caddy caddy validate --config /etc/caddy/Caddyfile && docker exec caddy caddy reload --config /etc/caddy/Caddyfile`
3. Проверить, что новый сайт обслуживает трафик, а старый выключен из маршрутизации (только после этого старый сайт можно считать не принимающим заявки):
   ```sh
   curl -sI https://prom-products.kz/ | head -1                # 200
   curl -sI https://www.prom-products.kz/ | grep -i location   # https://prom-products.kz/
   curl -s https://prom-products.kz/robots.txt                 # содержит Sitemap: https://prom-products.kz/sitemap.xml
   curl -sI https://prom-products.kz/api/ | head -1             # старый admin API больше не отвечает (404 или соединение закрыто)
   ```
4. Только теперь снять дамп старых заявок — старый сайт больше не обслуживается, значит дамп финальный и ничего не потеряется (контейнер старой БД называется `postgresql-db`):
   ```sh
   docker exec postgresql-db pg_dump -U appuser -d appdb --data-only --table=public.request > legacy_requests.sql
   docker compose cp legacy_requests.sql web:/tmp/legacy_requests.sql
   docker compose exec web python manage.py import_legacy_requests /tmp/legacy_requests.sql --date $(date +%F)
   ```
5. Остановить старые контейнеры (не удалять): `docker stop promproduct-app frontend postgresql-db`.

**Откат (в течение 7 дней):** вернуть Caddyfile из копии `Caddyfile.bak-…` (`sudo cp` обратно в `/etc/caddy/Caddyfile` или в смонтированный файл для контейнера), `docker start postgresql-db promproduct-app frontend`, применить конфиг (`sudo systemctl reload caddy` для службы или `docker exec caddy caddy reload --config /etc/caddy/Caddyfile` для контейнера).

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

15 товаров сейчас без фото — их можно дозаполнить через админку в любой момент, это не требует `import_catalog` и не блокирует запуск.

## 8. После запуска (SEO-чек-лист)

- [ ] Google Search Console: подтвердить домен, отправить `https://prom-products.kz/sitemap.xml`.
- [ ] Яндекс Вебмастер: то же самое.
- [ ] Google Business Profile на адрес в Астане с сайтом и телефонами.
- [ ] Карточка компании в 2GIS со ссылкой на сайт.
- [ ] Ссылки на сайт с satu.kz и отраслевых каталогов.
- [ ] Через 2–4 недели проверить в Search Console отчёт «Страницы»: все 50 товаров проиндексированы.
