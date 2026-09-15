import json

import pytest
from bs4 import BeautifulSoup
from django.core import mail

from orders.models import QuoteRequest
from tests.factories import make_product

pytestmark = pytest.mark.django_db


@pytest.fixture
def product():
    return make_product(name="Трубогиб ТПГ-2Б")


def payload(product, **overrides) -> dict:
    data = {
        "name": "Иван",
        "phone": "8 777 305 42 43",
        "items": json.dumps([{"id": product.pk, "qty": 2}]),
        "website": "",
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize("url", ["/", "/quote/", "/contacts/"])
def test_side_panel_form_on_every_page(client, url):
    page = BeautifulSoup(client.get(url).content, "html.parser")
    form = page.select_one("#quote-panel form[data-quote-form]")
    assert form["method"] == "post"
    assert form["action"] == "/quote/"
    assert form.select_one("input[name='csrfmiddlewaretoken']") is not None
    assert form.select_one("input[type='hidden'][name='items']") is not None
    assert form.select_one("input[name='name']") is not None
    assert form.select_one("input[name='phone']")["type"] == "tel"
    assert form.select_one("[data-quote-submit]") is not None
    honeypot = form.select_one(".form__hp")
    assert honeypot["aria-hidden"] == "true"
    assert honeypot.select_one("input[name='website']")["tabindex"] == "-1"


def test_quote_page_is_noindex(client):
    page = BeautifulSoup(client.get("/quote/").content, "html.parser")
    assert page.find("meta", attrs={"name": "robots"})["content"] == "noindex, follow"
    assert page.select_one("main h1").get_text() == "Запрос коммерческого предложения"


def test_valid_submission_creates_request_and_redirects(
    client, product, django_capture_on_commit_callbacks, settings
):
    settings.ADMIN_EMAIL = "sales@example.com"
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post("/quote/", payload(product))
    quote = QuoteRequest.objects.get()
    assert response.status_code == 302
    assert response["Location"] == f"/quote/thanks/?id={quote.pk}"
    assert quote.phone == "+77773054243"
    assert quote.source_ip == "127.0.0.1"
    assert [(i.product_name, i.quantity) for i in quote.items.all()] == [("Трубогиб ТПГ-2Б", 2)]
    assert len(mail.outbox) == 1


def test_forwarded_ip_is_stored(client, product):
    client.post("/quote/", payload(product), HTTP_X_FORWARDED_FOR="203.0.113.7")
    assert QuoteRequest.objects.get().source_ip == "203.0.113.7"


def test_garbage_forwarded_ip_is_ignored(client, product):
    client.post("/quote/", payload(product), HTTP_X_FORWARDED_FOR="not-an-ip")
    assert QuoteRequest.objects.get().source_ip is None


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"phone": "12345"}, "Укажите телефон в формате +7 XXX XXX XX XX."),
        ({"name": "И"}, "Имя слишком короткое."),
        ({"name": "Иван\nBcc: x@example.com"}, "Имя содержит недопустимые символы."),
        ({"items": ""}, "Добавьте товары в запрос."),
        ({"items": json.dumps([{"id": 999999, "qty": 1}])}, "Корзина пуста или товары недоступны."),
    ],
)
def test_invalid_submission_shows_error_in_side_panel(client, product, overrides, error):
    response = client.post("/quote/", payload(product, **overrides))
    page = BeautifulSoup(response.content, "html.parser")
    assert response.status_code == 200
    assert error in page.select_one("#quote-panel form[data-quote-form]").get_text()
    assert "Заявка не отправлена" in page.select_one("main").get_text()
    assert QuoteRequest.objects.count() == 0


def test_invalid_submission_keeps_entered_values(client, product):
    response = client.post("/quote/", payload(product, phone="12345"))
    form = BeautifulSoup(response.content, "html.parser").select_one("#quote-panel form[data-quote-form]")
    assert form.select_one("input[name='name']")["value"] == "Иван"
    assert form.select_one("input[name='phone']")["value"] == "12345"


def test_honeypot_pretends_success_without_saving(client, product):
    response = client.post("/quote/", payload(product, website="https://spam.example"))
    assert response.status_code == 302
    assert response["Location"] == "/quote/thanks/"
    assert QuoteRequest.objects.count() == 0
    assert mail.outbox == []


def test_sixth_submission_within_hour_is_rejected(client, product):
    for _ in range(5):
        assert client.post("/quote/", payload(product)).status_code == 302
    response = client.post("/quote/", payload(product))
    assert response.status_code == 200
    assert "Слишком много заявок" in response.content.decode()
    assert QuoteRequest.objects.count() == 5


def test_rate_limit_is_per_ip(client, product):
    for _ in range(5):
        client.post("/quote/", payload(product), HTTP_X_FORWARDED_FOR="203.0.113.1")
    response = client.post("/quote/", payload(product), HTTP_X_FORWARDED_FOR="203.0.113.2")
    assert response.status_code == 302


def test_thanks_page(client):
    response = client.get("/quote/thanks/?id=42")
    page = BeautifulSoup(response.content, "html.parser")
    assert response.status_code == 200
    assert "№42" in page.select_one("main").get_text()
    assert page.select_one("[data-cart-clear]") is not None
    assert page.find("meta", attrs={"name": "robots"})["content"] == "noindex, follow"
    other = BeautifulSoup(client.get("/quote/thanks/?id=abc").content, "html.parser")
    assert "№" not in other.select_one("main").get_text()
