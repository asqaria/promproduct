import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from catalog.models import SiteSettings
from orders.models import QuoteRequest

logger = logging.getLogger(__name__)


def send_quote_notification(request_id: int) -> bool:
    quote = QuoteRequest.objects.prefetch_related("items__product__category").get(pk=request_id)
    recipient = SiteSettings.load().notification_email or settings.ADMIN_EMAIL
    if not recipient:
        logger.error("Quote %s: no notification recipient configured", quote.pk)
        return False

    lines = [f"Имя: {quote.name}", f"Телефон: {quote.phone}", "", "Позиции:"]
    for item in quote.items.all():
        link = f" {settings.SITE_URL}{item.product.get_absolute_url()}" if item.product else ""
        lines.append(f"- {item.product_name} — {item.quantity} шт.{link}")
    admin_link = settings.SITE_URL + reverse("admin:orders_quoterequest_change", args=[quote.pk])
    lines += ["", f"Открыть заявку в админке: {admin_link}"]

    try:
        send_mail(
            subject=f"Заявка №{quote.pk} — {quote.name}",
            message="\n".join(lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Quote %s: failed to send notification", quote.pk)
        return False

    QuoteRequest.objects.filter(pk=quote.pk).update(email_sent=True)
    return True
