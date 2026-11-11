"""Markdown escaping and whitespace helpers."""

from __future__ import annotations

import re

# Characters that can change Markdown meaning when left unescaped in text.
# Pipes are handled separately in table cells via escape_cell.
_MD_SPECIALS = re.compile(r"([\\`*_{}\[\]<>#])")

# Leading list/heading markers at the start of a line in block context.
_LEADING_MARKERS = re.compile(r"^([-+*] |\d+\. |#{1,6} )", re.MULTILINE)

_WHITESPACE = re.compile(r"[ \t\r\n\f\v]+")


def collapse_whitespace(text: str) -> str:
    """Collapse runs of HTML whitespace to a single space."""
    return _WHITESPACE.sub(" ", text)


def escape_text(
    text: str,
    *,
    collapse: bool = True,
    leading_markers: bool = False,
) -> str:
    """Escape Markdown special characters in a text node.

    Args:
        text: Raw text (entities should already be decoded by BeautifulSoup).
        collapse: When True, collapse HTML whitespace to a single space.
        leading_markers: When True, escape leading ``1. `` / ``- `` / ``# ``
            so they are not interpreted as lists/headings. Off by default
            because TOC labels like ``1. Interpretation`` are real content.
    """
    if collapse:
        text = collapse_whitespace(text)
    # Escape backslash first via the character class, then the rest.
    text = _MD_SPECIALS.sub(r"\\\1", text)
    if leading_markers:
        text = _LEADING_MARKERS.sub(lambda m: "\\" + m.group(1), text)
    return text


def escape_cell(text: str) -> str:
    """Escape pipe characters for GFM table cells and flatten newlines."""
    text = text.replace("\n", " ").replace("|", r"\|")
    return collapse_whitespace(text).strip()


def wrap_inline_code(code: str) -> str:
    """Wrap inline code in enough backticks to avoid conflicts with content."""
    # Find longest run of backticks in the content.
    runs = re.findall(r"`+", code)
    longest = max((len(r) for r in runs), default=0)
    fence = "`" * (longest + 1)
    # Pad with spaces when content starts/ends with a backtick.
    if code.startswith("`") or code.endswith("`"):
        return f"{fence} {code} {fence}"
    return f"{fence}{code}{fence}"
