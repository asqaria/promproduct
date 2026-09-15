import pytest
from django.conf import settings
from django.contrib.auth.models import Group

from catalog.models import SiteSettings
from catalog.roles import MANAGER_GROUP
from tests.factories import make_product

pytestmark = pytest.mark.django_db

ADMIN = f"/{settings.ADMIN_URL}"


@pytest.mark.parametrize("model", ["category", "product", "redirect", "sitesettings"])
def test_changelists_open(client, superuser, model):
    make_product()
    client.force_login(superuser)
    assert client.get(f"{ADMIN}catalog/{model}/").status_code == 200


def test_product_add_and_change_pages_open(client, superuser):
    product = make_product()
    client.force_login(superuser)
    assert client.get(f"{ADMIN}catalog/product/add/").status_code == 200
    assert client.get(f"{ADMIN}catalog/product/{product.pk}/change/").status_code == 200


def test_site_settings_cannot_be_added_twice_or_deleted(client, superuser):
    SiteSettings.load()
    client.force_login(superuser)
    assert client.get(f"{ADMIN}catalog/sitesettings/add/").status_code == 403
    assert client.get(f"{ADMIN}catalog/sitesettings/1/delete/").status_code == 403


def test_login_locked_after_five_failures(client, superuser):
    url = f"{ADMIN}login/"
    for _ in range(5):
        client.post(url, {"username": "root", "password": "wrong"})
    response = client.post(url, {"username": "root", "password": "very-strong-pass-123"})
    assert response.status_code == 429


def test_manager_group_has_catalog_permissions():
    group = Group.objects.get(name=MANAGER_GROUP)
    codenames = set(group.permissions.values_list("codename", flat=True))
    expected = {"change_product", "add_product", "change_category", "view_sitesettings", "change_redirect"}
    assert expected <= codenames
    assert "change_user" not in codenames
