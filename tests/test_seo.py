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
    category = make_category(
        name="Трубогибы", seo_text="<p>Гибка труб любых диаметров.</p>"
    )
    expected_title = "Трубогибы купить в Астане — Батыс Курылыс XXI"
    assert seo.category_title(category, "Батыс Курылыс XXI") == expected_title
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
    product = make_product(
        name="Трубогиб ТПГ-2Б", short_description="Для труб до 2 дюймов."
    )
    expected_title = "Трубогиб ТПГ-2Б купить в Астане — Батыс Курылыс XXI"
    assert seo.product_title(product, "Батыс Курылыс XXI") == expected_title
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
    data = {"name": "</script><b>"}
    html = Template("{% load seo_tags %}{% ld_json data %}").render(
        Context({"data": data})
    )
    assert html.startswith('<script type="application/ld+json">')
    assert "</script><b>" not in html
    payload = html.removeprefix('<script type="application/ld+json">').removesuffix(
        "</script>"
    )
    assert json.loads(payload) == {"name": "</script><b>"}
