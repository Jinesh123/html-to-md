"""Conversion options for HTML to Markdown."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

# Always dropped so non-content never leaks into Markdown output.
ALWAYS_SKIP: frozenset[str] = frozenset(
    {"script", "style", "noscript", "template"}
)

DEFAULT_BULLET = "-"
DEFAULT_FENCE = "```"


@dataclass(frozen=True)
class Options:
    """Options controlling HTML to Markdown conversion.

    Attributes:
        skip_tags: Tag names (case-insensitive) to remove along with their
            children before conversion. ``ALWAYS_SKIP`` tags are always
            included on top of this set.
        bullet: Marker used for unordered list items.
        fence: Fence marker used for fenced code blocks.
        smart: When True, infer Markdown roles from classes/styles
            (e.g. ``p.text-2xl.font-bold`` → heading).
    """

    skip_tags: frozenset[str] = field(default_factory=frozenset)
    bullet: str = DEFAULT_BULLET
    fence: str = DEFAULT_FENCE
    smart: bool = True

    @classmethod
    def from_skip_tags(
        cls,
        skip_tags: Iterable[str] | None = None,
        *,
        bullet: str = DEFAULT_BULLET,
        fence: str = DEFAULT_FENCE,
        smart: bool = True,
    ) -> Options:
        """Build options, merging user skip tags with ``ALWAYS_SKIP``."""
        user = {t.lower() for t in (skip_tags or ())}
        return cls(
            skip_tags=frozenset(user | set(ALWAYS_SKIP)),
            bullet=bullet,
            fence=fence,
            smart=smart,
        )
