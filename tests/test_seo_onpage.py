"""Проверки SEO-разметки, общей для всех страниц сайта."""

import json

import pytest
from bs4 import BeautifulSoup

from catalog.models import SiteSettings
from tests.factories import make_category, make_product

pytestmark = pytest.mark.django_db


def soup(response) -> BeautifulSoup:
    return BeautifulSoup(response.content, "html.parser")


def ld_objects(response) -> list[dict]:
    return [json.loads(tag.string) for tag in soup(response).find_all("script", type="application/ld+json")]


def ld_of_type(response, type_name: str) -> list[dict]:
    return [data for data in ld_objects(response) if data.get("@type") == type_name]


@pytest.fixture
def catalog():
    category = make_category(slug="pipe-benders", name="Трубогибы")
    make_product(category=category, slug="tpg-2b", name="Трубогиб ТПГ-2Б")
    return category


PUBLIC_PATHS = ["/", "/catalog/", "/catalog/pipe-benders/", "/catalog/pipe-benders/tpg-2b/", "/contacts/"]


@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_footer_links_to_catalog_contacts_and_categories(client, catalog, path):
    links = {a["href"] for a in soup(client.get(path)).find("footer").find_all("a", href=True)}
    assert {"/", "/catalog/", "/contacts/", "/catalog/pipe-benders/"} <= links


@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_local_business_ld_present_once_on_every_page(client, catalog, path):
    assert len(ld_of_type(client.get(path), "LocalBusiness")) == 1


@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_head_has_favicon_og_locale_and_canonical(client, catalog, path):
    head = soup(client.get(path)).head
    assert head.find("link", rel=["icon"])["href"].endswith(".svg")
    assert head.find("meta", property="og:locale")["content"] == "ru_RU"
    assert head.find("link", rel=["canonical"])["href"] == f"http://localhost:8000{path}"


def test_category_page_lists_products_in_item_list_ld(client, catalog):
    item_list = ld_of_type(client.get("/catalog/pipe-benders/"), "ItemList")[0]
    assert item_list["name"] == "Трубогибы"
    assert item_list["numberOfItems"] == 1
    assert item_list["itemListElement"][0] == {
        "@type": "ListItem",
        "position": 1,
        "name": "Трубогиб ТПГ-2Б",
        "url": "http://localhost:8000/catalog/pipe-benders/tpg-2b/",
    }


def test_catalog_index_has_item_list_of_categories_and_intro_text(client, catalog):
    response = client.get("/catalog/")
    item_list = ld_of_type(response, "ItemList")[0]
    assert item_list["itemListElement"][0]["url"] == "http://localhost:8000/catalog/pipe-benders/"
    intro = soup(response).find("section", class_="prose")
    assert intro is not None
    assert len(intro.get_text(" ", strip=True)) > 400


def test_contacts_page_has_descriptive_text(client):
    intro = soup(client.get("/contacts/")).find("section", class_="prose")
    assert intro is not None
    assert len(intro.get_text(" ", strip=True)) > 400


def test_verification_meta_rendered_from_site_settings(client):
    site = SiteSettings.load()
    site.google_verification = "google-token"
    site.yandex_verification = "yandex-token"
    site.save()
    head = soup(client.get("/")).head
    assert head.find("meta", attrs={"name": "google-site-verification"})["content"] == "google-token"
    assert head.find("meta", attrs={"name": "yandex-verification"})["content"] == "yandex-token"


def test_verification_meta_omitted_when_not_configured(client):
    site = SiteSettings.load()
    site.google_verification = ""
    site.yandex_verification = ""
    site.save()
    head = soup(client.get("/")).head
    assert head.find("meta", attrs={"name": "google-site-verification"}) is None
    assert head.find("meta", attrs={"name": "yandex-verification"}) is None


def test_quote_pages_are_crawlable_but_noindex(client):
    """Закрытый в robots.txt путь не даёт роботу прочитать noindex, поэтому он открыт."""
    robots = client.get("/robots.txt").content.decode()
    assert "Disallow: /quote/" not in robots
    head = soup(client.get("/quote/")).head
    assert head.find("meta", attrs={"name": "robots"})["content"] == "noindex, follow"


def test_sitemap_static_pages_carry_lastmod_and_home_has_top_priority(client, catalog):
    body = client.get("/sitemap.xml").content.decode()
    home = body.split("<url>")[1]
    assert "<loc>http://testserver/</loc>" in home
    assert "<lastmod>" in home
    assert "<priority>1.0</priority>" in home


def test_sitemap_renders_without_products(client):
    """lastmod статических страниц вычисляется из каталога — пустой каталог не должен ломать выдачу."""
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert "<loc>http://testserver/</loc>" in response.content.decode()
