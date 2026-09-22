from django.contrib.sitemaps import Sitemap
from django.db.models import Max, Q

from catalog.models import Category, Product


class StaticSitemap(Sitemap):
    changefreq = "weekly"
    PRIORITIES = {"/": 1.0, "/catalog/": 0.9, "/contacts/": 0.5}

    def items(self):
        return list(self.PRIORITIES)

    def location(self, item: str) -> str:
        return item

    def priority(self, item: str) -> float:
        return self.PRIORITIES[item]

    def lastmod(self, item: str):
        """Дата последнего изменения каталога — сигнал для переобхода витрин."""
        if item == "/contacts/":
            return None
        return Product.objects.filter(is_active=True, category__is_active=True).aggregate(
            latest=Max("updated_at")
        )["latest"]


class CategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return (
            Category.objects.filter(is_active=True)
            .annotate(last_modified=Max("products__updated_at", filter=Q(products__is_active=True)))
            .filter(last_modified__isnull=False)
            .order_by("slug")
        )

    def lastmod(self, obj):
        return obj.last_modified


class ProductSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return (
            Product.objects.filter(is_active=True, category__is_active=True)
            .select_related("category")
            .order_by("slug")
        )

    def lastmod(self, obj):
        return obj.updated_at


SITEMAPS = {"static": StaticSitemap, "categories": CategorySitemap, "products": ProductSitemap}
