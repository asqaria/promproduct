import pytest
from django.conf import settings

from orders.models import QuoteItem, QuoteRequest
from tests.factories import make_product

pytestmark = pytest.mark.django_db

URL = f"/{settings.ADMIN_URL}orders/quoterequest/"


@pytest.fixture
def quote():
    product = make_product(name="Домкрат ДА5")
    request = QuoteRequest.objects.create(name="Иван", phone="+77773054243")
    QuoteItem.objects.create(request=request, product=product, product_name=product.name, quantity=3)
    return request


def test_changelist_shows_request(client, superuser, quote):
    client.force_login(superuser)
    response = client.get(URL)
    body = response.content.decode()
    assert response.status_code == 200
    assert "Иван" in body
    assert 'href="tel:+77773054243"' in body


def test_change_page_shows_items_read_only(client, superuser, quote):
    client.force_login(superuser)
    response = client.get(f"{URL}{quote.pk}/change/")
    body = response.content.decode()
    assert response.status_code == 200
    assert "Домкрат ДА5" in body
    assert 'name="items-0-quantity"' not in body


def test_requests_cannot_be_added_in_admin(client, superuser):
    client.force_login(superuser)
    assert client.get(f"{URL}add/").status_code == 403


@pytest.mark.parametrize(
    ("action", "status"),
    [("mark_in_progress", QuoteRequest.Status.IN_PROGRESS), ("mark_closed", QuoteRequest.Status.CLOSED)],
)
def test_status_actions(client, superuser, quote, action, status):
    client.force_login(superuser)
    response = client.post(URL, {"action": action, "_selected_action": [quote.pk]})
    assert response.status_code == 302
    quote.refresh_from_db()
    assert quote.status == status
