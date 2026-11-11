"""Command-line interface for html_to_md."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from html_to_md import __version__, convert


def _parse_skip(values: list[str] | None) -> list[str]:
    """Expand repeatable comma-separated --skip arguments into tag names."""
    tags: list[str] = []
    if not values:
        return tags
    for value in values:
        for part in value.split(","):
            tag = part.strip()
            if tag:
                tags.append(tag)
    return tags


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="html2md",
        description="Convert HTML to GitHub-flavored Markdown.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Input HTML file. Reads stdin when omitted.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output Markdown file. Writes stdout when omitted.",
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        metavar="TAGS",
        help=(
            "Comma-separated HTML tags to skip (with their children). "
            "May be repeated. Always skips script, style, noscript, template."
        ),
    )
    parser.add_argument(
        "--no-smart",
        action="store_true",
        help=(
            "Disable smart conversion (class/style heuristics such as "
            "treating p.text-2xl.font-bold as a heading)."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.input:
        html = Path(args.input).read_text(encoding="utf-8")
    else:
        html = sys.stdin.read()

    skip_tags = _parse_skip(args.skip)
    markdown = convert(
        html,
        skip_tags=skip_tags or None,
        smart=not args.no_smart,
    )

    if args.output:
        Path(args.output).write_text(markdown, encoding="utf-8")
    else:
        sys.stdout.write(markdown)
        if markdown and not markdown.endswith("\n"):
            sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
