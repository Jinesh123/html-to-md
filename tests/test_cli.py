"""Tests for the html2md CLI."""

from pathlib import Path

from html_to_md import convert
from html_to_md.cli import main


def test_cli_file_to_file(tmp_path: Path):
    src = tmp_path / "in.html"
    dst = tmp_path / "out.md"
    html = "<h1>Hi</h1><p>There</p>"
    src.write_text(html, encoding="utf-8")

    assert main([str(src), "-o", str(dst)]) == 0
    assert dst.read_text(encoding="utf-8").strip() == convert(html).strip()


def test_cli_skip(tmp_path: Path, capsys):
    src = tmp_path / "in.html"
    src.write_text(
        "<h1>Title</h1><p>Body</p><footer>f</footer>",
        encoding="utf-8",
    )
    assert main([str(src), "--skip", "h1,footer"]) == 0
    out = capsys.readouterr().out.strip()
    assert out == "Body"
    assert "Title" not in out
    assert "f" not in out


def test_cli_repeatable_skip(tmp_path: Path, capsys):
    src = tmp_path / "in.html"
    src.write_text(
        '<p>x</p><img src="a.png" alt="a"><header>h</header>',
        encoding="utf-8",
    )
    assert main([str(src), "--skip", "img", "--skip", "header"]) == 0
    out = capsys.readouterr().out.strip()
    assert out == "x"


def test_cli_stdin(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin",
        type("S", (), {"read": staticmethod(lambda: "<p>stdin</p>")})(),
    )
    assert main([]) == 0
    assert capsys.readouterr().out.strip() == "stdin"
