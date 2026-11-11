# html-to-md-converter

Convert HTML to GitHub-flavored Markdown from Python or the command line.
Optionally skip tags (and their children) such as `img`, `footer`, `header`, or `h1`.

## Install

```bash
pip install .
# or editable:
pip install -e ".[dev]"
```

## Library

```python
from html_to_md import convert

html = "<h1>Title</h1><p>Hello <strong>world</strong>.</p>"
md = convert(html)
# # Title
#
# Hello **world**.

md = convert(html, skip_tags=["img", "footer", "header", "h1"])
```

**Smart conversion** (on by default) infers Markdown roles from classes and
styles — for example a Tailwind-styled paragraph becomes a heading:

```html
<p class="text-2xl font-bold">Hello World</p>
```

```markdown
# Hello World
```

Pass `smart=False` (or CLI `--no-smart`) to disable. New heuristics live in
`html_to_md.smart` and can be extended as more patterns show up.

`script`, `style`, `noscript`, and `template` are always removed. Passing
`skip_tags` adds more tags on top of that set.

Reusable converter:

```python
from html_to_md import Converter

converter = Converter(skip_tags=["footer", "nav"])
print(converter.convert("<p>Hi</p><footer>bye</footer>"))
```

## CLI

```bash
html2md page.html -o page.md --skip img,footer,header,h1
html2md --skip img --skip footer < page.html
```

| Flag | Meaning |
|------|---------|
| `input` | HTML file (stdin if omitted) |
| `-o` / `--output` | Markdown file (stdout if omitted) |
| `--skip` | Comma-separated tags to drop; repeatable |
| `--no-smart` | Disable class/style role inference |

## Tag mapping

| HTML | Markdown |
|------|----------|
| `h1`–`h6` | ATX headings (`#` … `######`) |
| `p` | Paragraph |
| `br` | Hard break (`  \\n`) |
| `hr` | `---` |
| `blockquote` | `>` quoted lines |
| `strong` / `b` | `**bold**` |
| `em` / `i` | `*italic*` |
| `del` / `s` / `strike` | `~~strike~~` |
| `code` | Inline code |
| `pre` / `pre > code` | Fenced code block (language from `language-*`, `lang-*`, or `data-lang`) |
| `a` | `[text](href)` |
| `img` | `![alt](src)` |
| `ul` / `ol` / `li` | Lists (nested, indented) |
| `table` / `tr` / `th` / `td` | GFM pipe tables |
| `dl` / `dt` / `dd` | `**term**` plus definition |
| `q` | `"quoted"` |
| `figure` / `figcaption` | Content plus italic caption |
| `div`, `span`, `section`, … | Unwrapped (children kept) |
| `sub`, `sup`, `kbd`, `abbr`, `mark` | Kept as HTML snippets |

**Limits:** `colspan` / `rowspan` are flattened into cell text; complex nested
tables may need manual cleanup.

## Development

```bash
pip install -e ".[dev]"
pytest
```
