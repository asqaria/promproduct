import pytest
from django.conf import settings
from django.core.management import call_command


def test_system_check_passes():
    call_command("check")


def test_admin_url_is_not_default():
    assert settings.ADMIN_URL != "admin/"
    assert settings.ADMIN_URL.endswith("/")


@pytest.mark.django_db
def test_default_admin_path_is_404(client):
    assert client.get("/admin/").status_code == 404


def test_site_language_is_russian():
    assert settings.LANGUAGE_CODE == "ru"
