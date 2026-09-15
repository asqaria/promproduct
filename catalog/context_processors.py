from django.conf import settings

from catalog.models import Category, SiteSettings


def site(request) -> dict:
    return {
        "site": SiteSettings.load(),
        "site_url": settings.SITE_URL,
        "nav_categories": Category.objects.filter(is_active=True).only("name", "slug"),
    }
