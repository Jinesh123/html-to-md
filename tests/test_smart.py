"""Tests for smart class/style → Markdown role inference."""

from html_to_md import convert


def test_utility_class_page_becomes_headings():
    html = """
    <h1>Hello World</h1>
    <h2>Hello World</h2>
    <h3>Hello World</h3>
    <h4>Hello World</h4>
    <h5>Hello World</h5>
    <h6>Hello World</h6>
    <p class="text-red-500 text-2xl font-bold">Hello World</p>
    """
    result = convert(html).strip()
    blocks = [b.strip() for b in result.split("\n\n") if b.strip()]
    assert blocks == [
        "# Hello World",
        "## Hello World",
        "### Hello World",
        "#### Hello World",
        "##### Hello World",
        "###### Hello World",
        "## Hello World",  # text-2xl font-bold → h2 (size hierarchy)
    ]


def test_size_hierarchy_text_3xl_larger_than_2xl():
    html = (
        '<p class="text-3xl font-bold">Big</p>'
        '<p class="text-2xl font-bold">Less</p>'
        '<p class="text-xl font-semibold">Mid</p>'
        '<p class="text-lg font-semibold">Smaller</p>'
    )
    blocks = [b.strip() for b in convert(html).strip().split("\n\n")]
    assert blocks == ["# Big", "## Less", "### Mid", "#### Smaller"]


def test_font_weight_class_becomes_bold():
    assert convert('<p class="font-bold">Bold Font Weight</p>').strip() == (
        "**Bold Font Weight**"
    )
    assert convert('<p class="font-semibold">Semi</p>').strip() == "**Semi**"


def test_italic_and_strike_classes():
    assert convert('<p class="italic">Italic Paragraph</p>').strip() == (
        "*Italic Paragraph*"
    )
    assert convert(
        '<p class="line-through">Strikethrough Paragraph</p>'
    ).strip() == "~~Strikethrough Paragraph~~"


def test_underline_class_and_tag():
    assert convert('<p class="underline">Underlined</p>').strip() == (
        "<u>Underlined</u>"
    )
    assert convert("<p><u>Underlined text using HTML</u></p>").strip() == (
        "<u>Underlined text using HTML</u>"
    )


def test_text_transforms():
    assert convert(
        '<p class="uppercase">this should become uppercase</p>'
    ).strip() == "THIS SHOULD BECOME UPPERCASE"
    assert convert(
        '<p class="lowercase">THIS SHOULD BECOME LOWERCASE</p>'
    ).strip() == "this should become lowercase"
    assert convert(
        '<p class="capitalize">this should capitalize every word</p>'
    ).strip() == "This Should Capitalize Every Word"


def test_inline_span_styles():
    html = (
        '<p>This is <span class="text-red font-bold">red bold text</span> '
        "inside.</p>"
    )
    assert convert(html).strip() == "This is **red bold text** inside."

    html = (
        '<p>This is <span class="italic text-blue">blue italic text</span> '
        "x.</p>"
    )
    assert convert(html).strip() == "This is *blue italic text* x."

    html = (
        "<p>Normal "
        '<span style="font-weight: bold; font-style: italic;">'
        "combined</span> end.</p>"
    )
    assert convert(html).strip() == "Normal ***combined*** end."


def test_combined_heading_with_italic():
    html = '<p class="text-xl font-semibold italic text-blue">Title</p>'
    assert convert(html).strip() == "### *Title*"


def test_small_strike_italic():
    html = '<p class="text-sm italic text-gray line-through">Small</p>'
    assert convert(html).strip() == "~~*Small*~~"


def test_semantic_title_class():
    html = '<div class="page-title">Welcome</div>'
    assert convert(html).strip() == "# Welcome"


def test_semantic_heading_level_class():
    html = '<p class="heading-2">Mid</p>'
    assert convert(html).strip() == "## Mid"


def test_named_heading_like_classes():
    assert convert('<p class="heading-like">A</p>').strip() == "## A"
    assert convert('<p class="subheading-like">B</p>').strip() == "### B"


def test_inline_style_heading():
    html = '<p style="font-size: 2rem; font-weight: 700">Styled</p>'
    assert convert(html).strip() == "## Styled"


def test_smart_can_be_disabled():
    html = '<p class="text-2xl font-bold">Hello World</p>'
    assert convert(html, smart=False).strip() == "Hello World"


def test_empty_image_link_dropped_when_img_skipped():
    html = '<a href="https://example.com"><img src="x.png" alt="x"></a>'
    assert convert(html, skip_tags=["img"]).strip() == ""


def test_list_preserves_space_before_strong():
    html = "<ol><li>Generate your <strong>API key</strong>.</li></ol>"
    assert convert(html).strip() == "1. Generate your **API key**."


def test_nested_list_tight_indent():
    html = "<ul><li>Frontend<ul><li>HTML</li><li>CSS</li></ul></li></ul>"
    result = convert(html).strip()
    assert result == "- Frontend\n    - HTML\n    - CSS"
