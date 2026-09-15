from catalog.sanitize import ALLOWED_TAGS, sanitize_html


def test_empty_values_return_empty_string():
    assert sanitize_html(None) == ""
    assert sanitize_html("") == ""


def test_script_and_style_removed_with_content():
    result = sanitize_html("<script>alert(1)</script><style>p{}</style><p>ok</p>")
    assert result == "<p>ok</p>"


def test_style_and_class_attributes_removed():
    assert sanitize_html('<p style="color:red" class="x">text</p>') == "<p>text</p>"


def test_font_tag_unwrapped_keeping_text():
    assert sanitize_html('<p><font color="red">text</font></p>') == "<p>text</p>"


def test_img_removed():
    assert sanitize_html('<p>a<img src="x.jpg" onerror="alert(1)">b</p>') == "<p>ab</p>"


def test_javascript_links_lose_href():
    result = sanitize_html('<a href="javascript:alert(1)">x</a>')
    assert "javascript" not in result
    assert ">x</a>" in result


def test_allowed_link_keeps_href_and_gets_rel():
    result = sanitize_html('<a href="https://prom-products.kz/" target="_blank">site</a>')
    assert 'href="https://prom-products.kz/"' in result
    assert 'rel="noopener noreferrer"' in result
    assert "target" not in result


def test_tables_and_lists_kept():
    html = (
        "<table><thead><tr><th>A</th></tr></thead><tbody><tr><td>1</td></tr></tbody></table>"
        "<ul><li>x</li></ul>"
    )
    assert sanitize_html(html) == html


def test_allowed_tags_match_spec():
    assert ALLOWED_TAGS == {
        "p", "br", "strong", "em", "ul", "ol", "li", "h2", "h3", "h4",
        "a", "table", "thead", "tbody", "tr", "th", "td",
    }
