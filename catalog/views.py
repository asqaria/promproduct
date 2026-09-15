from itertools import groupby
from urllib.parse import quote as urlquote

from django.conf import settings
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from catalog import seo
from catalog.models import Category, Product, SiteSettings

HOME_CRUMB = ("Главная", "/")
CATALOG_CRUMB = ("Каталог", "/catalog/")


def public_products():
    return (
        Product.objects.filter(is_active=True, category__is_active=True)
        .select_related("category")
        .prefetch_related("images")
    )


def categories_with_products():
    return (
        Category.objects.filter(is_active=True)
        .annotate(product_count=Count("products", filter=Q(products__is_active=True)))
        .filter(product_count__gt=0)
    )


def category_blocks() -> list[dict]:
    products = public_products().order_by("category__sort_order", "category__name", "sort_order", "name")
    return [
        {"category": items[0].category, "products": items}
        for items in (list(group) for _, group in groupby(products, key=lambda p: p.category_id))
    ]


@require_GET
def home(request):
    site = SiteSettings.load()
    context = {
        "nav_active": "all",
        "page_title": f"Гидравлический и трубный инструмент в Астане — {site.company_name}",
        "page_description": (
            "Трубогибы, прессы, домкраты, маслостанции, съёмники подшипников и шинообрабатывающее "
            "оборудование в Астане. Запрос коммерческого предложения онлайн."
        ),
        "category_blocks": category_blocks(),
        "local_business": seo.local_business_ld(site),
    }
    return render(request, "catalog/home.html", context)


@require_GET
def catalog_index(request):
    site = SiteSettings.load()
    breadcrumbs = [HOME_CRUMB, CATALOG_CRUMB]
    context = {
        "nav_active": "",
        "page_title": f"Каталог инструмента — {site.company_name}",
        "page_description": (
            "Каталог гидравлического и трубного инструмента: трубогибы, прессы, домкраты, маслостанции "
            "и другое оборудование. Цены и сроки — по запросу."
        ),
        "categories": categories_with_products(),
        "breadcrumbs": breadcrumbs,
        "breadcrumbs_ld": seo.breadcrumb_ld(breadcrumbs),
    }
    return render(request, "catalog/index.html", context)


@require_GET
def category_detail(request, slug: str):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    site = SiteSettings.load()
    breadcrumbs = [HOME_CRUMB, CATALOG_CRUMB, (category.name, category.get_absolute_url())]
    context = {
        "nav_active": category.slug,
        "category": category,
        "products": public_products().filter(category=category),
        "page_title": seo.category_title(category, site.company_name),
        "page_description": seo.category_description(category),
        "breadcrumbs": breadcrumbs,
        "breadcrumbs_ld": seo.breadcrumb_ld(breadcrumbs),
    }
    return render(request, "catalog/category.html", context)


@require_GET
def product_detail(request, category_slug: str, slug: str):
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related("images", "specs"),
        slug=slug,
        is_active=True,
        category__is_active=True,
    )
    if product.category.slug != category_slug:
        return redirect(product.get_absolute_url(), permanent=True)

    site = SiteSettings.load()
    whatsapp_url = ""
    if site.whatsapp_list:
        text = f"Здравствуйте! Интересует {product.name}: {seo.absolute_url(product.get_absolute_url())}"
        whatsapp_url = f"https://wa.me/{site.whatsapp_list[0]['wa']}?text={urlquote(text)}"

    breadcrumbs = [
        HOME_CRUMB,
        CATALOG_CRUMB,
        (product.category.name, product.category.get_absolute_url()),
        (product.name, product.get_absolute_url()),
    ]
    context = {
        "nav_active": product.category.slug,
        "product": product,
        "images": list(product.images.all()),
        "specs": list(product.specs.all()),
        "related": public_products().filter(category=product.category).exclude(pk=product.pk)[:4],
        "whatsapp_url": whatsapp_url,
        "page_title": seo.product_title(product, site.company_name),
        "page_description": seo.product_description(product),
        "breadcrumbs": breadcrumbs,
        "breadcrumbs_ld": seo.breadcrumb_ld(breadcrumbs),
        "product_ld": seo.product_ld(product),
    }
    return render(request, "catalog/product.html", context)


@require_GET
def contacts(request):
    site = SiteSettings.load()
    breadcrumbs = [HOME_CRUMB, ("Контакты", "/contacts/")]
    context = {
        "nav_active": "",
        "page_title": f"Контакты — {site.company_name}",
        "page_description": f"Адрес, телефоны и WhatsApp компании {site.company_name} в Астане.",
        "breadcrumbs": breadcrumbs,
        "breadcrumbs_ld": seo.breadcrumb_ld(breadcrumbs),
        "local_business": seo.local_business_ld(site),
    }
    return render(request, "catalog/contacts.html", context)


@require_GET
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /quote/",
        "",
        f"Sitemap: {settings.SITE_URL}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")
