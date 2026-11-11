"""Tests for lists and tables."""

from html_to_md import convert


def test_unordered_list():
    html = "<ul><li>one</li><li>two</li></ul>"
    assert convert(html).strip() == "- one\n- two"


def test_ordered_list():
    html = "<ol><li>one</li><li>two</li></ol>"
    assert convert(html).strip() == "1. one\n2. two"


def test_ordered_list_start():
    html = '<ol start="3"><li>three</li><li>four</li></ol>'
    assert convert(html).strip() == "3. three\n4. four"


def test_nested_list():
    html = "<ul><li>parent<ul><li>child</li></ul></li></ul>"
    result = convert(html).strip()
    assert result.startswith("- parent")
    assert "    - child" in result


def test_list_in_blockquote():
    html = "<blockquote><ul><li>a</li><li>b</li></ul></blockquote>"
    result = convert(html).strip()
    assert result == "> - a\n> - b"


def test_simple_table():
    html = """
    <table>
      <thead><tr><th>A</th><th>B</th></tr></thead>
      <tbody><tr><td>1</td><td>2</td></tr></tbody>
    </table>
    """
    result = convert(html).strip()
    assert result == "| A | B |\n| --- | --- |\n| 1 | 2 |"


def test_table_without_thead_uses_first_row():
    html = """
    <table>
      <tr><th>Name</th><th>Age</th></tr>
      <tr><td>Ada</td><td>36</td></tr>
    </table>
    """
    result = convert(html).strip()
    lines = result.splitlines()
    assert lines[0] == "| Name | Age |"
    assert lines[1] == "| --- | --- |"
    assert lines[2] == "| Ada | 36 |"


def test_table_escapes_pipes():
    html = "<table><tr><th>a|b</th></tr><tr><td>c|d</td></tr></table>"
    result = convert(html).strip()
    assert r"a\|b" in result
    assert r"c\|d" in result
