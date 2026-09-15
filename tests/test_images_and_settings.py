from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from PIL import Image

from catalog.context_processors import site
from catalog.models import ProductImage, SiteSettings
from tests.factories import make_category, make_product

pytestmark = pytest.mark.django_db


def png_upload(width: int = 3000, height: int = 1000, mode: str = "RGB") -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new(mode, (width, height), "orange").save(buffer, "PNG")
    return SimpleUploadedFile("photo.png", buffer.getvalue(), content_type="image/png")


def test_uploaded_image_converted_to_webp_with_thumbnail():
    product = make_product(slug="tpg-2b")
    image = ProductImage.objects.create(product=product, image=png_upload())
    assert image.image.name.startswith("products/tpg-2b/")
    assert image.image.name.endswith(".webp")
    with Image.open(image.image.path) as full:
        assert full.format == "WEBP"
        assert full.size == (1600, 533)
    with Image.open(image.thumbnail.path) as thumb:
        assert thumb.format == "WEBP"
        assert thumb.size == (400, 133)


def test_small_image_not_upscaled_and_transparency_supported():
    product = make_product()
    image = ProductImage.objects.create(product=product, image=png_upload(300, 200, "RGBA"))
    with Image.open(image.image.path) as full:
        assert full.size == (300, 200)


def test_alt_defaults_to_product_name():
    product = make_product(name="Домкрат ДА5")
    image = ProductImage.objects.create(product=product, image=png_upload(100, 100))
    assert image.alt == "Домкрат ДА5"


def test_main_image_is_first_by_sort_order():
    product = make_product()
    second = ProductImage.objects.create(product=product, image=png_upload(100, 100), sort_order=2)
    first = ProductImage.objects.create(product=product, image=png_upload(100, 100), sort_order=1)
    assert product.main_image == first
    assert second != first


def test_main_image_none_without_images():
    assert make_product().main_image is None


def test_deleting_image_removes_files():
    product = make_product()
    image = ProductImage.objects.create(product=product, image=png_upload(100, 100))
    full_path, thumb_path = image.image.path, image.thumbnail.path
    ProductImage.objects.filter(pk=image.pk).delete()
    import os

    assert not os.path.exists(full_path)
    assert not os.path.exists(thumb_path)


def test_site_settings_singleton_with_defaults():
    settings_obj = SiteSettings.load()
    assert settings_obj.pk == 1
    assert settings_obj.company_name == "Батыс Курылыс XXI"
    assert "Астана" in settings_obj.address
    SiteSettings(company_name="Другое").save()
    assert SiteSettings.objects.count() == 1


def test_whatsapp_and_phone_lists():
    settings_obj = SiteSettings.load()
    settings_obj.phones = "+7 (7172) 00-00-00\n\n"
    settings_obj.save()
    assert settings_obj.phone_list == ["+7 (7172) 00-00-00"]
    assert settings_obj.whatsapp_list == [
        {"display": "+7 777 305 4243", "wa": "77773054243"},
        {"display": "+7 777 377 3763", "wa": "77773773763"},
    ]


def test_context_processor():
    make_category(name="Активная", is_active=True)
    make_category(name="Скрытая", is_active=False)
    context = site(RequestFactory().get("/"))
    assert context["site"].company_name == "Батыс Курылыс XXI"
    assert context["site_url"] == "http://localhost:8000"
    assert [c.name for c in context["nav_categories"]] == ["Активная"]
