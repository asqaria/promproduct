from collections import Counter
from pathlib import Path

import yaml
from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Category, Product, ProductImage, ProductSpec

CATEGORY_FIELDS = ("name", "seo_text", "meta_title", "meta_description", "sort_order", "is_active")
PRODUCT_FIELDS = (
    "name", "model_code", "short_description", "description",
    "meta_title", "meta_description", "sort_order", "is_active",
)


class Command(BaseCommand):
    help = "Загружает категории и товары из content/catalog.yaml (повторный запуск обновляет записи)."

    def add_arguments(self, parser):
        parser.add_argument("--content", default=str(Path(settings.BASE_DIR) / "content" / "catalog.yaml"))
        parser.add_argument("--images-dir", default=str(Path(settings.BASE_DIR) / "content" / "images"))
        parser.add_argument(
            "--replace-all",
            action="store_true",
            help="Всегда пересоздавать характеристики и фото, даже если в YAML для товара их нет "
            "(старое поведение; стирает фото, добавленные вручную в админке).",
        )

    def handle(self, *args, **options):
        content_path = Path(options["content"])
        images_dir = Path(options["images_dir"])
        replace_all = options["replace_all"]
        if not content_path.exists():
            raise CommandError(f"Файл не найден: {content_path}")
        data = yaml.safe_load(content_path.read_text(encoding="utf-8"))

        stats: Counter = Counter()
        missing_images: list[str] = []

        with transaction.atomic():
            categories = {}
            for entry in data["categories"]:
                defaults = {field: entry[field] for field in CATEGORY_FIELDS if field in entry}
                category, created = Category.objects.update_or_create(slug=entry["slug"], defaults=defaults)
                categories[category.slug] = category
                stats["categories_created" if created else "categories_updated"] += 1

            for entry in data["products"]:
                category = categories.get(entry["category"])
                if category is None:
                    raise CommandError(f"Товар {entry['slug']}: неизвестная категория {entry['category']}")
                defaults = {field: entry[field] for field in PRODUCT_FIELDS if field in entry}
                defaults["category"] = category
                product, created = Product.objects.update_or_create(slug=entry["slug"], defaults=defaults)
                stats["products_created" if created else "products_updated"] += 1

                specs = entry.get("specs", [])
                if specs or replace_all:
                    product.specs.all().delete()
                    ProductSpec.objects.bulk_create(
                        [
                            ProductSpec(product=product, name=str(name), value=str(value), sort_order=index)
                            for index, (name, value) in enumerate(specs)
                        ]
                    )
                else:
                    stats["specs_kept"] += 1

                images = entry.get("images", [])
                if images or replace_all:
                    product.images.all().delete()
                    for index, image in enumerate(images):
                        path = images_dir / image["file"]
                        if not path.exists():
                            missing_images.append(image["file"])
                            continue
                        with path.open("rb") as handle:
                            ProductImage.objects.create(
                                product=product,
                                image=File(handle, name=path.name),
                                alt=image.get("alt", ""),
                                sort_order=index,
                            )
                else:
                    stats["images_kept"] += 1

                if entry.get("needs_review"):
                    stats["needs_review"] += 1

        self.stdout.write(
            f"Категорий: создано {stats['categories_created']}, обновлено {stats['categories_updated']}\n"
            f"Товаров: создано {stats['products_created']}, обновлено {stats['products_updated']}\n"
            f"Требуют вычитки: {stats['needs_review']}\n"
            f"Товаров с фото, оставленными как в БД (в YAML не указаны): {stats['images_kept']}\n"
            f"Товаров с характеристиками, оставленными как в БД (в YAML не указаны): {stats['specs_kept']}"
        )
        if missing_images:
            self.stdout.write("Не найдены фото:\n" + "\n".join(f"  {name}" for name in missing_images))
