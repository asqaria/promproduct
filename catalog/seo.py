from django.conf import settings
from django.utils.html import strip_tags


def absolute_url(path: str) -> str:
    return f"{settings.SITE_URL}{path}"


def truncate(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;:—-")
    return f"{cut}…"


def _plain(html: str) -> str:
    return " ".join(strip_tags(html or "").split())


def category_title(category, site_name: str) -> str:
    return category.meta_title or f"{category.name} купить в Астане — {site_name}"


def category_description(category) -> str:
    if category.meta_description:
        return category.meta_description
    text = _plain(category.seo_text)
    if text:
        return truncate(text)
    return f"{category.name}: каталог, характеристики и запрос коммерческого предложения."


def product_title(product, site_name: str) -> str:
    return product.meta_title or f"{product.name} купить в Астане — {site_name}"


def product_description(product) -> str:
    if product.meta_description:
        return product.meta_description
    return truncate(product.short_description or _plain(product.description))


def breadcrumb_ld(items: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": index, "name": name, "item": absolute_url(path)}
            for index, (name, path) in enumerate(items, start=1)
        ],
    }


def item_list_ld(name: str, items: list[tuple[str, str]]) -> dict:
    """ItemList для страниц-списков: пары (название, путь) в порядке вывода."""
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": name,
        "numberOfItems": len(items),
        "itemListElement": [
            {"@type": "ListItem", "position": index, "name": item_name, "url": absolute_url(path)}
            for index, (item_name, path) in enumerate(items, start=1)
        ],
    }


def product_ld(product) -> dict:
    url = absolute_url(product.get_absolute_url())
    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "description": product_description(product),
        "url": url,
        "category": product.category.name,
        "itemCondition": "https://schema.org/NewCondition",
    }
    images = [absolute_url(image.image.url) for image in product.images.all() if image.image]
    if images:
        data["image"] = images
    if product.model_code:
        data["sku"] = product.model_code
    price = product.displayed_price
    if price is not None:
        data["offers"] = {
            "@type": "Offer",
            "price": str(price),
            "priceCurrency": "KZT",
            "availability": "https://schema.org/InStock",
            "url": url,
        }
    return data


def local_business_ld(site) -> dict:
    data = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": site.company_name,
        "url": settings.SITE_URL,
    }
    if site.address:
        data["address"] = {
            "@type": "PostalAddress",
            "streetAddress": site.address,
            "addressLocality": "Астана",
            "addressCountry": "KZ",
        }
    phones = site.phone_list + [item["display"] for item in site.whatsapp_list]
    if phones:
        data["telephone"] = phones[0]
    if site.public_email:
        data["email"] = site.public_email
    if site.working_hours:
        data["openingHours"] = site.working_hours
    if site.bin:
        data["taxID"] = site.bin
    if site.map_url:
        data["hasMap"] = site.map_url
    return data
