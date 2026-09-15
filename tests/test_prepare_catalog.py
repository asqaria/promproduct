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
        (
            "Шиногибы гидравлические ШГГ\nдля гибки токоведущих шин",
            "Шиногибы гидравлические ШГГ для гибки токоведущих шин",
        ),
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
