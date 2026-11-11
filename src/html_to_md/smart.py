"""Smart conversion heuristics — infer Markdown roles from classes/styles.

Handles utility classes, inline ``style`` attributes (including ``pt`` sizes
common in PDF→HTML), and bold/size on descendant ``span``/``b`` nodes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Sequence

from bs4 import NavigableString, Tag

# Tags that often stand in for richer semantics / emphasis.
STYLABLE_TAGS: frozenset[str] = frozenset({"p", "div", "span"})
BOLD_TAGS: frozenset[str] = frozenset({"b", "strong"})
ITALIC_TAGS: frozenset[str] = frozenset({"i", "em"})

SIZE_CLASS_TO_LEVEL: dict[str, int] = {
    "text-6xl": 1,
    "text-5xl": 1,
    "text-4xl": 1,
    "text-3xl": 1,
    "text-2xl": 2,
    "text-xl": 3,
    "text-lg": 4,
}

WEIGHT_CLASSES: frozenset[str] = frozenset(
    {
        "font-bold",
        "font-semibold",
        "font-extrabold",
        "font-black",
        "bold",
        "fw-bold",
        "fw-bolder",
        "font-weight-bold",
    }
)

ITALIC_CLASSES: frozenset[str] = frozenset(
    {"italic", "font-italic", "fst-italic"}
)

STRIKE_CLASSES: frozenset[str] = frozenset(
    {"line-through", "strike", "strikethrough"}
)

UNDERLINE_CLASSES: frozenset[str] = frozenset({"underline"})

TRANSFORM_CLASSES: dict[str, str] = {
    "uppercase": "upper",
    "lowercase": "lower",
    "capitalize": "capitalize",
}

NAMED_HEADING_CLASSES: dict[str, int] = {
    "heading-like": 2,
    "subheading-like": 3,
}

_SEMANTIC_HEADING = re.compile(
    r"(?:^|[-_])(?:h([1-6])|heading-?([1-6])|title|hero[-_]?title|page[-_]?title)(?:$|[-_])",
    re.IGNORECASE,
)

# PDF→HTML often uses pt; also accept px/rem/em/% .
_FONT_SIZE = re.compile(
    r"font-size\s*:\s*([\d.]+)\s*(px|pt|rem|em|%)?",
    re.IGNORECASE,
)
_FONT_WEIGHT_EMPHASIS = re.compile(
    r"font-weight\s*:\s*(bold|bolder|[6-9]00)", re.IGNORECASE
)
_FONT_STYLE_ITALIC = re.compile(
    r"font-style\s*:\s*italic", re.IGNORECASE
)
_TEXT_DECORATION_STRIKE = re.compile(
    r"text-decoration(?:-line)?\s*:\s*[^;]*line-through", re.IGNORECASE
)
_TEXT_DECORATION_UNDERLINE = re.compile(
    r"text-decoration(?:-line)?\s*:\s*[^;]*underline", re.IGNORECASE
)
_TEXT_TRANSFORM = re.compile(
    r"text-transform\s*:\s*(uppercase|lowercase|capitalize)", re.IGNORECASE
)

_TOP = re.compile(r"(?:^|;)\s*top\s*:\s*([-\d.]+)\s*(pt|px|em|rem)?", re.I)
_LEFT = re.compile(r"(?:^|;)\s*left\s*:\s*([-\d.]+)\s*(pt|px|em|rem)?", re.I)


@dataclass(frozen=True)
class StyleHint:
    """Inferred Markdown / presentation hints for an HTML element."""

    heading_level: int | None = None
    bold: bool = False
    italic: bool = False
    strike: bool = False
    underline: bool = False
    transform: str | None = None  # upper | lower | capitalize

    @property
    def has_inline_style(self) -> bool:
        return bool(
            self.bold
            or self.italic
            or self.strike
            or self.underline
            or self.transform
        )


Role = StyleHint


def _class_list(el: Tag) -> list[str]:
    raw = el.get("class") or []
    if isinstance(raw, str):
        return raw.split()
    return [str(c) for c in raw]


def _classes(el: Tag) -> set[str]:
    return {c.lower() for c in _class_list(el)}


def _style(el: Tag) -> str:
    style = el.get("style") or ""
    return style if isinstance(style, str) else ""


def font_size_to_rem(value: float, unit: str | None) -> float:
    """Normalize a CSS font-size to rem (16px root)."""
    u = (unit or "px").lower()
    if u == "pt":
        # 1pt = 1/72in, 1px = 1/96in → 1pt = 4/3 px
        return (value * 4.0 / 3.0) / 16.0
    if u == "px" or u == "":
        return value / 16.0
    if u == "%":
        return (value / 100.0) * 1.0
    # rem / em treated as rem for heuristic purposes
    return value


def parse_font_size(style: str) -> float | None:
    """Return font-size in rem from an inline style string, if present."""
    if not style:
        return None
    match = _FONT_SIZE.search(style)
    if not match:
        return None
    return font_size_to_rem(float(match.group(1)), match.group(2))


def _level_from_rem(rem: float) -> int | None:
    """Map a rem font-size to a heading level.

    Tuned for both Tailwind-ish sizes and PDF→HTML ``pt`` titles (~16pt ≈ 1.34rem).
    """
    if rem >= 2.25:  # ~36px+
        return 1
    if rem >= 1.75:  # ~28–35px
        return 2
    if rem >= 1.45:  # ~24px
        return 3
    if rem >= 1.25:  # ~16pt / ~20px section titles
        return 2
    if rem >= 1.15:  # ~18px
        return 4
    return None


def _heading_level_from_classes(classes: set[str]) -> int | None:
    for name, level in NAMED_HEADING_CLASSES.items():
        if name in classes:
            return level

    for cls in classes:
        match = _SEMANTIC_HEADING.search(cls)
        if not match:
            continue
        h = match.group(1) or match.group(2)
        if h:
            return int(h)
        return 1

    if not (classes & WEIGHT_CLASSES):
        return None
    level: int | None = None
    for cls, mapped in SIZE_CLASS_TO_LEVEL.items():
        if cls in classes:
            if level is None or mapped < level:
                level = mapped
    return level


def _heading_level_from_style(style: str) -> int | None:
    if not style or not _FONT_WEIGHT_EMPHASIS.search(style):
        return None
    rem = parse_font_size(style)
    if rem is None:
        return None
    return _level_from_rem(rem)


def _is_bold_context(el: Tag) -> bool:
    """True if el is bold via tag, class, style, or a bold ancestor."""
    node: Tag | None = el
    while isinstance(node, Tag):
        name = (node.name or "").lower()
        if name in BOLD_TAGS:
            return True
        classes = _classes(node)
        if classes & WEIGHT_CLASSES:
            return True
        style = _style(node)
        if style and _FONT_WEIGHT_EMPHASIS.search(style):
            return True
        parent = node.parent
        node = parent if isinstance(parent, Tag) else None
    return False


def _heading_from_descendants(el: Tag) -> int | None:
    """Detect heading from largest bold descendant font-size (PDF→HTML pattern).

    Example::

        <p><b><span style="font-size:16.1pt">Title</span></b>
           <span style="font-size:10.7pt"> (Clause 1)</span></p>
    """
    best_rem = 0.0
    best_level: int | None = None

    nodes: list[Tag] = [el]
    nodes.extend(t for t in el.find_all(True) if isinstance(t, Tag))

    for node in nodes:
        rem = parse_font_size(_style(node))
        if rem is None:
            continue
        if not _is_bold_context(node):
            continue
        # Prefer nodes that actually contain text.
        if not node.get_text(strip=True):
            continue
        level = _level_from_rem(rem)
        if level is not None and rem > best_rem:
            best_rem = rem
            best_level = level
    return best_level


def _emphasis_from_classes(classes: set[str]) -> tuple[bool, bool, bool, bool]:
    bold = bool(classes & WEIGHT_CLASSES)
    italic = bool(classes & ITALIC_CLASSES)
    strike = bool(classes & STRIKE_CLASSES)
    underline = bool(classes & UNDERLINE_CLASSES)
    return bold, italic, strike, underline


def _emphasis_from_style(style: str) -> tuple[bool, bool, bool, bool]:
    if not style:
        return False, False, False, False
    bold = bool(_FONT_WEIGHT_EMPHASIS.search(style))
    italic = bool(_FONT_STYLE_ITALIC.search(style))
    strike = bool(_TEXT_DECORATION_STRIKE.search(style))
    underline = bool(_TEXT_DECORATION_UNDERLINE.search(style))
    return bold, italic, strike, underline


def _transform_from(classes: set[str], style: str) -> str | None:
    for cls, name in TRANSFORM_CLASSES.items():
        if cls in classes:
            return name
    if style:
        match = _TEXT_TRANSFORM.search(style)
        if match:
            return match.group(1).lower()
    return None


def infer_style(el: Tag) -> StyleHint | None:
    """Infer heading / emphasis / transform hints from class, style, and children."""
    name = (el.name or "").lower()
    if name not in STYLABLE_TAGS:
        return None

    classes = _classes(el)
    style = _style(el)

    heading = _heading_level_from_classes(classes)
    if heading is None:
        heading = _heading_level_from_style(style)
    # Only paragraphs: containers like positioned page <div>s must not become
    # one giant heading just because a child title uses a large font-size.
    if heading is None and name == "p":
        heading = _heading_from_descendants(el)

    bold_c, italic_c, strike_c, under_c = _emphasis_from_classes(classes)
    bold_s, italic_s, strike_s, under_s = _emphasis_from_style(style)

    if heading is not None:
        return StyleHint(
            heading_level=heading,
            bold=False,
            italic=italic_c or italic_s,
            strike=strike_c or strike_s,
            underline=under_c or under_s,
            transform=_transform_from(classes, style),
        )

    bold = bold_c or bold_s
    italic = italic_c or italic_s
    strike = strike_c or strike_s
    underline = under_c or under_s
    transform = _transform_from(classes, style)

    if not (bold or italic or strike or underline or transform):
        return None

    return StyleHint(
        bold=bold,
        italic=italic,
        strike=strike,
        underline=underline,
        transform=transform,
    )


def parse_position(el: Tag) -> tuple[float, float] | None:
    """Return (top, left) from inline style when both/absolute layout is present."""
    style = _style(el)
    if not style:
        return None
    top_m = _TOP.search(style)
    if not top_m:
        return None
    left_m = _LEFT.search(style)
    top = float(top_m.group(1))
    left = float(left_m.group(1)) if left_m else 0.0
    return (top, left)


def reading_order_key(el: Tag, index: int) -> tuple:
    """Sort key for absolute-positioned PDF→HTML: top, then left."""
    pos = parse_position(el)
    if pos is None:
        return (float("inf"), float("inf"), index)
    top, left = pos
    return (top, left, index)


LINE_TOLERANCE_PT = 6.0
# Relative font-size gap above which same-line elements are different content
# streams (e.g. 7.6pt marginal note vs 10.7pt body). TOC title 9.2pt + page
# 10.7pt stays under this and may still merge.
FONT_SIZE_MERGE_RATIO = 0.20


def dominant_font_size_rem(el: Tag) -> float | None:
    """Dominant font-size (rem) for an element, weighted by text length."""
    scored: list[tuple[int, float]] = []
    nodes: list[Tag] = [el]
    nodes.extend(n for n in el.find_all(True) if isinstance(n, Tag))
    for node in nodes:
        rem = parse_font_size(_style(node))
        if rem is None:
            continue
        direct = sum(
            len(str(child).strip())
            for child in node.children
            if isinstance(child, NavigableString)
        )
        weight = direct or len(node.get_text(strip=True))
        if weight <= 0:
            continue
        scored.append((weight, rem))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def font_sizes_compatible(
    a: float | None,
    b: float | None,
    *,
    ratio: float = FONT_SIZE_MERGE_RATIO,
) -> bool:
    """True when two sizes belong to the same content boundary."""
    if a is None or b is None:
        return True
    larger = max(a, b)
    if larger <= 0:
        return True
    return abs(a - b) / larger <= ratio


def group_by_compatible_font_size(tags: list[Tag]) -> list[list[Tag]]:
    """Split a left→right line into runs that share a similar font-size."""
    if not tags:
        return []
    groups: list[list[Tag]] = [[tags[0]]]
    current_size = dominant_font_size_rem(tags[0])
    for tag in tags[1:]:
        size = dominant_font_size_rem(tag)
        if font_sizes_compatible(current_size, size):
            groups[-1].append(tag)
            if current_size is None:
                current_size = size
        else:
            groups.append([tag])
            current_size = size
    return groups


def cluster_positioned_lines(
    tags: list[Tag],
    *,
    line_tolerance_pt: float = LINE_TOLERANCE_PT,
) -> list[list[Tag]]:
    """Group absolute-positioned tags into visual lines (top bands), left→right."""
    indexed: list[tuple[float, float, int, Tag]] = []
    for i, tag in enumerate(tags):
        pos = parse_position(tag)
        if pos is None:
            continue
        indexed.append((pos[0], pos[1], i, tag))
    indexed.sort(key=lambda t: (t[0], t[1], t[2]))

    lines: list[list[Tag]] = []
    band_top: float | None = None
    current: list[tuple[float, int, Tag]] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        current.sort(key=lambda t: (t[0], t[1]))
        lines.append([tag for _, _, tag in current])
        current = []

    for top, left, i, tag in indexed:
        if band_top is None or abs(top - band_top) > line_tolerance_pt:
            flush()
            band_top = top
        current.append((left, i, tag))
    flush()
    return lines


# Max vertical gap (pt) within one font-size content block before a new block.
STREAM_BLOCK_GAP_PT = 40.0
# How far ahead (pt) to look for a smaller-font stream beside the frontier.
FRONTIER_WINDOW_PT = 10.0


def _assign_font_stream_ids(
    sizes: list[float | None],
) -> list[int]:
    """Map each size to a stream id (compatible sizes share an id)."""
    reps: list[float | None] = []
    ids: list[int] = []
    for size in sizes:
        found: int | None = None
        for idx, rep in enumerate(reps):
            if font_sizes_compatible(rep, size):
                found = idx
                if rep is None and size is not None:
                    reps[idx] = size
                break
        if found is None:
            found = len(reps)
            reps.append(size)
        ids.append(found)
    return ids


def order_positioned_by_font_streams(tags: list[Tag]) -> list[Tag]:
    """Order positioned tags so font-size streams stay contiguous.

    When different font-sizes overlap vertically (e.g. marginal notes beside
    body text), emit the smaller-size stream block first, then the larger.
    Same-size fragments still follow top/left order within their block.
    """
    items: list[dict] = []
    for index, tag in enumerate(tags):
        pos = parse_position(tag)
        if pos is None:
            continue
        items.append(
            {
                "top": pos[0],
                "left": pos[1],
                "size": dominant_font_size_rem(tag),
                "tag": tag,
                "index": index,
            }
        )
    if len(items) < 2:
        return [item["tag"] for item in items]

    items.sort(key=lambda item: (item["top"], item["left"], item["index"]))
    stream_ids = _assign_font_stream_ids([item["size"] for item in items])
    for item, stream_id in zip(items, stream_ids):
        item["stream"] = stream_id

    # Representative size per stream (for "smaller first" when overlapping).
    stream_size: dict[int, float] = {}
    for item in items:
        size = item["size"]
        sid = item["stream"]
        if size is None:
            continue
        if sid not in stream_size or size < stream_size[sid]:
            stream_size[sid] = size

    used = [False] * len(items)
    ordered: list[Tag] = []

    while not all(used):
        frontier_top = min(
            item["top"] for item, is_used in zip(items, used) if not is_used
        )
        window = [
            i
            for i, item in enumerate(items)
            if not used[i] and item["top"] <= frontier_top + FRONTIER_WINDOW_PT
        ]
        # Prefer the smallest font among streams touching the frontier.
        pick_stream = min(
            window,
            key=lambda i: (
                stream_size.get(items[i]["stream"], 999.0),
                items[i]["left"],
                items[i]["index"],
            ),
        )
        stream = items[pick_stream]["stream"]

        # Emit a contiguous vertical block of this stream.
        block_indexes = [
            i
            for i, item in enumerate(items)
            if not used[i] and item["stream"] == stream
        ]
        block_indexes.sort(key=lambda i: (items[i]["top"], items[i]["left"]))

        # Start from the first unused tag of this stream at/after frontier.
        start = 0
        while (
            start < len(block_indexes)
            and items[block_indexes[start]]["top"] < frontier_top - FRONTIER_WINDOW_PT
        ):
            start += 1
        if start >= len(block_indexes):
            start = 0

        last_top = items[block_indexes[start]]["top"]
        # Tighter gaps for small type (marginal notes); body may span more.
        rep = stream_size.get(stream)
        if rep is not None:
            size_pt = rep * 12.0  # rem → approx pt
            max_gap = max(12.0, size_pt * 1.55)
        else:
            max_gap = STREAM_BLOCK_GAP_PT
        my_size = stream_size.get(stream, 999.0)

        block_tags: list[Tag] = []
        for pos in range(start, len(block_indexes)):
            idx = block_indexes[pos]
            top = items[idx]["top"]
            if pos > start:
                if top - last_top > max_gap:
                    break
                # Body must yield when a smaller-font note sits beside/near
                # the next fragment (notes can be a few pt below the body top).
                intervening_smaller = any(
                    (not used[k])
                    and items[k]["stream"] != stream
                    and stream_size.get(items[k]["stream"], 999.0) < my_size
                    and (last_top - FRONTIER_WINDOW_PT)
                    < items[k]["top"]
                    <= (top + FRONTIER_WINDOW_PT)
                    for k in range(len(items))
                )
                if intervening_smaller:
                    break
            block_tags.append(items[idx]["tag"])
            used[idx] = True
            last_top = top

        # Safety: always consume at least the picked item.
        if not used[pick_stream]:
            block_tags.append(items[pick_stream]["tag"])
            used[pick_stream] = True

        # Within a stream block, restore left→right on each visual line.
        for line in cluster_positioned_lines(block_tags):
            ordered.extend(line)

    return ordered


def iter_positioned_render_groups(tags: list[Tag]) -> list[list[Tag]]:
    """Stream-aware order, then same-line groups without global re-sort.

    Preserves font-size block order from ``order_positioned_by_font_streams``.
    Only joins neighbors that share a visual line and compatible font-size.
    """
    ordered = order_positioned_by_font_streams(tags)
    if not ordered:
        return []

    groups: list[list[Tag]] = []
    i = 0
    while i < len(ordered):
        line = [ordered[i]]
        pos_i = parse_position(ordered[i])
        j = i + 1
        while j < len(ordered):
            pos_j = parse_position(ordered[j])
            if (
                pos_i is not None
                and pos_j is not None
                and abs(pos_j[0] - pos_i[0]) <= LINE_TOLERANCE_PT
            ):
                line.append(ordered[j])
                j += 1
            else:
                break
        groups.extend(group_by_compatible_font_size(line))
        i = j
    return groups


def sort_positioned(tags: list[Tag]) -> list[Tag]:
    """Sort absolute-positioned tags into stream-aware reading order."""
    return order_positioned_by_font_streams(tags)


def is_page_number(text: str) -> bool:
    """True if text looks like a TOC page number (digits, optional roman)."""
    t = text.strip()
    if not t:
        return False
    if t.isdigit():
        return True
    # Lowercase roman numerals sometimes appear in front matter.
    return bool(re.fullmatch(r"[ivxlcdm]+", t, re.IGNORECASE))


def apply_text_transform(text: str, transform: str | None) -> str:
    """Apply a CSS-like text-transform to a plain text fragment."""
    if not transform or not text:
        return text
    if transform == "upper":
        return text.upper()
    if transform == "lower":
        return text.lower()
    if transform == "capitalize":
        return text.title()
    return text


def wrap_emphasis(
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    strike: bool = False,
    underline: bool = False,
) -> str:
    """Wrap rendered inline Markdown with emphasis markers."""
    if not text or not text.strip():
        return text
    leading = text[: len(text) - len(text.lstrip())]
    trailing = text[len(text.rstrip()) :]
    core = text.strip()
    if bold and italic:
        core = f"***{core}***"
    elif bold:
        core = f"**{core}**"
    elif italic:
        core = f"*{core}*"
    if strike:
        core = f"~~{core}~~"
    if underline:
        core = f"<u>{core}</u>"
    return f"{leading}{core}{trailing}"


def join_inline(parts: list[str]) -> str:
    """Join inline fragments, inserting a space when HTML omitted one."""
    out = ""
    for part in parts:
        if not part:
            continue
        if not out:
            out = part
            continue
        if out[-1].isspace() or part[0].isspace():
            out += part
            continue
        # Glue punctuation to the left; otherwise separate words/emphasis.
        if part[0] in ".,;:!?)]}%":
            out += part
        elif out[-1] in "([{/" :
            out += part
        else:
            out += " " + part
    return out


@dataclass(frozen=True)
class _LegacyRole:
    kind: str
    level: int = 0


def infer_role(el: Tag, rules: Sequence[Callable] | None = None) -> _LegacyRole | None:
    """Deprecated: prefer ``infer_style``."""
    del rules
    hint = infer_style(el)
    if hint is None:
        return None
    if hint.heading_level is not None:
        return _LegacyRole(kind="heading", level=hint.heading_level)
    if hint.has_inline_style:
        return _LegacyRole(kind="emphasis", level=0)
    return None
