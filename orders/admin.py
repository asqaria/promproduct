from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from orders.models import QuoteItem, QuoteRequest


class QuoteItemInline(admin.TabularInline):
    model = QuoteItem
    extra = 0
    can_delete = False
    fields = ("product_name", "quantity", "product_link")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None) -> bool:
        return False

    @admin.display(description="Товар на сайте")
    def product_link(self, obj: QuoteItem) -> str:
        if obj.product_id and obj.product:
            url = obj.product.get_absolute_url()
            return format_html(
                '<a href="{}" target="_blank" rel="noopener">открыть</a>', url
            )
        return "удалён"


@admin.register(QuoteRequest)
class QuoteRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "name", "phone_link", "items_count", "status", "email_sent")
    list_display_links = ("id", "name")
    list_editable = ("status",)
    list_filter = ("status", "email_sent", ("created_at", admin.DateFieldListFilter))
    search_fields = ("name", "phone")
    fields = ("created_at", "name", "phone", "status", "admin_note", "email_sent", "source_ip")
    readonly_fields = ("created_at", "name", "phone", "email_sent", "source_ip")
    inlines = (QuoteItemInline,)
    actions = ("mark_in_progress", "mark_closed")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_items_count=Count("items"))

    def has_add_permission(self, request) -> bool:
        return False

    @admin.display(description="Телефон", ordering="phone")
    def phone_link(self, obj: QuoteRequest) -> str:
        return format_html('<a href="tel:{}">{}</a>', obj.phone, obj.phone)

    @admin.display(description="Позиций", ordering="_items_count")
    def items_count(self, obj: QuoteRequest) -> int:
        return obj._items_count

    @admin.action(description="Отметить «В работе»")
    def mark_in_progress(self, request, queryset) -> None:
        queryset.update(status=QuoteRequest.Status.IN_PROGRESS)

    @admin.action(description="Отметить «Закрыта»")
    def mark_closed(self, request, queryset) -> None:
        queryset.update(status=QuoteRequest.Status.CLOSED)
