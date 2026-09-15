import pytest
from django.conf import settings

from tests.factories import make_category, make_product

pytestmark = pytest.mark.django_db


def test_sitemap_contains_only_public_pages(client):
    active = make_category(slug="pipe-benders")
    hidden = make_category(slug="hidden", is_active=False)
    make_category(slug="empty")
    make_product(category=active, slug="tpg-2b")
    make_product(category=active, slug="old-model", is_active=False)
    make_product(category=hidden, slug="in-hidden")

    response = client.get("/sitemap.xml")
    body = response.content.decode()

    assert response.status_code == 200
    assert "/catalog/pipe-benders/</loc>" in body
    assert "/catalog/pipe-benders/tpg-2b/</loc>" in body
    assert "/contacts/</loc>" in body
    assert "<lastmod>" in body
    assert "old-model" not in body
    assert "hidden" not in body
    assert "/catalog/empty/" not in body


def test_robots_txt(client):
    response = client.get("/robots.txt")
    body = response.content.decode()
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    assert "User-agent: *" in body
    assert "Disallow: /quote/" in body
    assert "Sitemap: http://localhost:8000/sitemap.xml" in body
    assert settings.ADMIN_URL not in body
