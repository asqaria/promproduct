from decimal import Decimal

import pytest
from django.db import IntegrityError

from catalog.models import Redirect
from tests.factories import make_category, make_product

pytestmark = pytest.mark.django_db


def test_absolute_urls():
    category = make_category(slug="pipe-benders")
    product = make_product(category=category, slug="tpg-2b")
    assert category.get_absolute_url() == "/catalog/pipe-benders/"
    assert product.get_absolute_url() == "/catalog/pipe-benders/tpg-2b/"


def test_html_fields_sanitized_on_save():
    category = make_category(seo_text='<p style="x">a</p><script>x</script>')
    product = make_product(description='<p><font>b</font></p><img src="x">')
    category.refresh_from_db()
    product.refresh_from_db()
    assert category.seo_text == "<p>a</p>"
    assert product.description == "<p>b</p>"


def test_slug_is_unique():
    make_product(slug="same")
    with pytest.raises(IntegrityError):
        make_product(slug="same")


@pytest.mark.parametrize(
    ("price", "show_price", "expected"),
    [
        (Decimal("150000"), False, None),
        (Decimal("150000"), True, Decimal("150000")),
        (None, True, None),
    ],
)
def test_displayed_price(price, show_price, expected):
    product = make_product(price=price, show_price=show_price)
    assert product.displayed_price == expected


def test_changing_product_slug_creates_redirect():
    category = make_category(slug="jacks")
    product = make_product(category=category, slug="old")
    product.slug = "new"
    product.save()
    assert Redirect.objects.get(old_path="/catalog/jacks/old/").new_path == "/catalog/jacks/new/"


def test_changing_product_category_creates_redirect():
    first = make_category(slug="first")
    second = make_category(slug="second")
    product = make_product(category=first, slug="item")
    product.category = second
    product.save()
    assert Redirect.objects.get(old_path="/catalog/first/item/").new_path == "/catalog/second/item/"


def test_saving_without_slug_change_creates_no_redirect():
    product = make_product()
    product.name = "Другое название"
    product.save()
    assert Redirect.objects.count() == 0


def test_changing_category_slug_redirects_category_and_products():
    category = make_category(slug="old-cat")
    make_product(category=category, slug="p1")
    category.slug = "new-cat"
    category.save()
    assert Redirect.objects.get(old_path="/catalog/old-cat/").new_path == "/catalog/new-cat/"
    assert Redirect.objects.get(old_path="/catalog/old-cat/p1/").new_path == "/catalog/new-cat/p1/"


def test_redirect_chains_are_collapsed():
    Redirect.record("/a/", "/b/")
    Redirect.record("/b/", "/c/")
    assert Redirect.objects.get(old_path="/a/").new_path == "/c/"
    assert Redirect.objects.get(old_path="/b/").new_path == "/c/"


def test_moving_back_removes_loop():
    Redirect.record("/a/", "/b/")
    Redirect.record("/b/", "/a/")
    assert not Redirect.objects.filter(old_path="/a/").exists()
    assert Redirect.objects.get(old_path="/b/").new_path == "/a/"


def test_middleware_redirects_known_old_path(client):
    Redirect.record("/catalog/old/", "/catalog/new/")
    response = client.get("/catalog/old/")
    assert response.status_code == 301
    assert response["Location"] == "/catalog/new/"


def test_middleware_keeps_unknown_404(client):
    assert client.get("/catalog/unknown/").status_code == 404
