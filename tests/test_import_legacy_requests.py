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
    content_yaml = {
        "categories": [],
        "products": [{"slug": "tpg-2b", "legacy_ids": [10]}],
    }
    content_path.write_text(
        yaml.safe_dump(content_yaml, allow_unicode=True),
        encoding="utf-8",
    )
    return {"dump": dump_path, "content": content_path}


def run(files) -> str:
    out = StringIO()
    call_command(
        "import_legacy_requests",
        str(files["dump"]),
        date="2025-06-01",
        content=str(files["content"]),
        stdout=out,
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


def test_row_with_wrong_field_count(files):
    """Test that malformed rows with wrong field count raise CommandError with line number."""
    dump = "\n".join(
        [
            "SET statement_timeout = 0;",
            "COPY public.request (id, customer_name, customer_phone, product_list) FROM stdin;",
            "1\tИван\t8 777 305 42 43",  # Missing product_list field (line 3 in dump)
            "\\.",
            "",
        ]
    )
    files["dump"].write_text(dump, encoding="utf-8")
    with pytest.raises(CommandError, match="Строка.*3.*ожидалось.*4.*найдено.*3"):
        run(files)
    assert QuoteRequest.objects.count() == 0


def test_reports_broken_product_list_bad_item_and_unnormalized_phone(tmp_path):
    """One row has invalid JSON in product_list, one has an item entry with a bad id, one has an
    unnormalizable phone; the summary must count all three explicitly instead of dropping them
    silently."""
    rows = [
        # broken product_list (not valid JSON)
        ["1", "Один", "8 777 305 42 43", "{not valid json"],
        # one good item + one bad item entry (missing/invalid id)
        [
            "2",
            "Два",
            "8 777 305 42 44",
            json.dumps(
                [{"id": 10, "name": "Трубогиб"}, {"id": "не число", "name": "Плохой"}],
                ensure_ascii=False,
            ),
        ],
        # unnormalizable phone
        ["3", "Три", "не телефон", "[]"],
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
    content_yaml = {"categories": [], "products": [{"slug": "tpg-2b", "legacy_ids": [10]}]}
    content_path.write_text(yaml.safe_dump(content_yaml, allow_unicode=True), encoding="utf-8")
    make_product(slug="tpg-2b")

    output = run({"dump": dump_path, "content": content_path})

    assert "Импортировано: 3" in output
    assert "Не разобран product_list (JSON невалиден): 1" in output
    assert "Пропущено позиций (некорректная форма/id): 1" in output
    assert "Телефонов не нормализовано (сохранены как есть): 1" in output
    assert QuoteRequest.objects.get(admin_note__startswith="legacy:3 ").phone == "не телефон"


def test_missing_id_column(files):
    """Test that missing id column raises CommandError naming the column."""
    dump = "\n".join(
        [
            "SET statement_timeout = 0;",
            "COPY public.request (customer_name, customer_phone, product_list) FROM stdin;",
            "Иван\t8 777 305 42 43\t[]",
            "\\.",
            "",
        ]
    )
    files["dump"].write_text(dump, encoding="utf-8")
    with pytest.raises(CommandError, match="id"):
        run(files)
    assert QuoteRequest.objects.count() == 0
