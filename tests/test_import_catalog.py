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
            {
                "slug": "tpg-2b",
                "legacy_ids": [10],
                "category": "pipe-benders",
                "name": "Трубогиб ТПГ-2Б",
                "model_code": "ТПГ-2Б",
                "sort_order": 10,
                "is_active": True,
                "needs_review": True,
                "short_description": "Кратко",
                "description": "<p>Описание</p>",
                "meta_title": "",
                "meta_description": "Описание",
                "specs": [["Масса, кг", "54"], ["Ход штока, мм", "180"]],
                "images": [
                    {"file": "tpg-2b/1.webp", "alt": "Трубогиб"},
                    {"file": "tpg-2b/missing.webp", "alt": "X"},
                ],
            },
        ],
    }
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return {"path": path, "images_dir": images_dir, "data": data}


def run(content) -> str:
    out = StringIO()
    call_command(
        "import_catalog",
        content=str(content["path"]),
        images_dir=str(content["images_dir"]),
        stdout=out,
    )
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
