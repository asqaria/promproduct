from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from catalog.models import Product


class QuoteRequest(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Новая"
        IN_PROGRESS = "in_progress", "В работе"
        CLOSED = "closed", "Закрыта"

    name = models.CharField("Имя", max_length=100)
    phone = models.CharField("Телефон", max_length=16)
    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices, default=Status.NEW, db_index=True
    )
    admin_note = models.TextField("Заметка менеджера", blank=True)
    email_sent = models.BooleanField("Письмо отправлено", default=False)
    source_ip = models.GenericIPAddressField("IP", null=True, blank=True)
    created_at = models.DateTimeField("Создана", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "заявка"
        verbose_name_plural = "заявки"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Заявка №{self.pk} — {self.name}"


class QuoteItem(models.Model):
    request = models.ForeignKey(QuoteRequest, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", verbose_name="Товар"
    )
    product_name = models.CharField("Название на момент заявки", max_length=255)
    quantity = models.PositiveIntegerField(
        "Количество", validators=[MinValueValidator(1), MaxValueValidator(999)]
    )

    class Meta:
        verbose_name = "позиция"
        verbose_name_plural = "позиции"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product_name} × {self.quantity}"
