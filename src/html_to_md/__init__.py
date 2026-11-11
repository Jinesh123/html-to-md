"""html_to_md — convert HTML to GitHub-flavored Markdown."""

from __future__ import annotations

from typing import Iterable

from html_to_md.converter import Converter
from html_to_md.options import Options

__all__ = ["Converter", "Options", "convert", "__version__"]
__version__ = "0.1.0"


def convert(
    html: str,
    *,
    skip_tags: Iterable[str] | None = None,
    bullet: str = "-",
    fence: str = "```",
    smart: bool = True,
) -> str:
    """Convert an HTML string to GitHub-flavored Markdown.

    Args:
        html: HTML document or fragment.
        skip_tags: Tag names to remove (with their children) before conversion.
            ``script``, ``style``, ``noscript``, and ``template`` are always
            skipped in addition to any tags listed here.
        bullet: Unordered list marker.
        fence: Fenced code block marker.
        smart: Infer roles from classes/styles (e.g. styled ``p`` → heading).

    Returns:
        Markdown string.
    """
    return Converter(
        skip_tags=skip_tags,
        bullet=bullet,
        fence=fence,
        smart=smart,
    ).convert(html)
