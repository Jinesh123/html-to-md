# Project plan — HTML to Markdown converter

Living plan for building and extending this package. Update **Progress** and
**Open tasks** whenever work lands.

## Product intent (important)

This is a **general-purpose** HTML → Markdown converter — not a tool built for
one document type, one CMS, or the sample files in this repo.

| Principle | Meaning |
|-----------|---------|
| Tag-accurate | Semantic HTML (`h1`, `ul`, `table`, …) maps to correct GFM |
| Style-aware | Classes **and** inline CSS drive smart Markdown when tags are weak |
| Input-agnostic | Same rules apply to hand-written HTML, Tailwind pages, PDF→HTML, emails, etc. |
| Fixtures ≠ product | `page.html` / `testcase.html` are **regression samples** that reveal gaps; features must be general heuristics, not one-off hardcodes for those files |

When a fixture fails, extract the **general rule** (e.g. “parse `font-size` in
`pt`”, “merge elements that share a visual line via `top`/`left`”) and implement
that rule so any similar HTML benefits.

## Goals

1. Convert arbitrary HTML to correct GitHub-flavored Markdown.
2. Map common HTML tags to equivalent Markdown accurately.
3. Infer structure/emphasis from **styles and CSS properties** when markup is
   presentational (`font-size`, `font-weight`, utility classes, positioning, …).
4. Support skipping selected HTML tags (and their children), e.g. `img`,
   `footer`, `header`, `h1`.
5. Ship as a **pip-installable** Python package with both a **library API** and
   a **CLI**.

## Decisions (locked in)

| Choice | Decision |
|--------|----------|
| Stack | Python 3.10+, BeautifulSoup (`html.parser`) |
| Implementation | Own converter (not wrapping markdownify/html2text) |
| Markdown dialect | GitHub-flavored Markdown (GFM) |
| Interface | Library (`html_to_md.convert` / `Converter`) + CLI (`html2md`) |
| Smart mode | On by default; style/class heuristics; disable with `smart=False` / `--no-smart` |
| Default skips | Always drop `script`, `style`, `noscript`, `template` |
| User skips | Opt-in via `skip_tags` / `--skip` (case-insensitive; removes subtree) |
| Dist name | `html-to-md-converter` |
| Import / CLI | `html_to_md` / `html2md` |

## Pipeline

```text
HTML string
  → BeautifulSoup parse
  → prune skip tags (+ comments)
  → (smart) reorder absolute-positioned children by top/left
  → recursive walk
       → (smart) infer StyleHint from class / inline style / descendants
       → (smart) merge same visual line when many positioned siblings
       → tag handlers
  → Markdown string
```

## Layout

```text
pyproject.toml
README.md
plan.md
src/html_to_md/
  __init__.py      # convert(), Converter, Options
  options.py       # Options + ALWAYS_SKIP + smart
  escape.py        # Markdown escaping, whitespace, inline code
  smart.py         # general style/class → StyleHint + layout helpers
  converter.py     # parse, prune, walk, handlers, positioned-line merge
  cli.py           # html2md
tests/             # unit tests + optional local fixtures (not the product)
```

## Smart conversion — general capabilities

Capabilities are defined by **CSS/HTML signals**, not by document type.

| Signal | General behavior | Status |
|--------|------------------|--------|
| Semantic tags `h1`–`h6`, `ul`, `table`, … | Direct GFM mapping | Done |
| Utility / semantic **classes** (`text-2xl`, `font-bold`, `title`, …) | Heading / emphasis | Done |
| Inline **`font-size`** (`px`, `pt`, `rem`, `em`, `%`) | Size → heading level when bold | Done |
| Inline **`font-weight` / `font-style` / decorations** | Bold / italic / strike / underline | Done |
| **`text-transform`** | upper / lower / capitalize on text nodes | Done |
| Large bold size on **descendant** `span` (parent `p` plain) | Promote paragraph to heading | Done |
| Absolute **`top` / `left`** on siblings | Visual reading order | Done |
| Multiple positioned siblings on same line | Merge into one Markdown line (e.g. label + page #) | Done |
| Leading `1. ` in normal content | Do not force list-escape inside emphasis | Done |
| Colors / alignment / background | No clean GFM; optional keep-as-HTML later | Open |
| `<style>` stylesheet rules resolved onto classes | Compute effective size/weight from CSS | Open |
| Relative size vs document body average | Heading without absolute thresholds only | Open |
| `ol type`, `details`/`summary`, rich tables | Tag/CSS follow-ups | Open |

## Progress

### Done — core package

- [x] Pip-installable package + `html2md` CLI
- [x] Tag handlers for common GFM constructs
- [x] Skip-tags API/CLI
- [x] Library API: `convert()`, `Converter`, `Options`

### Done — style-aware smart conversion

- [x] `StyleHint` + `infer_style` (classes + inline styles)
- [x] Size hierarchy from utility classes and normalized font-size
- [x] Emphasis from weight/italic/strike/underline (class + style)
- [x] Text transforms
- [x] Descendant bold+size → heading (presentational title pattern)
- [x] Font-size units: `px`, **`pt`**, `rem`, `em`, `%`
- [x] Absolute layout: sort by `top`/`left` with line clustering
- [x] Same-line merge for positioned siblings (TOC-like and any side-by-side text)
- [x] Safer escaping (don’t turn real `1. Title` labels into `\1.`)
- [x] Suppress redundant `**` when already emitting a heading
- [x] Inline join inserts missing spaces between adjacent fragments
- [x] **65 tests passing**

### Regression samples (not product scope)

Local files used to **discover** general rules and prevent regressions:

| File | What it exercises |
|------|-------------------|
| `testcase.html` | Broad tag + class + inline-style matrix |
| `page.html` | Presentational HTML (absolute layout, `pt` sizes, same-line columns) |

Do **not** add features that only work for these files. Prefer heuristics that
apply to any HTML with the same signals.

### Testcase matrix (signal coverage)

| Signal area | Status |
|-------------|--------|
| Semantic headings / lists / tables / links / code | Done |
| Font size → heading (class + inline) | Done |
| Font weight / italic / underline / strike | Done |
| Text transforms (upper/lower/capitalize) | Done (`small-caps` open) |
| Nested + combined styles | Done |
| Colors | Open (GFM limit → optional HTML keep) |
| Alignment | Open (GFM limit → optional HTML keep) |
| Background / border / highlight | Open |
| Stylesheet (`<style>`) resolution | Open |
| `ol type="A"`, `details`/`summary` | Open |

## Open tasks

### High priority (general style engine)

- [ ] **Stylesheet resolution** — parse `<style>` / linked rules enough to apply
      `font-size` / `font-weight` / `font-style` from class selectors (not only
      hard-coded class name maps).
- [ ] **Relative typography** — detect headings from size relative to surrounding
      body text, not only absolute rem thresholds.
- [ ] **Decorative CSS → optional HTML** — when Markdown cannot express color /
      align / background, optionally keep a compact styled `<span>`/`<div>`
      (configurable).
- [ ] **Indent / left-position hierarchy** — use horizontal position or margin
      as a general outline signal (sections vs items), not TOC-specific logic.

### Medium priority

- [ ] Honor `ol[type]` (`A`/`a`/`I`/`i`)
- [ ] Better `details`/`summary` mapping
- [ ] Table `colspan`/`rowspan` / alignment from style
- [ ] Richer skip: CSS selector / class / id; unwrap vs drop
- [ ] Snapshot tests for fixtures in CI (still as regressions, not the spec)

### Packaging / quality

- [ ] LICENSE, CHANGELOG, CI, PyPI publish
- [ ] `py.typed`, mypy, ruff

## How to work on this repo

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
html2md path/to/any.html -o out.md --skip img,footer,header
```

```python
from html_to_md import convert

# Works on any HTML; smart mode uses tags + classes + inline CSS
print(convert(html, skip_tags=["footer"], smart=True))
```

When fixing a bad conversion:

1. Identify the **HTML/CSS signal** that was misread.
2. Add/adjust a **general** rule in `smart.py` / `converter.py`.
3. Add a **minimal unit test** for that signal (fixture pages optional).
4. Update this plan’s Progress / Open tasks.

## Version log

| Version | Notes |
|---------|--------|
| 0.1.0 | Core converter, skip tags, library + CLI |
| 0.1.0+ | Style-aware smart mode: classes, inline CSS, layout merge, pt sizes |
