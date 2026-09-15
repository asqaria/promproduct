from django.contrib.auth.models import Group, Permission
from django.db.models import Q

MANAGER_GROUP = "Менеджер"
MANAGER_MODELS = {
    "catalog": ["category", "product", "productspec", "productimage", "redirect", "sitesettings"],
    "orders": ["quoterequest", "quoteitem"],
}


def ensure_manager_group(**kwargs) -> None:
    """Идемпотентно выдаёт группе все права на модели каталога и заявок (вызывается после migrate)."""
    group, _ = Group.objects.get_or_create(name=MANAGER_GROUP)
    condition = Q()
    for app_label, models in MANAGER_MODELS.items():
        condition |= Q(content_type__app_label=app_label, content_type__model__in=models)
    group.permissions.set(Permission.objects.filter(condition))
