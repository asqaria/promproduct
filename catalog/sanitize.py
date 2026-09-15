import nh3

ALLOWED_TAGS = {
    "p", "br", "strong", "em", "ul", "ol", "li", "h2", "h3", "h4",
    "a", "table", "thead", "tbody", "tr", "th", "td",
}
ALLOWED_ATTRIBUTES = {"a": {"href"}}
URL_SCHEMES = {"http", "https", "tel", "mailto"}


def sanitize_html(value: str | None) -> str:
    """Оставляет только безопасное подмножество HTML для описаний и SEO-текстов."""
    if not value:
        return ""
    return nh3.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=URL_SCHEMES,
        link_rel="noopener noreferrer",
    ).strip()
