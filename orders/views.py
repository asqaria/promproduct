import ipaddress

from django.core.cache import cache
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from catalog.models import SiteSettings
from orders.forms import QuoteForm
from orders.services import create_quote

RATE_LIMIT = 5
RATE_WINDOW_SECONDS = 3600


def client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    candidate = forwarded.split(",")[-1].strip() if forwarded else request.META.get("REMOTE_ADDR", "")
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def _rate_key(ip: str | None) -> str:
    return f"quote-rate:{ip or 'unknown'}"


def _is_rate_limited(ip: str | None) -> bool:
    return cache.get(_rate_key(ip), 0) >= RATE_LIMIT


def _register_submission(ip: str | None) -> None:
    key = _rate_key(ip)
    if cache.add(key, 1, RATE_WINDOW_SECONDS):
        return
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, RATE_WINDOW_SECONDS)


@require_http_methods(["GET", "POST"])
def quote(request):
    if request.method == "POST":
        form = QuoteForm(request.POST)
        if form.is_spam():
            return redirect("orders:thanks")
        ip = client_ip(request)
        if _is_rate_limited(ip):
            form.add_error(None, "Слишком много заявок. Попробуйте позже или напишите нам в WhatsApp.")
        elif form.is_valid():
            quote_request = create_quote(
                form.cleaned_data["name"], form.cleaned_data["phone"], form.cleaned_data["items"], ip
            )
            _register_submission(ip)
            return redirect(f"{reverse('orders:thanks')}?id={quote_request.pk}")
    else:
        form = QuoteForm()

    site = SiteSettings.load()
    context = {
        "nav_active": "",
        "quote_form": form,
        "page_title": f"Запрос коммерческого предложения — {site.company_name}",
        "page_description": "Список товаров для запроса коммерческого предложения.",
    }
    return render(request, "orders/quote.html", context)


@require_GET
def thanks(request):
    quote_id = request.GET.get("id", "")
    site = SiteSettings.load()
    context = {
        "nav_active": "",
        "quote_id": quote_id if quote_id.isdigit() else None,
        "page_title": f"Запрос отправлен — {site.company_name}",
    }
    return render(request, "orders/thanks.html", context)
