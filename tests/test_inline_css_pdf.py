"""Tests for PDF→HTML inline CSS (pt sizes, absolute positioning, TOC lines)."""

from pathlib import Path

from html_to_md import convert
from html_to_md.smart import font_size_to_rem, parse_font_size

ROOT = Path(__file__).resolve().parents[1]


SAMPLE_FORM = """
<div id="page0" style="width:612.0pt;height:792.0pt">
    <p style="top:130.4pt;left:68.8pt;line-height:16.1pt"><b><span
                style="font-family:Arial,sans-serif;font-size:16.1pt;color:#000000">Superintendent</span></b><span
            style="font-family:Arial,sans-serif;font-size:10.7pt;color:#000000"> (Clause 1) </span></p>
    <p style="top:152.3pt;left:76.5pt;line-height:9.8pt"><b><span
                style="font-family:Arial,sans-serif;font-size:9.8pt;color:#222222">NAME</span></b></p>
    <p style="top:254.0pt;left:76.5pt;line-height:10.7pt"><span
            style="font-family:Arial,sans-serif;font-size:10.7pt;color:#000000">(a)</span><b><span
                style="font-family:Arial,sans-serif;font-size:9.9pt;color:#222222"> DATE NOMINATED</span></b></p>
    <p style="top:133.9pt;left:45.9pt;line-height:10.7pt"><span
            style="font-family:Arial,sans-serif;font-size:10.7pt;color:#000000">5.</span></p>
</div>
"""

SAMPLE_TOC = """
<div id="page0" style="width:612.0pt;height:792.0pt">
    <p style="top:107.6pt;left:99.4pt"><b><span style="font-size:9.2pt">Schedule 1</span></b></p>
    <p style="top:107.1pt;left:468.9pt"><span style="font-size:10.7pt">1</span></p>
    <p style="top:123.7pt;left:114.8pt"><b><span style="font-size:9.2pt">Date</span></b></p>
    <p style="top:122.4pt;left:468.9pt"><span style="font-size:10.7pt">1</span></p>
    <p style="top:490.9pt;left:114.8pt"><b><span style="font-size:9.2pt">1. Interpretation</span></b></p>
    <p style="top:489.6pt;left:468.9pt"><span style="font-size:10.7pt">8</span></p>
</div>
"""


def test_pt_font_size_parsed():
    rem = parse_font_size("font-family:Arial;font-size:16.1pt;color:#000")
    assert rem is not None
    assert abs(rem - font_size_to_rem(16.1, "pt")) < 1e-6
    assert rem >= 1.25  # heading-eligible


def test_pt_bold_span_becomes_heading():
    html = (
        '<p><b><span style="font-size:16.1pt">Superintendent</span></b>'
        '<span style="font-size:10.7pt"> (Clause 1) </span></p>'
    )
    result = convert(html).strip()
    assert result.startswith("## ")
    assert "Superintendent" in result
    assert "(Clause 1)" in result
    assert not result.startswith("## **")


def test_small_bold_label_not_heading():
    html = '<p><b><span style="font-size:9.8pt">NAME</span></b></p>'
    assert convert(html).strip() == "**NAME**"


def test_space_between_marker_and_bold():
    html = (
        '<p><span style="font-size:10.7pt">(a)</span>'
        '<b><span style="font-size:9.9pt">DATE NOMINATED</span></b></p>'
    )
    assert convert(html).strip() == "(a) **DATE NOMINATED**"


def test_reading_order_puts_item_number_before_title():
    result = convert(SAMPLE_FORM)
    idx_num = result.find("5.")
    idx_title = result.find("Superintendent")
    assert idx_num != -1 and idx_title != -1
    assert idx_num < idx_title


def test_toc_merges_title_and_page_number():
    result = convert(SAMPLE_TOC)
    assert "**Schedule 1** 1" in result
    assert "**Date** 1" in result
    assert "**1. Interpretation** 8" in result
    # Not split across blank lines
    assert "**Schedule 1**\n\n1" not in result


def test_numbered_toc_entry_not_backslash_escaped():
    html = '<p><b><span style="font-size:9.2pt">1. Interpretation</span></b></p>'
    assert convert(html).strip() == "**1. Interpretation**"


def test_different_font_sizes_on_same_line_not_merged():
    """Font-size gap = content boundary; do not merge into one MD line."""
    html = """
    <div style="width:612pt;height:792pt">
      <p style="top:625.2pt;left:53.5pt"><i><span style="font-size:7.6pt">When given and </span></i></p>
      <p style="top:624.3pt;left:139.2pt"><span style="font-size:10.7pt">31.1</span></p>
      <p style="top:623.5pt;left:169.8pt"><span style="font-size:10.7pt">A notice is deemed given</span></p>
    </div>
    """
    result = convert(html)
    assert "*When given and*" in result
    assert "31.1 A notice is deemed given" in result
    # Marginal note must not be glued onto the body clause line
    assert "*When given and* 31.1" not in result


def test_marginal_note_block_stays_together_before_body():
    """Multi-line smaller-font notes emit as one block, then body clause."""
    html = """
    <div style="width:612pt;height:792pt">
      <p style="top:625.2pt;left:53.5pt"><i><span style="font-size:7.6pt">When given and </span></i></p>
      <p style="top:632.1pt;left:53.5pt"><i><span style="font-size:7.6pt">received</span></i></p>
      <p style="top:642.0pt;left:53.5pt"><i><span style="font-size:7.6pt">Refer to Items 2 and 3 </span></i></p>
      <p style="top:649.7pt;left:53.5pt"><i><span style="font-size:7.6pt">of Schedule 1.</span></i></p>
      <p style="top:624.3pt;left:139.2pt"><span style="font-size:10.7pt">31.1</span></p>
      <p style="top:623.5pt;left:169.8pt"><span style="font-size:10.7pt">A notice (and other documents) is deemed to have been given and </span></p>
      <p style="top:635.8pt;left:169.8pt"><span style="font-size:10.7pt">received:</span></p>
    </div>
    """
    result = convert(html)
    note_start = result.index("*When given and*")
    received_note = result.index("*received*")
    refer = result.index("*Refer to Items 2 and 3*")
    schedule = result.index("*of Schedule 1.*")
    body = result.index("31.1 A notice")
    assert note_start < received_note < refer < schedule < body
    assert result.index("received:") > body


def test_page_html_clause_fixture():
    html = (ROOT / "page.html").read_text(encoding="utf-8")
    result = convert(html)
    assert "## 31. Service of Notices" in result
    assert "31.1 A notice (and other documents) is deemed to have been given and" in result
    assert "*When given and*" in result
    assert "*When given and* 31.1" not in result
    # Notes stay together before the clause body
    assert result.index("*When given and*") < result.index("*of Schedule 1.*")
    assert result.index("*of Schedule 1.*") < result.index("31.1 A notice")
    assert "*Cooperation* 30.9" not in result
    assert "30.9 The parties must cooperate with the **expert**." in result
    assert result.index("*Cooperation*") < result.index("30.9 The parties")
