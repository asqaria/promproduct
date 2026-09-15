import json
import re

from catalog.models import Product

MAX_ITEMS = 50
MAX_QTY = 999


class ItemsError(ValueError):
    """Ошибка в списке позиций; текст показывается пользователю."""


def normalize_phone(raw: str | None) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10 and digits.startswith("7"):
        digits = "7" + digits
    elif len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if len(digits) != 11 or digits[0] != "7":
        return None
    return f"+{digits}"


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_items(raw: str | None) -> list[tuple[Product, int]]:
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ItemsError("Некорректный список товаров.") from exc

    if not isinstance(data, list) or not 1 <= len(data) <= MAX_ITEMS:
        raise ItemsError(f"В заявке должно быть от 1 до {MAX_ITEMS} позиций.")

    quantities: dict[int, int] = {}
    for entry in data:
        if not isinstance(entry, dict) or not _is_int(entry.get("id")) or not _is_int(entry.get("qty")):
            raise ItemsError("Некорректный список товаров.")
        if not 1 <= entry["qty"] <= MAX_QTY:
            raise ItemsError(f"Количество должно быть от 1 до {MAX_QTY}.")
        quantities[entry["id"]] = quantities.get(entry["id"], 0) + entry["qty"]

    products = Product.objects.filter(pk__in=quantities, is_active=True, category__is_active=True).in_bulk()
    result = [(products[pk], min(qty, MAX_QTY)) for pk, qty in quantities.items() if pk in products]
    if not result:
        raise ItemsError("Корзина пуста или товары недоступны.")
    return result
