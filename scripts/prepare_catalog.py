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
    (
        "Съемники подшипников гидравлические",
        "hydraulic-bearing-pullers",
        "Съёмники подшипников гидравлические",
    ),
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
    n_categories = len(draft["categories"])
    n_products = len(draft["products"])
    print(f"Категорий: {n_categories}, товаров: {n_products}, ошибок фото: {len(report)}")


if __name__ == "__main__":
    main()
