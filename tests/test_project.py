from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command

from orders.views import client_ip


def test_system_check_passes():
    call_command("check")


def test_axes_uses_shared_client_ip_callable():
    assert settings.AXES_CLIENT_IP_CALLABLE == "orders.views.client_ip"
    # django-axes itself injects AXES_IPWARE_* defaults onto django.conf.settings at import time
    # (axes/conf.py: settings.AXES_IPWARE_META_PRECEDENCE_ORDER = getattr(...)), so those names are
    # always present on the live settings object once axes is installed - that can't be asserted
    # away. What we control is our own settings module: it must not declare AXES_IPWARE_* itself
    # (that setting was dead once AXES_CLIENT_IP_CALLABLE takes precedence, and it contradicted
    # orders.views.client_ip's own X-Forwarded-For handling).
    our_settings_source = (Path(__file__).resolve().parent.parent / "config" / "settings.py").read_text(
        encoding="utf-8"
    )
    assert "AXES_IPWARE" not in our_settings_source


def test_client_ip_uses_last_forwarded_for_entry(rf):
    request = rf.get("/", HTTP_X_FORWARDED_FOR="203.0.113.1, 10.0.0.1, 127.0.0.1")
    assert client_ip(request) == "127.0.0.1"


def test_admin_url_is_not_default():
    assert settings.ADMIN_URL != "admin/"
    assert settings.ADMIN_URL.endswith("/")


@pytest.mark.django_db
def test_default_admin_path_is_404(client):
    assert client.get("/admin/").status_code == 404


def test_site_language_is_russian():
    assert settings.LANGUAGE_CODE == "ru"
