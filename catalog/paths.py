def category_path(slug: str) -> str:
    return f"/catalog/{slug}/"


def product_path(category_slug: str, slug: str) -> str:
    return f"/catalog/{category_slug}/{slug}/"
