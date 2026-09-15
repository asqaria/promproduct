import re

from django import forms

from orders.services import ItemsError, normalize_phone, parse_items


class QuoteForm(forms.Form):
    name = forms.CharField(
        label="Имя",
        min_length=2,
        max_length=100,
        error_messages={
            "required": "Укажите имя.",
            "min_length": "Имя слишком короткое.",
            "max_length": "Имя слишком длинное.",
        },
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    phone = forms.CharField(
        label="Телефон",
        max_length=32,
        error_messages={"required": "Укажите телефон."},
        widget=forms.TextInput(
            attrs={"type": "tel", "autocomplete": "tel", "placeholder": "+7 777 305 4243"}
        ),
    )
    items = forms.CharField(required=False, widget=forms.HiddenInput)
    website = forms.CharField(
        required=False, label="Сайт", widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"})
    )

    def clean_name(self) -> str:
        name = self.cleaned_data["name"]
        if re.search(r"[\x00-\x1f\x7f]", name):
            raise forms.ValidationError("Имя содержит недопустимые символы.")
        return name

    def clean_phone(self) -> str:
        phone = normalize_phone(self.cleaned_data["phone"])
        if phone is None:
            raise forms.ValidationError("Укажите телефон в формате +7 XXX XXX XX XX.")
        return phone

    def clean_items(self):
        raw = self.cleaned_data.get("items")
        if not raw:
            raise forms.ValidationError("Добавьте товары в запрос.")
        try:
            return parse_items(raw)
        except ItemsError as exc:
            raise forms.ValidationError(str(exc)) from exc

    def is_spam(self) -> bool:
        return bool(self.data.get("website", "").strip())
