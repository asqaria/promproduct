from django import forms
from django_prose_editor.fields import ProseEditorFormField

from catalog.models import Category, Product

EDITOR_EXTENSIONS = {
    "Bold": True,
    "Italic": True,
    "Heading": {"levels": [2, 3, 4]},
    "BulletList": True,
    "OrderedList": True,
    "ListItem": True,
    "Link": {"protocols": ["http", "https", "tel", "mailto"]},
    "Table": True,
    "TableRow": True,
    "TableHeader": True,
    "TableCell": True,
    "HardBreak": True,
}


class CategoryAdminForm(forms.ModelForm):
    seo_text = ProseEditorFormField(label="SEO-текст", required=False, extensions=EDITOR_EXTENSIONS)

    class Meta:
        model = Category
        fields = ["name", "slug", "seo_text", "meta_title", "meta_description", "sort_order", "is_active"]


class ProductAdminForm(forms.ModelForm):
    description = ProseEditorFormField(label="Описание", required=False, extensions=EDITOR_EXTENSIONS)

    class Meta:
        model = Product
        fields = [
            "category",
            "name",
            "slug",
            "model_code",
            "short_description",
            "description",
            "price",
            "show_price",
            "is_active",
            "sort_order",
            "meta_title",
            "meta_description",
        ]
