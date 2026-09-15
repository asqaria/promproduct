import json
from decimal import Decimal
from io import BytesIO

import pytest
from bs4 import BeautifulSoup
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from catalog.models import Category, Product, ProductImage, ProductSpec
from tests.factories import make_category, make_product

pytestmark = pytest.mark.django_db


def soup(response) -> BeautifulSoup:
    return BeautifulSoup(response.content, "html.parser")


def ld_objects(response) -> list[dict]:
    return [json.loads(tag.string) for tag in soup(response).find_all("script", type="application/ld+json")]


def png_upload(width: int = 100, height: int = 100) -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new("RGB", (width, height), "orange").save(buffer, "PNG")
    return SimpleUploadedFile("photo.png", buffer.getvalue(), content_type="image/png")


@pytest.fixture
def catalog_data():
    pipe = make_category(name="Трубогибы", slug="pipe-benders", seo_text="<p>Гибка труб.</p>", sort_order=10)
    make_category(name="Пустая", slug="empty", sort_order=20)
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


@pytest.mark.parametrize(
    "url", ["/", "/catalog/", "/catalog/pipe-benders/", "/catalog/pipe-benders/tpg-2b/", "/contacts/"]
)
def test_every_page_has_three_column_shell(client, catalog_data, url):
    page = soup(client.get(url))
    assert page.select_one("aside.sidebar#catalog-menu nav.category-nav") is not None
    assert page.select_one("main.content#main") is not None
    assert page.select_one("aside.side-panel#quote-panel [data-quote-list]") is not None
    assert page.select_one("[data-drawer-toggle][aria-controls='catalog-menu']") is not None
    assert page.select_one("[data-drawer-backdrop]").has_attr("hidden")
    assert page.select_one("a.cart-link[href='#quote-panel'] [data-cart-count]") is not None
    assert "wa.me/77773054243" in page.select_one(".contacts-panel").decode()


def test_sidebar_lists_categories_and_marks_current(client, catalog_data):
    home = soup(client.get("/"))
    assert home.select_one(".category-nav a[aria-current='page']").get_text() == "Все товары"
    names = [a.get_text() for a in home.select(".category-nav a")]
    assert names[0] == "Все товары"
    assert "Трубогибы" in names

    category_page = soup(client.get("/catalog/pipe-benders/"))
    assert category_page.select_one(".category-nav a[aria-current='page']").get_text() == "Трубогибы"

    product_page = soup(client.get("/catalog/pipe-benders/tpg-2b/"))
    assert product_page.select_one(".category-nav a[aria-current='page']").get_text() == "Трубогибы"


def test_home_groups_products_by_category_in_sort_order(client, catalog_data):
    jacks = make_category(name="Домкраты", slug="jacks", sort_order=5)
    make_product(category=jacks, name="Домкрат ДА5", slug="da-5")
    make_product(category=catalog_data["category"], name="Трубогиб ТПГ-1Б", slug="tpg-1b", is_active=False)

    response = client.get("/")
    page = soup(response)
    blocks = page.select("section.category-block")
    assert [b.select_one("h2").get_text() for b in blocks] == ["Домкраты", "Трубогибы"]
    assert [a.get_text() for a in blocks[1].select(".product-card__name")] == ["Трубогиб ТПГ-2Б"]
    assert blocks[1].select_one(".section__head a")["href"] == "/catalog/pipe-benders/"
    assert any(obj["@type"] == "LocalBusiness" for obj in ld_objects(response))


def test_home_loads_only_first_category_block_images_eagerly(client, catalog_data):
    jacks = make_category(name="Домкраты", slug="jacks", sort_order=5)
    first_product = make_product(category=jacks, name="Домкрат ДА5", slug="da-5")
    ProductImage.objects.create(product=first_product, image=png_upload())
    ProductImage.objects.create(product=catalog_data["product"], image=png_upload())

    page = soup(client.get("/"))
    blocks = page.select("section.category-block")
    assert [b.select_one("h2").get_text() for b in blocks] == ["Домкраты", "Трубогибы"]
    assert blocks[0].select_one(".product-card__image img").has_attr("loading") is False
    assert blocks[1].select_one(".product-card__image img")["loading"] == "lazy"


def test_product_card_hooks(client, catalog_data):
    page = soup(client.get("/catalog/pipe-benders/"))
    card = page.select_one(".product-grid [data-product]")
    assert card["data-id"] == str(catalog_data["product"].pk)
    assert card["data-name"] == "Трубогиб ТПГ-2Б"
    assert card["data-url"] == "/catalog/pipe-benders/tpg-2b/"
    assert card.select_one("button.product-card__add[data-add-to-quote]").get_text(strip=True) == "В запрос"
    assert card.select_one("a.product-card__name")["href"] == "/catalog/pipe-benders/tpg-2b/"


def test_catalog_index(client, catalog_data):
    response = client.get("/catalog/")
    page = soup(response)
    assert response.status_code == 200
    assert page.select_one("main h1").get_text() == "Каталог"
    assert [el.get_text() for el in page.select(".category-card__name")] == ["Трубогибы"]


def test_category_page_seo(client, catalog_data):
    response = client.get("/catalog/pipe-benders/")
    page = soup(response)
    assert response.status_code == 200
    assert page.select_one("main h1").get_text() == "Трубогибы"
    assert page.title.get_text() == "Трубогибы купить в Астане — Батыс Курылыс XXI"
    assert page.find("meta", attrs={"name": "description"})["content"] == "Гибка труб."
    assert page.find("link", rel="canonical")["href"] == "http://localhost:8000/catalog/pipe-benders/"
    assert "Трубогиб ТПГ-2Б" in page.select_one(".product-grid").get_text()
    assert any(obj["@type"] == "BreadcrumbList" for obj in ld_objects(response))


def test_product_page_content_and_seo(client, catalog_data):
    response = client.get("/catalog/pipe-benders/tpg-2b/")
    page = soup(response)
    assert response.status_code == 200
    assert page.select_one("main h1").get_text() == "Трубогиб ТПГ-2Б"
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
    page = soup(client.get("/catalog/pipe-benders/tpg-2b/"))
    actions = page.select_one(".product__actions[data-product]")
    assert actions["data-id"] == str(catalog_data["product"].pk)
    assert actions["data-name"] == "Трубогиб ТПГ-2Б"
    assert actions["data-url"] == "/catalog/pipe-benders/tpg-2b/"
    assert actions.select_one("[data-add-to-quote]") is not None
    assert actions.select_one("input[data-qty]")["max"] == "999"
    whatsapp = actions.select_one("a.btn--whatsapp")["href"]
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


def test_inactive_product_is_404(client, catalog_data):
    Product.objects.filter(pk=catalog_data["product"].pk).update(is_active=False)
    response = client.get("/catalog/pipe-benders/tpg-2b/")
    assert response.status_code == 404
    assert "Страница не найдена" in response.content.decode()


def test_inactive_category_hides_category_and_its_products(client, catalog_data):
    Category.objects.filter(pk=catalog_data["category"].pk).update(is_active=False)
    assert client.get("/catalog/pipe-benders/").status_code == 404
    assert client.get("/catalog/pipe-benders/tpg-2b/").status_code == 404


def test_contacts_page(client, catalog_data):
    response = client.get("/contacts/")
    page = soup(response)
    assert response.status_code == 200
    assert "Керей Жанибек хандар" in page.select_one("main").get_text()
    assert "wa.me/77773773763" in page.select_one("main").decode()
