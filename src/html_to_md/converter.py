"""HTML to Markdown converter."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Iterable

from bs4 import BeautifulSoup, Comment, NavigableString, PageElement, Tag

from html_to_md.escape import escape_cell, escape_text, wrap_inline_code
from html_to_md.options import Options
from html_to_md.smart import (
    StyleHint,
    apply_text_transform,
    cluster_positioned_lines,
    infer_style,
    is_page_number,
    join_inline,
    parse_position,
    sort_positioned,
    wrap_emphasis,
)

# Structural tags with no Markdown meaning — unwrap children.
UNWRAP_TAGS: frozenset[str] = frozenset(
    {
        "html",
        "body",
        "div",
        "span",
        "section",
        "article",
        "main",
        "nav",
        "header",
        "footer",
        "aside",
        "center",
        "font",
        "form",
        "label",
        "fieldset",
        "legend",
        "details",
        "summary",
        "dialog",
        "picture",
        "source",
        "time",
        "data",
        "address",
        "small",
        "ins",
        "wbr",
    }
)

# Tags kept as short HTML snippets (no clean Markdown equivalent).
RAW_HTML_TAGS: frozenset[str] = frozenset(
    {"sub", "sup", "kbd", "abbr", "mark", "var", "samp"}
)

_LANGUAGE_CLASS = re.compile(
    r"(?:language|lang)-([A-Za-z0-9_+-]+)", re.IGNORECASE
)


class Converter:
    """Convert HTML documents or fragments to GitHub-flavored Markdown."""

    def __init__(
        self,
        *,
        skip_tags: Iterable[str] | None = None,
        bullet: str = "-",
        fence: str = "```",
        smart: bool = True,
        options: Options | None = None,
    ) -> None:
        if options is not None:
            self.options = options
        else:
            self.options = Options.from_skip_tags(
                skip_tags, bullet=bullet, fence=fence, smart=smart
            )
        # Stack of text-transform names applied to descendant text nodes.
        self._transforms: list[str] = []
        # When rendering a smart heading, bold is implied by `#` — don't emit `**`.
        self._suppress_bold: int = 0

    def convert(self, html: str) -> str:
        """Parse ``html``, prune skipped tags, and return Markdown."""
        soup = BeautifulSoup(html, "html.parser")
        self._prune(soup)
        # Prefer body content when a full document was parsed.
        root: PageElement = soup.body if soup.body is not None else soup
        if self.options.smart and isinstance(root, Tag):
            self._reorder_positioned(root)
        parts = self._render_children(root, block=True)
        return self._join_blocks(parts).strip() + ("\n" if parts else "")

    # ------------------------------------------------------------------
    # Pruning / layout
    # ------------------------------------------------------------------

    def _prune(self, soup: BeautifulSoup) -> None:
        for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
            comment.extract()

        skip = self.options.skip_tags
        for tag in soup.find_all(True):
            if isinstance(tag, Tag) and tag.name and tag.name.lower() in skip:
                tag.decompose()

    def _reorder_positioned(self, root: Tag) -> None:
        """Reorder absolute-positioned children into visual reading order.

        PDF→HTML often emits item numbers after the body text in DOM order
        while ``top``/``left`` place them beside section titles.
        """
        # Process deepest containers first so nested layouts stay consistent.
        containers = [root, *root.find_all(True)]
        for container in reversed(containers):
            if not isinstance(container, Tag):
                continue
            children = [c for c in container.children if isinstance(c, Tag)]
            positioned = [c for c in children if parse_position(c) is not None]
            if len(positioned) < 2:
                continue
            ordered = sort_positioned(positioned)
            for tag in ordered:
                tag.extract()
            # Insert after any leading non-tag nodes (whitespace).
            insert_at = 0
            contents = list(container.contents)
            for i, node in enumerate(contents):
                if isinstance(node, Tag):
                    insert_at = i
                    break
                insert_at = i + 1
            for offset, tag in enumerate(ordered):
                container.insert(insert_at + offset, tag)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_children(
        self, parent: PageElement, *, block: bool = False
    ) -> list[str]:
        parts: list[str] = []
        if not isinstance(parent, Tag):
            return parts

        if (
            block
            and self.options.smart
            and self._should_merge_positioned_lines(parent)
        ):
            return self._render_positioned_lines(parent)

        for child in parent.children:
            rendered = self._render(child, block=block)
            if rendered:
                parts.append(rendered)
        return parts

    def _should_merge_positioned_lines(self, parent: Tag) -> bool:
        tags = [c for c in parent.children if isinstance(c, Tag)]
        positioned = [c for c in tags if parse_position(c) is not None]
        # PDF page containers: most/all block children are absolutely positioned.
        return len(positioned) >= 2 and len(positioned) >= len(tags) * 0.8

    def _render_positioned_lines(self, parent: Tag) -> list[str]:
        """Merge same-line absolute elements (e.g. TOC title + page number)."""
        tags = [
            c
            for c in parent.children
            if isinstance(c, Tag) and parse_position(c) is not None
        ]
        parts: list[str] = []
        for line in cluster_positioned_lines(tags):
            bits: list[str] = []
            for tag in line:
                rendered = self._render(tag, block=True)
                if not rendered:
                    continue
                # Each positioned <p> is one fragment on the visual line.
                bits.append(" ".join(rendered.split()))
            if not bits:
                continue
            parts.append(self._format_positioned_line(bits))
        return parts

    def _format_positioned_line(self, bits: list[str]) -> str:
        if len(bits) == 1:
            return bits[0]
        # TOC pattern: label(s) on the left, page number on the right.
        if is_page_number(bits[-1]):
            title = join_inline(bits[:-1]).strip()
            page = bits[-1].strip()
            if title:
                return f"{title} {page}"
            return page
        return join_inline(bits)

    def _render(self, el: PageElement, *, block: bool = False) -> str:
        if isinstance(el, Comment):
            return ""
        if isinstance(el, NavigableString):
            text = str(el)
            if not text:
                return ""
            if block:
                # In block context, pure whitespace between tags is noise.
                if text.strip() == "":
                    return ""
            for transform in self._transforms:
                text = apply_text_transform(text, transform)
            return escape_text(text, collapse=True)

        if not isinstance(el, Tag):
            return ""

        if self.options.smart:
            hint = infer_style(el)
            if hint is not None:
                return self._render_with_hint(el, hint, block=block)

        return self._render_tag(el, block=block)

    def _render_tag(self, el: Tag, *, block: bool = False) -> str:
        name = (el.name or "").lower()
        handler = self._handlers.get(name)
        if handler is not None:
            return handler(self, el)

        if name in RAW_HTML_TAGS:
            return self._raw_html(el)

        if name in UNWRAP_TAGS or name == "figure":
            return self._unwrap(el, block=block)

        # Unknown tag: unwrap children to preserve text.
        return self._unwrap(el, block=block)

    def _render_with_hint(
        self, el: Tag, hint: StyleHint, *, block: bool = False
    ) -> str:
        pushed = False
        if hint.transform:
            self._transforms.append(hint.transform)
            pushed = True
        try:
            if hint.heading_level is not None:
                self._suppress_bold += 1
                try:
                    text = self._heading_level(el, hint.heading_level)
                finally:
                    self._suppress_bold -= 1
            else:
                # Prefer normal tag handler (p → paragraph) then wrap.
                name = (el.name or "").lower()
                if name == "p":
                    text = self._paragraph(el)
                elif name in UNWRAP_TAGS or name == "span":
                    text = self._unwrap(el, block=block)
                else:
                    text = self._render_tag(el, block=block)

            if hint.heading_level is not None:
                # Emphasis inside heading markers: "# **text**" looks odd;
                # wrap only the title text portion.
                if hint.italic or hint.strike or hint.underline:
                    hashes, _, title = text.partition(" ")
                    wrapped = wrap_emphasis(
                        title,
                        italic=hint.italic,
                        strike=hint.strike,
                        underline=hint.underline,
                    )
                    text = f"{hashes} {wrapped}" if title else hashes
                return text

            return wrap_emphasis(
                text,
                bold=hint.bold,
                italic=hint.italic,
                strike=hint.strike,
                underline=hint.underline,
            )
        finally:
            if pushed:
                self._transforms.pop()

    def _unwrap(self, el: Tag, *, block: bool = False) -> str:
        parts = self._render_children(el, block=block)
        if block:
            return self._join_blocks(parts)
        return join_inline(parts)

    def _inline(self, el: Tag) -> str:
        parts = [
            self._render(c, block=False)
            for c in el.children
        ]
        return join_inline([p for p in parts if p])

    def _raw_html(self, el: Tag) -> str:
        # Preserve a compact HTML snippet for tags without Markdown equivalents.
        attr_parts: list[str] = []
        for k, v in el.attrs.items():
            if isinstance(v, list):
                attr_parts.append(f' {k}="{" ".join(v)}"')
            elif v is True or v is None:
                attr_parts.append(f" {k}")
            else:
                attr_parts.append(f' {k}="{v}"')
        attrs = "".join(attr_parts)
        children_md = "".join(self._render(c, block=False) for c in el.children)
        return f"<{el.name}{attrs}>{children_md}</{el.name}>"

    def _join_blocks(self, parts: list[str]) -> str:
        cleaned = [p.strip("\n") for p in parts if p and p.strip()]
        return "\n\n".join(cleaned)

    # ------------------------------------------------------------------
    # Tag handlers
    # ------------------------------------------------------------------

    def _heading(self, el: Tag) -> str:
        level = int(el.name[1])
        return self._heading_level(el, level)

    def _heading_level(self, el: Tag, level: int) -> str:
        level = max(1, min(6, level))
        text = self._inline(el).strip()
        if not text:
            return ""
        return f'{"#" * level} {text}'

    def _paragraph(self, el: Tag) -> str:
        text = self._inline(el).strip()
        return text

    def _br(self, el: Tag) -> str:
        return "  \n"

    def _hr(self, el: Tag) -> str:
        return "---"

    def _strong(self, el: Tag) -> str:
        text = self._inline(el)
        if not text.strip():
            return text
        if self._suppress_bold:
            return text
        return f"**{text.strip()}**"

    def _em(self, el: Tag) -> str:
        text = self._inline(el)
        if not text.strip():
            return text
        return f"*{text.strip()}*"

    def _del(self, el: Tag) -> str:
        text = self._inline(el)
        if not text.strip():
            return text
        return f"~~{text.strip()}~~"

    def _underline(self, el: Tag) -> str:
        text = self._inline(el)
        if not text.strip():
            return text
        return f"<u>{text.strip()}</u>"

    def _code(self, el: Tag) -> str:
        # If inside a pre, the pre handler takes care of fencing.
        if el.parent and isinstance(el.parent, Tag) and el.parent.name == "pre":
            return el.get_text()
        code = el.get_text()
        return wrap_inline_code(code)

    def _pre(self, el: Tag) -> str:
        code_el = el.find("code")
        language = ""
        if code_el and isinstance(code_el, Tag):
            language = self._extract_language(code_el)
            code = code_el.get_text()
        else:
            language = self._extract_language(el)
            code = el.get_text()

        # Strip a single trailing newline for cleaner fences.
        if code.endswith("\n"):
            code = code[:-1]

        fence = self.options.fence
        # Grow fence if code contains the fence marker.
        while fence in code:
            fence += "`"

        info = language
        return f"{fence}{info}\n{code}\n{fence}"

    def _extract_language(self, el: Tag) -> str:
        data_lang = el.get("data-lang") or el.get("data-language")
        if isinstance(data_lang, str) and data_lang.strip():
            return data_lang.strip()

        classes = el.get("class") or []
        if isinstance(classes, str):
            classes = classes.split()
        for cls in classes:
            match = _LANGUAGE_CLASS.search(cls)
            if match:
                return match.group(1)
        return ""

    def _anchor(self, el: Tag) -> str:
        href = el.get("href")
        text = self._inline(el).strip()
        if not href or not isinstance(href, str):
            return text
        # Drop empty links (e.g. image-only anchors when img is skipped).
        if not text:
            return ""
        title = el.get("title")
        if isinstance(title, str) and title:
            escaped_title = title.replace('"', '\\"')
            return f'[{text}]({href} "{escaped_title}")'
        return f"[{text}]({href})"

    def _img(self, el: Tag) -> str:
        src = el.get("src")
        alt = el.get("alt") or ""
        if not isinstance(alt, str):
            alt = ""
        title = el.get("title")
        if not src or not isinstance(src, str):
            return alt
        if isinstance(title, str) and title:
            escaped_title = title.replace('"', '\\"')
            return f'![{alt}]({src} "{escaped_title}")'
        return f"![{alt}]({src})"

    def _blockquote(self, el: Tag) -> str:
        inner = self._join_blocks(self._render_children(el, block=True))
        if not inner.strip():
            return ""
        lines = inner.split("\n")
        return "\n".join(f"> {line}" if line else ">" for line in lines)

    def _list(self, el: Tag) -> str:
        ordered = el.name.lower() == "ol"
        start_attr = el.get("start")
        try:
            index = int(start_attr) if start_attr else 1
        except (TypeError, ValueError):
            index = 1

        items: list[str] = []
        for child in el.children:
            if not isinstance(child, Tag) or child.name.lower() != "li":
                continue
            items.append(self._list_item(child, ordered=ordered, index=index))
            index += 1

        return "\n".join(items)

    def _list_item(
        self, el: Tag, *, ordered: bool, index: int
    ) -> str:
        marker = f"{index}." if ordered else self.options.bullet

        # Separate block children (nested lists, paragraphs) from inline.
        blocks: list[str] = []
        inline_parts: list[str] = []

        # Track which block indexes are already-indented nested lists.
        nested_list_indexes: set[int] = set()

        for child in el.children:
            if isinstance(child, NavigableString):
                text = str(child)
                for transform in self._transforms:
                    text = apply_text_transform(text, transform)
                text = escape_text(text, collapse=True)
                if text.strip() or inline_parts:
                    # Preserve trailing/leading spaces between inline pieces.
                    if text.strip():
                        inline_parts.append(text)
                    elif inline_parts and not inline_parts[-1].endswith(" "):
                        inline_parts.append(" ")
                continue

            if not isinstance(child, Tag):
                continue

            name = child.name.lower()
            if name in {"ul", "ol"}:
                if inline_parts:
                    blocks.append("".join(inline_parts).strip())
                    inline_parts = []
                nested = self._list(child)
                indented = "\n".join(
                    f"    {line}" if line else "" for line in nested.split("\n")
                )
                nested_list_indexes.add(len(blocks))
                blocks.append(indented)
            elif name in {
                "p",
                "blockquote",
                "pre",
                "table",
                "hr",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "dl",
            }:
                if inline_parts:
                    blocks.append("".join(inline_parts).strip())
                    inline_parts = []
                rendered = self._render(child, block=True)
                if rendered:
                    lines = rendered.split("\n")
                    indented_lines = [lines[0]] + [
                        f"    {line}" if line else "" for line in lines[1:]
                    ]
                    blocks.append("\n".join(indented_lines))
            else:
                rendered = self._render(child, block=False)
                if rendered:
                    inline_parts.append(rendered)

        if inline_parts:
            blocks.append("".join(inline_parts).strip())

        if not blocks:
            return f"{marker} "

        first = blocks[0]
        if len(blocks) == 1:
            return f"{marker} {first}"

        # Nested list after a label stays tight (no blank line, no re-indent).
        if len(blocks) == 2 and 1 in nested_list_indexes:
            return f"{marker} {first}\n{blocks[1]}"

        rest = []
        for idx, block in enumerate(blocks[1:], start=1):
            if idx in nested_list_indexes:
                rest.append(block)
            else:
                indented = "\n".join(
                    f"    {line}" if line else "" for line in block.split("\n")
                )
                rest.append(indented)
        return f"{marker} {first}\n\n" + "\n\n".join(rest)

    def _table(self, el: Tag) -> str:
        rows: list[list[str]] = []
        header_count: int | None = None

        thead = el.find("thead", recursive=False)
        if thead and isinstance(thead, Tag):
            for tr in thead.find_all("tr", recursive=False):
                row = self._table_row(tr)
                if row:
                    rows.append(row)
                    header_count = len(row)

        bodies = el.find_all("tbody", recursive=False)
        if bodies:
            for tbody in bodies:
                if not isinstance(tbody, Tag):
                    continue
                for tr in tbody.find_all("tr", recursive=False):
                    row = self._table_row(tr)
                    if row:
                        rows.append(row)
        else:
            # Rows directly under table (or via tfoot ignored for simplicity).
            for tr in el.find_all("tr", recursive=False):
                row = self._table_row(tr)
                if row:
                    rows.append(row)

            # Also pick up tr nested only under table without tbody
            # (html.parser may leave them as direct children already handled).
            if not rows:
                for tr in el.find_all("tr"):
                    # Skip ones already inside thead handled above.
                    if thead and tr.parent == thead:
                        continue
                    row = self._table_row(tr)
                    if row:
                        rows.append(row)

        if not rows:
            return ""

        # If no thead, treat first row as header.
        if header_count is None:
            header_count = len(rows[0])

        # Normalize column count.
        width = max(len(r) for r in rows)
        normalized = [r + [""] * (width - len(r)) for r in rows]

        header = normalized[0]
        body = normalized[1:]
        sep = ["---"] * width

        def fmt(row: list[str]) -> str:
            return "| " + " | ".join(row) + " |"

        lines = [fmt(header), fmt(sep)]
        lines.extend(fmt(r) for r in body)
        return "\n".join(lines)

    def _table_row(self, tr: Tag) -> list[str]:
        cells: list[str] = []
        for cell in tr.children:
            if not isinstance(cell, Tag):
                continue
            if cell.name.lower() not in {"td", "th"}:
                continue
            text = escape_cell(self._inline(cell))
            # Flatten colspan into repeated empty cells after content? Plan says
            # flatten colspan/rowspan into the cell text — keep single cell.
            cells.append(text)
        return cells

    def _dl(self, el: Tag) -> str:
        parts: list[str] = []
        current_terms: list[str] = []
        for child in el.children:
            if not isinstance(child, Tag):
                continue
            name = child.name.lower()
            if name == "dt":
                current_terms.append(f"**{self._inline(child).strip()}**")
            elif name == "dd":
                definition = self._inline(child).strip()
                if current_terms:
                    parts.append("\n".join(current_terms))
                    current_terms = []
                if definition:
                    parts.append(definition)
        if current_terms:
            parts.append("\n".join(current_terms))
        return self._join_blocks(parts)

    def _q(self, el: Tag) -> str:
        text = self._inline(el)
        return f'"{text}"'

    def _figure(self, el: Tag) -> str:
        caption_el = el.find("figcaption")
        caption = ""
        if caption_el and isinstance(caption_el, Tag):
            caption = self._inline(caption_el).strip()
            caption_el.extract()

        content = self._join_blocks(self._render_children(el, block=True))
        if caption:
            if content:
                return f"{content}\n\n*{caption}*"
            return f"*{caption}*"
        return content

    # Handler dispatch table (bound methods looked up by tag name).
    _handlers: dict[str, Callable[["Converter", Tag], str]] = {}


# Bind handlers after class body so methods exist.
Converter._handlers = {
    "h1": Converter._heading,
    "h2": Converter._heading,
    "h3": Converter._heading,
    "h4": Converter._heading,
    "h5": Converter._heading,
    "h6": Converter._heading,
    "p": Converter._paragraph,
    "br": Converter._br,
    "hr": Converter._hr,
    "strong": Converter._strong,
    "b": Converter._strong,
    "em": Converter._em,
    "i": Converter._em,
    "del": Converter._del,
    "s": Converter._del,
    "strike": Converter._del,
    "u": Converter._underline,
    "code": Converter._code,
    "pre": Converter._pre,
    "a": Converter._anchor,
    "img": Converter._img,
    "blockquote": Converter._blockquote,
    "ul": Converter._list,
    "ol": Converter._list,
    "table": Converter._table,
    "dl": Converter._dl,
    "q": Converter._q,
    "figure": Converter._figure,
}
