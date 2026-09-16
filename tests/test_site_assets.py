from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from catalog.models import SiteSettings

pytestmark = pytest.mark.django_db


def png_upload(name: str = "logo.png", width: int = 200, height: int = 60) -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new("RGB", (width, height), "orange").save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def xlsx_upload(name: str = "pricelist.xlsx", content: bytes = b"fake-xlsx-bytes") -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name, content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def pdf_upload(name: str = "pricelist.pdf", content: bytes = b"%PDF-1.4 fake") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type="application/pdf")


def test_price_list_rejects_pdf_extension():
    settings_obj = SiteSettings.load()
    settings_obj.price_list = pdf_upload()
    with pytest.raises(ValidationError):
        settings_obj.full_clean()


def test_price_list_accepts_xlsx_extension():
    settings_obj = SiteSettings.load()
    settings_obj.price_list = xlsx_upload()
    settings_obj.full_clean()  # should not raise


def test_price_list_updated_set_on_first_upload():
    settings_obj = SiteSettings.load()
    assert settings_obj.price_list_updated is None
    settings_obj.price_list = xlsx_upload()
    settings_obj.save()
    settings_obj.refresh_from_db()
    assert settings_obj.price_list_updated == timezone.localdate()


def test_price_list_updated_unchanged_when_file_untouched():
    settings_obj = SiteSettings.load()
    settings_obj.price_list = xlsx_upload()
    settings_obj.save()
    settings_obj.refresh_from_db()
    first_date = settings_obj.price_list_updated

    settings_obj.company_name = "Другое название"
    settings_obj.save()
    settings_obj.refresh_from_db()
    assert settings_obj.price_list_updated == first_date


def test_price_list_updated_changes_when_new_file_uploaded():
    settings_obj = SiteSettings.load()
    settings_obj.price_list = xlsx_upload("first.xlsx", b"one")
    settings_obj.save()
    settings_obj.refresh_from_db()
    first_date = settings_obj.price_list_updated
    assert first_date is not None

    settings_obj.price_list = xlsx_upload("second.xlsx", b"two")
    settings_obj.save()
    settings_obj.refresh_from_db()
    assert settings_obj.price_list_updated == timezone.localdate()
    assert settings_obj.price_list.name.endswith("second.xlsx") or "second" in settings_obj.price_list.name


def test_price_list_updated_cleared_when_file_removed():
    settings_obj = SiteSettings.load()
    settings_obj.price_list = xlsx_upload()
    settings_obj.save()
    settings_obj.refresh_from_db()
    assert settings_obj.price_list_updated is not None

    settings_obj.price_list = None
    settings_obj.save()
    settings_obj.refresh_from_db()
    assert settings_obj.price_list_updated is None


def test_header_shows_logo_image_when_set(client):
    settings_obj = SiteSettings.load()
    settings_obj.logo = png_upload()
    settings_obj.save()

    response = client.get("/")
    html = response.content.decode()
    assert 'class="logo__img"' in html
    assert f'alt="{settings_obj.company_name}"' in html


def test_header_shows_plain_text_when_no_logo(client):
    settings_obj = SiteSettings.load()
    assert not settings_obj.logo

    response = client.get("/")
    html = response.content.decode()
    assert 'class="logo__img"' not in html
    assert settings_obj.company_name in html


def test_pricelist_panel_absent_without_file(client):
    settings_obj = SiteSettings.load()
    assert not settings_obj.price_list

    response = client.get("/")
    html = response.content.decode()
    assert "pricelist-panel" not in html


def test_pricelist_panel_present_with_file(client):
    settings_obj = SiteSettings.load()
    settings_obj.price_list = xlsx_upload()
    settings_obj.save()
    settings_obj.refresh_from_db()

    response = client.get("/")
    html = response.content.decode()
    assert "pricelist-panel" in html
    assert settings_obj.price_list.url in html
    assert "download" in html


def test_admin_change_form_includes_new_fields(client, superuser):
    settings_obj = SiteSettings.load()
    client.force_login(superuser)

    url = reverse("admin:catalog_sitesettings_change", args=[settings_obj.pk])
    response = client.get(url)
    assert response.status_code == 200
    html = response.content.decode()
    assert 'name="logo"' in html
    assert 'name="price_list"' in html
