import logging

import pytest
from django.core import mail

from catalog.models import SiteSettings
from orders import notifications
from orders.models import QuoteRequest
from orders.services import create_quote
from tests.factories import make_category, make_product

pytestmark = pytest.mark.django_db


@pytest.fixture
def recipient():
    site = SiteSettings.load()
    site.notification_email = "sales@example.com"
    site.save()
    return site.notification_email


@pytest.fixture
def products():
    category = make_category(slug="jacks")
    return (
        make_product(category=category, name="Домкрат ДА5", slug="da-5"),
        make_product(category=category, name="Домкрат ДГ", slug="dg"),
    )


def test_create_quote_saves_items_and_sends_email(
    recipient, products, django_capture_on_commit_callbacks, settings
):
    first, second = products
    with django_capture_on_commit_callbacks(execute=True):
        quote = create_quote("Иван", "+77773054243", [(first, 2), (second, 1)], "203.0.113.5")

    quote.refresh_from_db()
    assert quote.status == QuoteRequest.Status.NEW
    assert quote.source_ip == "203.0.113.5"
    assert quote.email_sent is True
    items_list = [(i.product_name, i.quantity) for i in quote.items.all()]
    assert items_list == [("Домкрат ДА5", 2), ("Домкрат ДГ", 1)]

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["sales@example.com"]
    assert message.subject == f"Заявка №{quote.pk} — Иван"
    assert "+77773054243" in message.body
    assert "Домкрат ДА5 — 2 шт. http://localhost:8000/catalog/jacks/da-5/" in message.body
    assert f"http://localhost:8000/{settings.ADMIN_URL}orders/quoterequest/{quote.pk}/change/" in message.body


def test_email_not_sent_before_commit(recipient, products, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        create_quote("Иван", "+77773054243", [(products[0], 1)], None)
    assert len(callbacks) == 1
    assert mail.outbox == []


def test_fallback_to_admin_email_setting(settings, products, django_capture_on_commit_callbacks):
    settings.ADMIN_EMAIL = "fallback@example.com"
    with django_capture_on_commit_callbacks(execute=True):
        create_quote("Иван", "+77773054243", [(products[0], 1)], None)
    assert mail.outbox[0].to == ["fallback@example.com"]


def test_no_recipient_logs_error_and_keeps_request(
    settings, products, caplog, django_capture_on_commit_callbacks
):
    settings.ADMIN_EMAIL = ""
    with caplog.at_level(logging.ERROR, logger="orders.notifications"):
        with django_capture_on_commit_callbacks(execute=True):
            quote = create_quote("Иван", "+77773054243", [(products[0], 1)], None)
    quote.refresh_from_db()
    assert quote.email_sent is False
    assert mail.outbox == []
    assert "no notification recipient" in caplog.text


def test_smtp_failure_keeps_request_unsent(
    recipient, products, monkeypatch, caplog, django_capture_on_commit_callbacks
):
    def broken_send_mail(**kwargs):
        raise OSError("SMTP down")

    monkeypatch.setattr(notifications, "send_mail", broken_send_mail)
    with caplog.at_level(logging.ERROR, logger="orders.notifications"):
        with django_capture_on_commit_callbacks(execute=True):
            quote = create_quote("Иван", "+77773054243", [(products[0], 1)], None)
    quote.refresh_from_db()
    assert QuoteRequest.objects.filter(pk=quote.pk).exists()
    assert quote.email_sent is False
    assert "failed to send notification" in caplog.text


def test_deleted_product_still_listed_by_snapshot_name(
    recipient, products, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=False):
        quote = create_quote("Иван", "+77773054243", [(products[0], 4)], None)
    products[0].delete()
    assert notifications.send_quote_notification(quote.pk) is True
    assert "Домкрат ДА5 — 4 шт." in mail.outbox[0].body
