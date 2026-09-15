import pytest
from django.contrib.staticfiles import finders


@pytest.mark.parametrize("path", ["css/site.css", "js/cart.js"])
def test_static_assets_exist(path):
    assert finders.find(path) is not None


def test_cart_script_uses_agreed_contract():
    source = open(finders.find("js/cart.js"), encoding="utf-8").read()
    for marker in [
        '"quote_cart"', "[data-add-to-quote]", "[data-quote-list]", '[name="items"]',
        "[data-cart-count]", "[data-cart-clear]", "[data-gallery-thumb]",
        "[data-drawer-toggle]", "[data-drawer-backdrop]", "sidebar--open", "quote-item__row", "Escape",
    ]:
        assert marker in source
    assert "innerHTML" not in source


def test_css_defines_classes_used_by_script():
    css = open(finders.find("css/site.css"), encoding="utf-8").read()
    for selector in [".sidebar--open", ".quote-item__row", ".toast", ".drawer-backdrop"]:
        assert selector in css
