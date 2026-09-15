from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"
    verbose_name = "Каталог"

    def ready(self) -> None:
        from catalog.roles import ensure_manager_group

        post_migrate.connect(ensure_manager_group, dispatch_uid="catalog.ensure_manager_group")
