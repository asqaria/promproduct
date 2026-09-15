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
    required_columns = {"id", "customer_name", "customer_phone", "product_list"}

    for line_number, line in enumerate(text.splitlines(), 1):
        if columns is None:
            match = COPY_RE.match(line.strip())
            if match:
                columns = [column.strip() for column in match.group(1).split(",")]
                # Validate that all required columns are present
                missing = required_columns - set(columns)
                if missing:
                    raise CommandError(f"В блоке COPY нет колонок: {', '.join(sorted(missing))}")
            continue
        if line == r"\.":
            break
        try:
            rows.append(
                dict(zip(columns, (unescape_copy(v) for v in line.split("\t")), strict=True))
            )
        except ValueError as e:
            if "zip()" in str(e):
                actual_count = len(line.split("\t"))
                expected_count = len(columns)
                raise CommandError(
                    f"Строка {line_number} дампа: ожидалось {expected_count} полей, найдено {actual_count}"
                ) from e
            raise

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
        option_date = options["date"]
        if isinstance(option_date, str):
            option_date = date.fromisoformat(option_date)
        base_time = datetime.combine(option_date, time(0), tzinfo=ZoneInfo(settings.TIME_ZONE))

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
