from django.contrib import admin
from django.db.models import Count, URLField
from django.utils.html import format_html

from catalog.forms import CategoryAdminForm, ProductAdminForm
from catalog.models import Category, Product, ProductImage, ProductSpec, Redirect, SiteSettings

admin.site.site_header = "Батыс Курылыс XXI — управление сайтом"
admin.site.site_title = "Батыс Курылыс XXI"
admin.site.index_title = "Разделы"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    form = CategoryAdminForm
    list_display = ("name", "slug", "product_count", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (None, {"fields": ("name", "slug", "seo_text", "is_active", "sort_order")}),
        ("SEO", {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_product_count=Count("products"))

    @admin.display(description="Товаров", ordering="_product_count")
    def product_count(self, obj: Category) -> int:
        return obj._product_count


class ProductSpecInline(admin.TabularInline):
    model = ProductSpec
    extra = 1
    fields = ("name", "value", "sort_order")


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("preview", "image", "alt", "sort_order")
    readonly_fields = ("preview",)

    @admin.display(description="Превью")
    def preview(self, obj: ProductImage) -> str:
        if obj.pk and obj.thumbnail:
            return format_html('<img src="{}" alt="" style="height:60px">', obj.thumbnail.url)
        return "—"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ("thumb", "name", "category", "is_active", "show_price", "price")
    list_display_links = ("thumb", "name")
    list_filter = ("category", "is_active", "show_price")
    search_fields = ("name", "model_code")
    list_select_related = ("category",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ProductSpecInline, ProductImageInline)
    fieldsets = (
        (None, {"fields": ("category", "name", "slug", "model_code", "short_description", "description")}),
        ("Цена", {"fields": ("price", "show_price")}),
        ("Публикация", {"fields": ("is_active", "sort_order")}),
        ("SEO", {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("images")

    @admin.display(description="Фото")
    def thumb(self, obj: Product) -> str:
        image = obj.main_image
        if image and image.thumbnail:
            return format_html('<img src="{}" alt="" style="height:40px">', image.thumbnail.url)
        return "—"


@admin.register(Redirect)
class RedirectAdmin(admin.ModelAdmin):
    list_display = ("old_path", "new_path")
    search_fields = ("old_path", "new_path")


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    # Opt into Django 6.0 behaviour now for map_url: treat a scheme-less URL as
    # https:// instead of http://. Scoped to this one URLField (the admin is the
    # only place it's ever edited) so it doesn't rely on the deprecated
    # FORMS_URLFIELD_ASSUME_HTTPS transitional setting.
    formfield_overrides = {URLField: {"assume_scheme": "https"}}

    def has_add_permission(self, request) -> bool:
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
