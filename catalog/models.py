import re
import uuid
from decimal import Decimal

from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from catalog.images import to_webp
from catalog.paths import category_path, product_path
from catalog.sanitize import sanitize_html


class Redirect(models.Model):
    old_path = models.CharField("Старый путь", max_length=300, unique=True)
    new_path = models.CharField("Новый путь", max_length=300)

    class Meta:
        verbose_name = "редирект"
        verbose_name_plural = "редиректы"
        ordering = ["old_path"]

    def __str__(self) -> str:
        return f"{self.old_path} → {self.new_path}"

    @classmethod
    def record(cls, old_path: str, new_path: str) -> None:
        if old_path == new_path:
            return
        cls.objects.filter(new_path=old_path).update(new_path=new_path)
        cls.objects.filter(old_path=new_path).delete()
        cls.objects.update_or_create(old_path=old_path, defaults={"new_path": new_path})


class Category(models.Model):
    name = models.CharField("Название", max_length=200)
    slug = models.SlugField("Slug", max_length=100, unique=True)
    seo_text = models.TextField("SEO-текст", blank=True)
    meta_title = models.CharField("Meta title", max_length=70, blank=True, help_text="До 60 символов.")
    meta_description = models.CharField(
        "Meta description", max_length=200, blank=True, help_text="До 160 символов."
    )
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "категория"
        verbose_name_plural = "категории"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        self.seo_text = sanitize_html(self.seo_text)
        old_slug = None
        if self.pk:
            old_slug = type(self).objects.filter(pk=self.pk).values_list("slug", flat=True).first()
        super().save(*args, **kwargs)
        if old_slug and old_slug != self.slug:
            Redirect.record(category_path(old_slug), category_path(self.slug))
            for product_slug in self.products.values_list("slug", flat=True):
                Redirect.record(product_path(old_slug, product_slug), product_path(self.slug, product_slug))

    def get_absolute_url(self) -> str:
        return category_path(self.slug)


class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products", verbose_name="Категория"
    )
    name = models.CharField("Название", max_length=255)
    slug = models.SlugField("Slug", max_length=100, unique=True)
    model_code = models.CharField("Модель", max_length=100, blank=True)
    short_description = models.CharField("Краткое описание", max_length=300, blank=True)
    description = models.TextField("Описание", blank=True)
    price = models.DecimalField("Цена, ₸", max_digits=12, decimal_places=0, null=True, blank=True)
    show_price = models.BooleanField("Показывать цену", default=False)
    is_active = models.BooleanField("Активен", default=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    meta_title = models.CharField("Meta title", max_length=70, blank=True, help_text="До 60 символов.")
    meta_description = models.CharField(
        "Meta description", max_length=200, blank=True, help_text="До 160 символов."
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Изменён", auto_now=True)

    class Meta:
        verbose_name = "товар"
        verbose_name_plural = "товары"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        self.description = sanitize_html(self.description)
        old_path = None
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values_list("slug", "category__slug").first()
            if old:
                old_path = product_path(old[1], old[0])
        super().save(*args, **kwargs)
        new_path = self.get_absolute_url()
        if old_path and old_path != new_path:
            Redirect.record(old_path, new_path)

    def get_absolute_url(self) -> str:
        return product_path(self.category.slug, self.slug)

    @property
    def displayed_price(self) -> Decimal | None:
        if self.show_price and self.price is not None:
            return self.price
        return None

    @property
    def main_image(self) -> "ProductImage | None":
        images = list(self.images.all())
        return images[0] if images else None


class ProductSpec(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="specs")
    name = models.CharField("Характеристика", max_length=200)
    value = models.CharField("Значение", max_length=300)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "характеристика"
        verbose_name_plural = "характеристики"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return f"{self.name}: {self.value}"


def product_image_path(instance: "ProductImage", filename: str) -> str:
    return f"products/{instance.product.slug}/{uuid.uuid4().hex}.webp"


def product_thumbnail_path(instance: "ProductImage", filename: str) -> str:
    return f"products/{instance.product.slug}/thumbs/{uuid.uuid4().hex}.webp"


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField("Фото", upload_to=product_image_path)
    thumbnail = models.ImageField(upload_to=product_thumbnail_path, blank=True, editable=False)
    alt = models.CharField("Alt-текст", max_length=255, blank=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "фото"
        verbose_name_plural = "фото"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return self.alt or self.image.name

    def save(self, *args, **kwargs) -> None:
        if self.image and not getattr(self.image, "_committed", True):
            full, thumb = to_webp(self.image.file)
            self.image.save("image.webp", full, save=False)
            self.thumbnail.save("thumb.webp", thumb, save=False)
        if not self.alt:
            self.alt = self.product.name
        super().save(*args, **kwargs)


@receiver(post_delete, sender=ProductImage)
def delete_product_image_files(sender, instance: ProductImage, **kwargs) -> None:
    for field_file in (instance.image, instance.thumbnail):
        if field_file:
            field_file.delete(save=False)


DEFAULT_ADDRESS = "Казахстан, г. Астана, ул. Керей Жанибек хандар, 50/3"
DEFAULT_WHATSAPP = "+7 777 305 4243\n+7 777 377 3763"


class SiteSettings(models.Model):
    company_name = models.CharField("Название компании", max_length=200, default="Батыс Курылыс XXI")
    address = models.CharField("Адрес", max_length=300, blank=True, default=DEFAULT_ADDRESS)
    phones = models.TextField("Телефоны", blank=True, help_text="По одному номеру в строке.")
    whatsapp_numbers = models.TextField(
        "WhatsApp", blank=True, default=DEFAULT_WHATSAPP, help_text="По одному номеру в строке."
    )
    notification_email = models.EmailField("Email для заявок", blank=True)
    public_email = models.EmailField("Email для клиентов", blank=True)
    working_hours = models.CharField(
        "Часы работы", max_length=200, blank=True, help_text="Формат schema.org, например: Mo-Fr 09:00-18:00"
    )
    bin = models.CharField("БИН", max_length=12, blank=True)
    map_url = models.URLField("Ссылка на карту (2GIS)", blank=True)

    class Meta:
        verbose_name = "настройки сайта"
        verbose_name_plural = "настройки сайта"

    def __str__(self) -> str:
        return "Настройки сайта"

    def save(self, *args, **kwargs) -> None:
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "SiteSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def phone_list(self) -> list[str]:
        return [line.strip() for line in self.phones.splitlines() if line.strip()]

    @property
    def whatsapp_list(self) -> list[dict]:
        return [
            {"display": line.strip(), "wa": re.sub(r"\D", "", line)}
            for line in self.whatsapp_numbers.splitlines()
            if line.strip()
        ]
