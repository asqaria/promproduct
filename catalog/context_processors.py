from django.conf import settings

from catalog import seo
from catalog.models import Category, SiteSettings


def site(request) -> dict:
    site_settings = SiteSettings.load()
    return {
        "site": site_settings,
        "site_url": settings.SITE_URL,
        "nav_categories": Category.objects.filter(is_active=True).only("name", "slug"),
        # Разметка организации отдаётся на каждой странице, а не только на главной.
        "local_business": seo.local_business_ld(site_settings),
    }
