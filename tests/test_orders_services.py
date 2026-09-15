import json

import pytest
from django.contrib.auth.models import Group

from catalog.roles import MANAGER_GROUP
from orders.services import ItemsError, normalize_phone, parse_items
from tests.factories import make_category, make_product


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+7 777 305 42 43", "+77773054243"),
        ("87773054243", "+77773054243"),
        ("7 (777) 305-42-43", "+77773054243"),
        ("777 305 4243", "+77773054243"),
        ("+7 7172 00 00 00", "+77172000000"),
    ],
)
def test_normalize_phone_valid(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", None, "12345", "+1 202 555 0100", "99773054243", "8777305424", "+7777305424311"],
)
def test_normalize_phone_invalid(raw):
    assert normalize_phone(raw) is None


def items(*pairs) -> str:
    return json.dumps([{"id": pid, "qty": qty} for pid, qty in pairs])


@pytest.mark.django_db
def test_parse_items_returns_products_with_quantities_in_input_order():
    first, second = make_product(), make_product()
    assert parse_items(items((second.pk, 2), (first.pk, 1))) == [(second, 2), (first, 1)]


@pytest.mark.django_db
def test_parse_items_sums_duplicates_and_caps_at_999():
    product = make_product()
    assert parse_items(items((product.pk, 3), (product.pk, 4))) == [(product, 7)]
    assert parse_items(items((product.pk, 600), (product.pk, 600))) == [(product, 999)]


@pytest.mark.django_db
def test_parse_items_drops_unknown_and_inactive_products():
    active = make_product()
    inactive = make_product(is_active=False)
    in_hidden_category = make_product(category=make_category(is_active=False))
    result = parse_items(items((active.pk, 1), (inactive.pk, 1), (in_hidden_category.pk, 1), (999999, 1)))
    assert result == [(active, 1)]


@pytest.mark.django_db
def test_parse_items_error_when_nothing_available():
    with pytest.raises(ItemsError, match="Корзина пуста или товары недоступны"):
        parse_items(items((999999, 1)))


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (None, "Некорректный список товаров"),
        ("not json", "Некорректный список товаров"),
        ("{}", "от 1 до 50 позиций"),
        ("[]", "от 1 до 50 позиций"),
        (json.dumps([{"id": i, "qty": 1} for i in range(51)]), "от 1 до 50 позиций"),
        (json.dumps([{"id": "1", "qty": 1}]), "Некорректный список товаров"),
        (json.dumps([{"id": 1, "qty": True}]), "Некорректный список товаров"),
        (json.dumps([{"id": 1, "qty": 0}]), "от 1 до 999"),
        (json.dumps([{"id": 1, "qty": 1000}]), "от 1 до 999"),
        (json.dumps([1, 2]), "Некорректный список товаров"),
    ],
)
def test_parse_items_rejects_bad_payload(raw, message):
    with pytest.raises(ItemsError, match=message):
        parse_items(raw)


@pytest.mark.django_db
def test_manager_group_has_orders_permissions():
    codenames = set(Group.objects.get(name=MANAGER_GROUP).permissions.values_list("codename", flat=True))
    assert {"change_quoterequest", "view_quoteitem"} <= codenames
