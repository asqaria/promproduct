import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_ESCAPES = {ord("<"): "\\u003C", ord(">"): "\\u003E", ord("&"): "\\u0026"}


@register.simple_tag
def ld_json(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False).translate(_ESCAPES)
    return mark_safe(f'<script type="application/ld+json">{payload}</script>')  # noqa: S308
