from itertools import count

from catalog.models import Category, Product

_seq = count(1)


def make_category(**kwargs) -> Category:
    n = next(_seq)
    data = {"name": f"Категория {n}", "slug": f"category-{n}"}
    data.update(kwargs)
    return Category.objects.create(**data)


def make_product(category: Category | None = None, **kwargs) -> Product:
    n = next(_seq)
    data = {
        "category": category or make_category(),
        "name": f"Трубогиб ТПГ-{n}",
        "slug": f"tpg-{n}",
    }
    data.update(kwargs)
    return Product.objects.create(**data)
