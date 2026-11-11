"""Tests for inline emphasis, links, images, code, and entities."""

from html_to_md import convert
from html_to_md.escape import wrap_inline_code


def test_bold_italic_strike_aliases():
    html = "<p><b>b</b> <i>i</i> <s>s</s> <del>d</del> <strike>x</strike></p>"
    result = convert(html).strip()
    assert "**b**" in result
    assert "*i*" in result
    assert "~~s~~" in result
    assert "~~d~~" in result
    assert "~~x~~" in result


def test_link_with_title():
    html = '<p><a href="https://example.com" title="Example">click</a></p>'
    assert (
        convert(html).strip()
        == '[click](https://example.com "Example")'
    )


def test_link_missing_href():
    html = "<p><a>just text</a></p>"
    assert convert(html).strip() == "just text"


def test_image():
    html = '<img src="pic.png" alt="A pic" title="t">'
    assert convert(html).strip() == '![A pic](pic.png "t")'


def test_image_missing_src():
    html = '<img alt="fallback">'
    assert convert(html).strip() == "fallback"


def test_inline_code():
    html = "<p>Use <code>x</code>.</p>"
    assert convert(html).strip() == "Use `x`."


def test_inline_code_with_backticks():
    assert wrap_inline_code("a`b") == "``a`b``"
    html = "<p><code>a`b</code></p>"
    assert convert(html).strip() == "``a`b``"


def test_fenced_code_with_language():
    html = '<pre><code class="language-python">print(1)\n</code></pre>'
    result = convert(html).strip()
    assert result.startswith("```python\n")
    assert "print(1)" in result
    assert result.endswith("```")


def test_fenced_code_data_lang():
    html = '<pre><code data-lang="js">x</code></pre>'
    assert "```js\n" in convert(html)


def test_entities():
    html = "<p>A &amp; B&nbsp;C</p>"
    result = convert(html).strip()
    assert "A & B" in result
    # nbsp becomes a regular space after collapse
    assert "B C" in result or "B\xa0C" in result or "B C" in result.replace(
        "\xa0", " "
    )


def test_escape_specials():
    html = "<p>Use *stars* and [brackets]</p>"
    result = convert(html).strip()
    assert r"\*stars\*" in result
    assert r"\[brackets\]" in result


def test_raw_html_tags():
    html = "<p>H<sub>2</sub>O and <kbd>Ctrl</kbd></p>"
    result = convert(html).strip()
    assert "<sub>2</sub>" in result
    assert "<kbd>Ctrl</kbd>" in result


def test_q_and_dl():
    html = "<p><q>hi</q></p><dl><dt>Term</dt><dd>Definition</dd></dl>"
    result = convert(html).strip()
    assert '"hi"' in result
    assert "**Term**" in result
    assert "Definition" in result


def test_figure_caption():
    html = (
        '<figure><img src="a.png" alt="A">'
        "<figcaption>Caption</figcaption></figure>"
    )
    result = convert(html).strip()
    assert "![A](a.png)" in result
    assert "*Caption*" in result
