"""Tests for headings, paragraphs, breaks, and horizontal rules."""

from html_to_md import convert


def test_headings():
    html = "<h1>One</h1><h2>Two</h2><h3>Three</h3><h6>Six</h6>"
    assert convert(html).strip() == "# One\n\n## Two\n\n### Three\n\n###### Six"


def test_heading_keeps_level_when_higher_skipped():
    html = "<h1>Skip me</h1><h2>Keep me</h2>"
    assert convert(html, skip_tags=["h1"]).strip() == "## Keep me"


def test_paragraph_and_emphasis():
    html = "<p>Hello <strong>world</strong> and <em>friends</em>.</p>"
    assert convert(html).strip() == "Hello **world** and *friends*."


def test_br_and_hr():
    html = "<p>a<br>b</p><hr><p>c</p>"
    result = convert(html).strip()
    assert "a  \nb" in result
    assert "---" in result
    assert result.endswith("c")


def test_blockquote():
    html = "<blockquote><p>Quoted</p></blockquote>"
    assert convert(html).strip() == "> Quoted"


def test_nested_blockquote_lines():
    html = "<blockquote><p>Line one</p><p>Line two</p></blockquote>"
    result = convert(html).strip()
    assert result == "> Line one\n>\n> Line two"
