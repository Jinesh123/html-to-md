"""Tests for tag skipping and pruning."""

from html_to_md import Converter, convert
from html_to_md.options import ALWAYS_SKIP, Options


def test_default_skips_script_and_style():
    html = (
        "<p>Keep</p>"
        "<script>alert(1)</script>"
        "<style>.x{}</style>"
        "<noscript>no</noscript>"
        "<template>t</template>"
    )
    result = convert(html).strip()
    assert result == "Keep"
    assert "alert" not in result
    assert ".x" not in result


def test_skip_removes_element_and_descendants():
    html = (
        "<p>Intro</p>"
        '<footer><a href="/x">link</a><p>bye</p></footer>'
        "<p>Outro</p>"
    )
    result = convert(html, skip_tags=["footer"]).strip()
    assert result == "Intro\n\nOutro"
    assert "link" not in result
    assert "bye" not in result


def test_skip_case_insensitive():
    html = "<HEADER>top</HEADER><p>body</p>"
    result = convert(html, skip_tags=["HeAdEr"]).strip()
    assert result == "body"
    assert "top" not in result


def test_skip_img_header_h1():
    html = (
        "<h1>Title</h1>"
        "<header>nav bits</header>"
        '<p>Text <img src="x.png" alt="x"> more</p>'
        "<footer>foot</footer>"
    )
    result = convert(
        html, skip_tags=["img", "footer", "header", "h1"]
    ).strip()
    assert "Title" not in result
    assert "nav bits" not in result
    assert "foot" not in result
    assert "![x]" not in result
    assert "Text" in result
    assert "more" in result


def test_always_skip_stacked_on_user_tags():
    opts = Options.from_skip_tags(["img"])
    assert "img" in opts.skip_tags
    for tag in ALWAYS_SKIP:
        assert tag in opts.skip_tags


def test_converter_reuse():
    converter = Converter(skip_tags=["nav"])
    assert converter.convert("<p>a</p><nav>n</nav>").strip() == "a"


def test_comments_removed():
    html = "<p>hi</p><!-- secret --><p>there</p>"
    result = convert(html).strip()
    assert "secret" not in result
    assert result == "hi\n\nthere"


def test_malformed_html():
    html = "<p>Unclosed <strong>bold <em>and italic</p>"
    result = convert(html)
    assert "bold" in result
    assert "italic" in result
