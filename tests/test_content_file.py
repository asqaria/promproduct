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
