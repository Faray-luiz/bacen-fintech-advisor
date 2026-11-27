"""Google Material Design 3 executive PDF generator for Bacen Fintech Advisor outputs.

Converts any Markdown response from the multi-agent pipeline into a clean, print-ready A4
PDF featuring:

* Google-inspired visual identity (4-color top accent rule, Google Blue ``#1A73E8`` headers,
  generous whitespace, crisp hairline tables with repeating headers across page breaks);
* Full UTF-8 Portuguese typography via system TrueType fonts (Roboto -> DejaVuSans ->
  LiberationSans -> built-in Helvetica fallback) with emoji sanitization so tofu boxes never
  appear;
* Two-pass ``Page X de Y`` footer with official BCB & Open Finance source attribution;
* Mandatory PII scrubbing (:func:`bacen_advisor.pii.redact_regex`) prior to PDF rendering.
"""

from __future__ import annotations

import datetime as dt
import html
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, StyleSheet1
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from bacen_advisor.pii import redact_regex

# --------------------------------------------------------------------------------------
# Google Material Design 3 Color Palette
# --------------------------------------------------------------------------------------

GOOGLE_BLUE = colors.HexColor("#1A73E8")
GOOGLE_BLUE_DARK = colors.HexColor("#174EA6")
GOOGLE_BLUE_TINT = colors.HexColor("#E8F0FE")
GOOGLE_SURFACE_ALT = colors.HexColor("#F8F9FA")
GOOGLE_SURFACE_CALLOUT = colors.HexColor("#F0F4F9")
GOOGLE_RED = colors.HexColor("#EA4335")
GOOGLE_YELLOW = colors.HexColor("#FBBC04")
GOOGLE_GREEN = colors.HexColor("#34A853")
GOOGLE_GREEN_TEXT = colors.HexColor("#137333")
GOOGLE_GREEN_TINT = colors.HexColor("#E6F4EA")
GOOGLE_AMBER_TEXT = colors.HexColor("#B06000")
GOOGLE_AMBER_TINT = colors.HexColor("#FEF7E0")
TEXT_PRIMARY = colors.HexColor("#1F1F1F")
TEXT_BODY = colors.HexColor("#3C4043")
TEXT_MUTED = colors.HexColor("#5F6368")
BORDER_SUBTLE = colors.HexColor("#E0E3E7")
BORDER_MEDIUM = colors.HexColor("#DADCE0")

# --------------------------------------------------------------------------------------
# Font discovery & registration (UTF-8 Portuguese safe)
# --------------------------------------------------------------------------------------

_FONT_CANDIDATES: list[dict[str, Any]] = [
    {
        "family": "GoogleRoboto",
        "regular": "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Regular.ttf",
        "bold": "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Bold.ttf",
        "italic": "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Italic.ttf",
        "bold_italic": "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-BoldItalic.ttf",
    },
    {
        "family": "DejaVuSansCustom",
        "regular": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "italic": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        "bold_italic": "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
    },
    {
        "family": "LiberationSansCustom",
        "regular": "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "bold": "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "italic": "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
        "bold_italic": "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf",
    },
]

_MONO_CANDIDATES: list[str] = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
]

_REGISTERED_SANS: tuple[str, str, str, str] | None = None
_REGISTERED_MONO: str | None = None
_REGISTERED_SYMBOL: str | None = None

_SYMBOL_CANDIDATES: list[str] = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _ensure_fonts() -> tuple[tuple[str, str, str, str], str]:
    """Registers the best available UTF-8 sans, mono & arrow-symbol fonts once per process."""
    global _REGISTERED_SANS, _REGISTERED_MONO, _REGISTERED_SYMBOL

    if _REGISTERED_SANS is None:
        for candidate in _FONT_CANDIDATES:
            paths = {k: Path(candidate[k]) for k in ("regular", "bold", "italic", "bold_italic")}
            if all(p.is_file() for p in paths.values()):
                fam = candidate["family"]
                reg_name = f"{fam}-Regular"
                bold_name = f"{fam}-Bold"
                ital_name = f"{fam}-Italic"
                bi_name = f"{fam}-BoldItalic"
                try:
                    if reg_name not in pdfmetrics.getRegisteredFontNames():
                        pdfmetrics.registerFont(TTFont(reg_name, str(paths["regular"])))
                        pdfmetrics.registerFont(TTFont(bold_name, str(paths["bold"])))
                        pdfmetrics.registerFont(TTFont(ital_name, str(paths["italic"])))
                        pdfmetrics.registerFont(TTFont(bi_name, str(paths["bold_italic"])))
                        pdfmetrics.registerFontFamily(
                            fam,
                            normal=reg_name,
                            bold=bold_name,
                            italic=ital_name,
                            boldItalic=bi_name,
                        )
                    _REGISTERED_SANS = (reg_name, bold_name, ital_name, bi_name)
                    break
                except Exception:  # noqa: BLE001
                    continue

        if _REGISTERED_SANS is None:
            _REGISTERED_SANS = ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique")

    if _REGISTERED_MONO is None:
        for mono_path in _MONO_CANDIDATES:
            p = Path(mono_path)
            if p.is_file():
                mono_name = "BacenMono"
                try:
                    if mono_name not in pdfmetrics.getRegisteredFontNames():
                        pdfmetrics.registerFont(TTFont(mono_name, str(p)))
                    _REGISTERED_MONO = mono_name
                    break
                except Exception:  # noqa: BLE001
                    continue
        if _REGISTERED_MONO is None:
            _REGISTERED_MONO = "Courier"

    if _REGISTERED_SYMBOL is None:
        for sym_path in _SYMBOL_CANDIDATES:
            p = Path(sym_path)
            if p.is_file():
                sym_name = "BacenSymbol"
                try:
                    if sym_name not in pdfmetrics.getRegisteredFontNames():
                        pdfmetrics.registerFont(TTFont(sym_name, str(p)))
                    _REGISTERED_SYMBOL = sym_name
                    break
                except Exception:  # noqa: BLE001
                    continue
        if _REGISTERED_SYMBOL is None:
            _REGISTERED_SYMBOL = ""

    return _REGISTERED_SANS, _REGISTERED_MONO


# --------------------------------------------------------------------------------------
# Emoji & text sanitization (prevents missing-glyph boxes in PDF fonts)
# --------------------------------------------------------------------------------------

_EMOJI_REPLACEMENTS: dict[str, str] = {
    "🥇": "#1 ",
    "🥈": "#2 ",
    "🥉": "#3 ",
    "✅": "[OK] ",
    "✔️": "[OK] ",
    "✔": "[OK] ",
    "❌": "[X] ",
    "⚠️": "[!] ",
    "⚠": "[!] ",
    "🟢": "[+] ",
    "🟡": "[~] ",
    "🔴": "[-] ",
    "🔵": "[*] ",
    "⭐": "* ",
    "★": "* ",
    "→": "->",
    "←": "<-",
    "↓": "v",
    "↑": "^",
    "≥": ">=",
    "≤": "<=",
    "≠": "!=",
    "•": "-",
    "–": "-",
    "—": " - ",
    "\u00a0": " ",
}

# Strip supplementary-plane emojis / pictographs / variation selectors that TTF text fonts lack.
_STRIP_EMOJI_RE = re.compile(
    "["
    "\U00010000-\U0010FFFF"
    "\u2600-\u27BF"
    "\uFE0E\uFE0F\u200D"
    "]+"
)


def _clean_text_for_pdf(text: str, is_ttf: bool) -> str:
    """Normalizes symbols and strips unsupported emoji glyphs so PDF never renders tofu boxes."""
    out = text
    has_arrow_font = bool(_REGISTERED_SYMBOL)
    for src, dst in _EMOJI_REPLACEMENTS.items():
        if src in ("≥", "≤", "≠", "•", "–", "—") and is_ttf:
            continue
        if src in ("→", "←", "↓", "↑") and is_ttf and has_arrow_font:
            continue
        out = out.replace(src, dst)
    out = _STRIP_EMOJI_RE.sub("", out)
    if not is_ttf:
        # Built-in Helvetica uses WinAnsiEncoding; replace characters outside latin-1 safely.
        out = out.encode("latin-1", errors="replace").decode("latin-1")
    return out


# --------------------------------------------------------------------------------------
# Inline Markdown -> ReportLab XML converter
# --------------------------------------------------------------------------------------

_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_BOLD_ITALIC_RE = re.compile(r"\*\*\*([^\*\n]+)\*\*\*")
_BOLD_RE = re.compile(r"\*\*([^\*\n]+)\*\*|__([^_\n]+)__")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^\*\n]+)\*(?!\*)")
_ARROW_RE = re.compile(r"([↓↑→←])")


def _md_inline_to_rl(text: str, mono_font: str, is_ttf: bool) -> str:
    """Converts inline Markdown (**bold**, *italic*, `code`, [links](url)) to ReportLab XML."""
    cleaned = _clean_text_for_pdf(text, is_ttf=is_ttf)

    # Protect inline code spans first so asterisks inside code aren't formatted.
    code_tokens: list[str] = []

    def _stash_code(match: re.Match[str]) -> str:
        code_html = html.escape(match.group(1), quote=False)
        token = f"\x00CODE{len(code_tokens)}\x00"
        code_tokens.append(
            f'<font name="{mono_font}" color="#174EA6" size="8.5">{code_html}</font>'
        )
        return token

    work = _INLINE_CODE_RE.sub(_stash_code, cleaned)

    # Protect links before escaping XML.
    link_tokens: list[str] = []

    def _stash_link(match: re.Match[str]) -> str:
        label = html.escape(match.group(1), quote=False)
        url = html.escape(match.group(2), quote=True)
        token = f"\x00LINK{len(link_tokens)}\x00"
        link_tokens.append(f'<a href="{url}" color="#1A73E8"><u>{label}</u></a>')
        return token

    work = _LINK_RE.sub(_stash_link, work)

    # Escape XML entities cleanly.
    work = html.escape(work, quote=False)

    # Render Unicode arrows via DejaVu symbol font (Roboto TTF omits arrow glyphs).
    if is_ttf and _REGISTERED_SYMBOL:
        work = _ARROW_RE.sub(rf'<font name="{_REGISTERED_SYMBOL}">\1</font>', work)

    # Apply bold/italic emphasis.
    work = _BOLD_ITALIC_RE.sub(r"<b><i>\1</i></b>", work)
    work = _BOLD_RE.sub(lambda m: f"<b>{m.group(1) or m.group(2)}</b>", work)
    work = _ITALIC_RE.sub(r"<i>\1</i>", work)

    # Restore links and inline code.
    for idx, snippet in enumerate(link_tokens):
        work = work.replace(f"\x00LINK{idx}\x00", snippet)
    for idx, snippet in enumerate(code_tokens):
        work = work.replace(f"\x00CODE{idx}\x00", snippet)

    return work


# --------------------------------------------------------------------------------------
# Report Metadata & Page Template Canvas
# --------------------------------------------------------------------------------------


@dataclass
class PdfReportMetadata:
    """Optional AgentOps provenance metadata shown in the executive PDF header."""

    prompt: str = ""
    agents: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    tool_calls_count: int = 0
    latency_s: float | None = None
    critic_verdict: dict[str, Any] | None = None
    session_id: str = ""
    generated_at: str = ""


class _GoogleExecutiveCanvas(canvas.Canvas):
    """Two-pass canvas rendering Google's 4-color top accent, running header and Page X de Y."""

    def __init__(self, *args: Any, report_title: str = "", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []
        self._report_title = report_title

    def showPage(self) -> None:  # noqa: N802 - ReportLab API
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_chrome(total_pages)
            super().showPage()
        super().save()

    def _draw_chrome(self, total_pages: int) -> None:
        sans_fonts, _ = _ensure_fonts()
        regular_font, bold_font, _, _ = sans_fonts
        page_w, page_h = self._pagesize
        margin_x = 18 * mm
        page_num = self._pageNumber

        self.saveState()

        # Page 1: subtle 3pt Google 4-color accent bar across the very top edge.
        if page_num == 1:
            bar_h = 3.2
            y_bar = page_h - bar_h
            segments = [
                (0.00, 0.55, GOOGLE_BLUE),
                (0.55, 0.15, GOOGLE_RED),
                (0.70, 0.15, GOOGLE_YELLOW),
                (0.85, 0.15, GOOGLE_GREEN),
            ]
            for start_frac, width_frac, col in segments:
                self.setFillColor(col)
                self.rect(page_w * start_frac, y_bar, page_w * width_frac + 0.5, bar_h, stroke=0, fill=1)
        else:
            # Pages 2+: clean minimalist running header.
            header_y = page_h - 12 * mm
            self.setFont(bold_font, 7.5)
            self.setFillColor(GOOGLE_BLUE)
            self.drawString(margin_x, header_y, "BACEN FINTECH ADVISOR")
            self.setFont(regular_font, 7.5)
            self.setFillColor(TEXT_MUTED)
            short_title = (
                self._report_title[:72] + "..."
                if len(self._report_title) > 75
                else self._report_title
            )
            self.drawRightString(page_w - margin_x, header_y, short_title)
            self.setStrokeColor(BORDER_SUBTLE)
            self.setLineWidth(0.6)
            self.line(margin_x, header_y - 3.5, page_w - margin_x, header_y - 3.5)

        # All pages: clean footer with official BCB provenance + Page X de Y.
        footer_y = 11.5 * mm
        self.setStrokeColor(BORDER_SUBTLE)
        self.setLineWidth(0.6)
        self.line(margin_x, footer_y + 9, page_w - margin_x, footer_y + 9)

        self.setFont(regular_font, 7.2)
        self.setFillColor(TEXT_MUTED)
        self.drawString(
            margin_x,
            footer_y,
            "Fonte: Dados Públicos Banco Central do Brasil (Olinda / Deati / IF.data) & Open Finance Brasil",
        )
        self.setFont(bold_font, 7.5)
        self.setFillColor(TEXT_BODY)
        self.drawRightString(page_w - margin_x, footer_y, f"Página {page_num} de {total_pages}")

        self.restoreState()


# --------------------------------------------------------------------------------------
# Stylesheet Builder
# --------------------------------------------------------------------------------------


def _build_styles() -> tuple[StyleSheet1, str, bool]:
    (regular, bold, italic, _bold_italic), mono = _ensure_fonts()
    is_ttf = regular != "Helvetica"
    styles = StyleSheet1()

    styles.add(
        ParagraphStyle(
            name="Eyebrow",
            fontName=bold,
            fontSize=8,
            leading=11,
            textColor=GOOGLE_BLUE,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="DocTitle",
            fontName=bold,
            fontSize=17.5,
            leading=22,
            textColor=TEXT_PRIMARY,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="DocSubtitle",
            fontName=regular,
            fontSize=9,
            leading=13,
            textColor=TEXT_MUTED,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H1",
            fontName=bold,
            fontSize=13.5,
            leading=18,
            textColor=TEXT_PRIMARY,
            spaceBefore=12,
            spaceAfter=5,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H2",
            fontName=bold,
            fontSize=11.5,
            leading=15.5,
            textColor=GOOGLE_BLUE_DARK,
            spaceBefore=11,
            spaceAfter=4,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H3",
            fontName=bold,
            fontSize=10,
            leading=14,
            textColor=TEXT_PRIMARY,
            spaceBefore=8,
            spaceAfter=3,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            fontName=regular,
            fontSize=9.3,
            leading=14,
            textColor=TEXT_BODY,
            spaceAfter=5.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ListItem",
            fontName=regular,
            fontSize=9.2,
            leading=13.6,
            textColor=TEXT_BODY,
            spaceAfter=2.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Callout",
            fontName=regular,
            fontSize=9,
            leading=13.5,
            textColor=TEXT_PRIMARY,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PromptLabel",
            fontName=bold,
            fontSize=7.5,
            leading=10,
            textColor=GOOGLE_BLUE_DARK,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PromptText",
            fontName=italic,
            fontSize=9,
            leading=13,
            textColor=TEXT_PRIMARY,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CodeBlock",
            fontName=mono,
            fontSize=7.8,
            leading=11,
            textColor=TEXT_PRIMARY,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableHeader",
            fontName=bold,
            fontSize=8.0,
            leading=10.5,
            textColor=GOOGLE_BLUE_DARK,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableCell",
            fontName=regular,
            fontSize=7.9,
            leading=10.6,
            textColor=TEXT_BODY,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableCellNum",
            fontName=regular,
            fontSize=7.9,
            leading=10.6,
            textColor=TEXT_BODY,
            alignment=TA_RIGHT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="MetaKey",
            fontName=bold,
            fontSize=7.2,
            leading=9.5,
            textColor=TEXT_MUTED,
        )
    )
    styles.add(
        ParagraphStyle(
            name="MetaVal",
            fontName=regular,
            fontSize=8.2,
            leading=11,
            textColor=TEXT_PRIMARY,
        )
    )
    return styles, mono, is_ttf


# --------------------------------------------------------------------------------------
# Markdown Block Parser -> ReportLab Flowables
# --------------------------------------------------------------------------------------

_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")
_ORDERED_LIST_RE = re.compile(r"^\s*\d+\.\s+(.*)$")
_UNORDERED_LIST_RE = re.compile(r"^\s*[-*•]\s+(.*)$")
_NUMERIC_CELL_RE = re.compile(r"^[+-]?\s*(?:R\$\s*)?\d[\d.,]*\s*(?:%|p\.p\.|bps|a\.a\.|a\.m\.|ms|s|bi|mi|M|B)?$", re.IGNORECASE)


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _build_table_flowable(
    header_cells: list[str],
    body_rows: list[list[str]],
    styles: StyleSheet1,
    mono: str,
    is_ttf: bool,
    avail_width: float,
) -> Table:
    col_count = max(len(header_cells), max((len(r) for r in body_rows), default=0))
    if col_count == 0:
        return Table([[""]])

    padded_header = header_cells + [""] * (col_count - len(header_cells))
    padded_rows = [r + [""] * (col_count - len(r)) for r in body_rows]

    # Detect numeric columns for clean right-alignment (tabular financial style).
    numeric_cols: set[int] = set()
    for c_idx in range(col_count):
        non_empty = [r[c_idx].strip() for r in padded_rows if r[c_idx].strip() and r[c_idx].strip() not in ("-", "—", "N/A")]
        if non_empty and all(_NUMERIC_CELL_RE.match(v.replace("**", "").strip()) for v in non_empty):
            numeric_cols.add(c_idx)

    # Smart proportional column widths ensuring single words (e.g. INCUMBENTES) never orphan a letter.
    weights: list[float] = []
    min_widths: list[float] = []
    for c_idx in range(col_count):
        plain_cells = [re.sub(r"[*`_]", "", padded_header[c_idx])] + [
            re.sub(r"[*`_]", "", r[c_idx]) for r in padded_rows[:25]
        ]
        longest_word = max(
            (len(tok) for cell in plain_cells for tok in cell.split()),
            default=4,
        )
        # Approximate 4.8pt per char at 8pt font + 11pt horizontal padding.
        min_widths.append(min(avail_width * 0.30, max(36.0, longest_word * 4.85 + 12.0)))
        samples = [len(c) for c in plain_cells]
        avg_len = sum(samples) / max(len(samples), 1)
        max_len = max(samples, default=4)
        score = max(7.0, min(36.0, 0.45 * avg_len + 0.55 * min(max_len, 38)))
        weights.append(score)

    if sum(min_widths) <= avail_width:
        leftover = avail_width - sum(min_widths)
        total_w = sum(weights) or 1.0
        col_widths = [min_w + leftover * (w / total_w) for min_w, w in zip(min_widths, weights, strict=True)]
    else:
        total_min = sum(min_widths) or 1.0
        col_widths = [avail_width * (m / total_min) for m in min_widths]

    # Render cells as Paragraphs so long values wrap cleanly inside column bounds.
    header_style_right = ParagraphStyle(
        name="TableHeaderRight",
        parent=styles["TableHeader"],
        alignment=TA_RIGHT,
    )
    table_data: list[list[Paragraph]] = [
        [
            Paragraph(
                _md_inline_to_rl(cell, mono, is_ttf),
                header_style_right if idx in numeric_cols else styles["TableHeader"],
            )
            for idx, cell in enumerate(padded_header)
        ]
    ]
    for row in padded_rows:
        table_data.append(
            [
                Paragraph(
                    _md_inline_to_rl(cell, mono, is_ttf),
                    styles["TableCellNum"] if idx in numeric_cols else styles["TableCell"],
                )
                for idx, cell in enumerate(row)
            ]
        )

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    style_cmds: list[Any] = [
        ("BACKGROUND", (0, 0), (-1, 0), GOOGLE_BLUE_TINT),
        ("TEXTCOLOR", (0, 0), (-1, 0), GOOGLE_BLUE_DARK),
        ("LINEBELOW", (0, 0), (-1, 0), 1.1, GOOGLE_BLUE),
        ("LINEABOVE", (0, 0), (-1, 0), 0.6, BORDER_MEDIUM),
        ("LINEBELOW", (0, -1), (-1, -1), 0.8, BORDER_MEDIUM),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    for r_idx in range(1, len(table_data)):
        if r_idx % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, r_idx), (-1, r_idx), GOOGLE_SURFACE_ALT))
        if r_idx < len(table_data) - 1:
            style_cmds.append(("LINEBELOW", (0, r_idx), (-1, r_idx), 0.4, BORDER_SUBTLE))

    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def _build_callout_box(
    lines: list[str],
    styles: StyleSheet1,
    mono: str,
    is_ttf: bool,
    avail_width: float,
) -> Table:
    content_html = "<br/>".join(_md_inline_to_rl(ln, mono, is_ttf) for ln in lines)
    p = Paragraph(content_html, styles["Callout"])
    box = Table([[p]], colWidths=[avail_width])
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), GOOGLE_SURFACE_CALLOUT),
                ("LINEBEFORE", (0, 0), (0, -1), 3.0, GOOGLE_BLUE),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return box


def _build_code_box(lines: list[str], styles: StyleSheet1, is_ttf: bool, avail_width: float) -> Table:
    escaped_lines = [
        html.escape(_clean_text_for_pdf(ln, is_ttf=is_ttf), quote=False).replace(" ", "&nbsp;")
        for ln in lines
    ]
    p = Paragraph("<br/>".join(escaped_lines) or "&nbsp;", styles["CodeBlock"])
    box = Table([[p]], colWidths=[avail_width])
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), GOOGLE_SURFACE_ALT),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER_SUBTLE),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return box


def _parse_markdown_to_flowables(
    markdown: str,
    styles: StyleSheet1,
    mono: str,
    is_ttf: bool,
    avail_width: float,
) -> list[Any]:
    lines = markdown.replace("\r\n", "\n").split("\n")
    flowables: list[Any] = []
    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]
        stripped = raw.strip()

        if not stripped:
            i += 1
            continue

        # Fenced code block.
        if stripped.startswith("```"):
            code_lines: list[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < n:
                i += 1  # consume closing fence
            flowables.append(Spacer(1, 3))
            flowables.append(_build_code_box(code_lines, styles, is_ttf, avail_width))
            flowables.append(Spacer(1, 6))
            continue

        # Horizontal rule.
        if re.match(r"^([-*_])\1{2,}\s*$", stripped):
            flowables.append(Spacer(1, 4))
            flowables.append(HRFlowable(width="100%", thickness=0.6, color=BORDER_SUBTLE))
            flowables.append(Spacer(1, 6))
            i += 1
            continue

        # Headings (#, ##, ###, ####).
        heading_match = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text_xml = _md_inline_to_rl(heading_match.group(2).strip(), mono, is_ttf)
            style_name = {1: "H1", 2: "H2", 3: "H3", 4: "H3"}[level]
            flowables.append(Paragraph(text_xml, styles[style_name]))
            if level == 1:
                flowables.append(HRFlowable(width="100%", thickness=0.8, color=GOOGLE_BLUE_TINT))
                flowables.append(Spacer(1, 4))
            i += 1
            continue

        # Markdown Table (header + separator + body rows).
        if "|" in stripped and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1]):
            header = _split_table_row(lines[i])
            i += 2  # skip header + separator
            body: list[list[str]] = []
            while i < n and lines[i].strip() and "|" in lines[i]:
                body.append(_split_table_row(lines[i]))
                i += 1
            flowables.append(Spacer(1, 3))
            flowables.append(_build_table_flowable(header, body, styles, mono, is_ttf, avail_width))
            flowables.append(Spacer(1, 7))
            continue

        # Blockquote -> Material 3 Callout Box.
        if stripped.startswith(">"):
            quote_lines: list[str] = []
            while i < n and lines[i].strip().startswith(">"):
                quote_lines.append(re.sub(r"^>\s?", "", lines[i].strip()))
                i += 1
            flowables.append(Spacer(1, 3))
            flowables.append(_build_callout_box(quote_lines, styles, mono, is_ttf, avail_width))
            flowables.append(Spacer(1, 6))
            continue

        # Unordered list.
        if _UNORDERED_LIST_RE.match(raw):
            items: list[ListItem] = []
            while i < n:
                m = _UNORDERED_LIST_RE.match(lines[i])
                if not m:
                    break
                items.append(
                    ListItem(
                        Paragraph(_md_inline_to_rl(m.group(1).strip(), mono, is_ttf), styles["ListItem"]),
                        bulletColor=GOOGLE_BLUE,
                    )
                )
                i += 1
            flowables.append(
                ListFlowable(
                    items,
                    bulletType="bullet",
                    start="bulletchar",
                    leftIndent=14,
                    bulletOffsetY=-0.5,
                    spaceBefore=2,
                    spaceAfter=6,
                )
            )
            continue

        # Ordered list.
        if _ORDERED_LIST_RE.match(raw):
            sans_fonts, _ = _ensure_fonts()
            items = []
            while i < n:
                m = _ORDERED_LIST_RE.match(lines[i])
                if not m:
                    break
                items.append(
                    ListItem(
                        Paragraph(_md_inline_to_rl(m.group(1).strip(), mono, is_ttf), styles["ListItem"]),
                        bulletColor=GOOGLE_BLUE_DARK,
                    )
                )
                i += 1
            flowables.append(
                ListFlowable(
                    items,
                    bulletType="1",
                    bulletFontName=sans_fonts[1],
                    bulletFontSize=9.0,
                    bulletFormat="%s.",
                    leftIndent=16,
                    bulletDedent=12,
                    spaceBefore=2,
                    spaceAfter=6,
                )
            )
            continue

        # Regular paragraph (merge consecutive plain lines until blank or next block).
        para_lines: list[str] = [stripped]
        i += 1
        while i < n:
            nxt = lines[i]
            nxt_s = nxt.strip()
            if (
                not nxt_s
                or nxt_s.startswith(("#", ">", "```"))
                or _UNORDERED_LIST_RE.match(nxt)
                or _ORDERED_LIST_RE.match(nxt)
                or re.match(r"^([-*_])\1{2,}\s*$", nxt_s)
                or ("|" in nxt_s and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1]))
            ):
                break
            para_lines.append(nxt_s)
            i += 1
        flowables.append(Paragraph(_md_inline_to_rl(" ".join(para_lines), mono, is_ttf), styles["Body"]))

    return flowables


# --------------------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------------------


def _infer_title(title: str | None, markdown: str, prompt: str) -> str:
    if title and title.strip():
        return title.strip()
    for line in markdown.splitlines():
        m = re.match(r"^#{1,3}\s+(.*)$", line.strip())
        if m:
            candidate = re.sub(r"[*`_]", "", m.group(1)).strip()
            if candidate:
                return candidate
    if prompt and prompt.strip():
        clean = prompt.strip()
        return clean[:85] + ("..." if len(clean) > 85 else "")
    return "Relatório de Inteligência Competitiva & Regulatória BCB"


def generate_executive_pdf(
    markdown: str,
    *,
    title: str | None = None,
    metadata: PdfReportMetadata | None = None,
) -> bytes:
    """Renders a Google Material Design 3 executive PDF from a Markdown response.

    Applies deterministic PII redaction (:func:`bacen_advisor.pii.redact_regex`) to all
    input strings before rendering.

    Args:
      markdown: Markdown content produced by the Bacen Fintech Advisor agent.
      title: Optional explicit document title (inferred from first heading or prompt if omitted).
      metadata: Optional AgentOps provenance (prompt, agents, models, CriticVerdict, latency).

    Returns:
      Raw ``application/pdf`` bytes ready to stream or save to disk.
    """
    meta = metadata or PdfReportMetadata()

    safe_markdown = redact_regex(markdown or "")
    safe_prompt = redact_regex(meta.prompt or "")
    raw_title = _infer_title(title, safe_markdown, safe_prompt)
    safe_title = redact_regex(raw_title)

    styles, mono, is_ttf = _build_styles()
    clean_title_for_canvas = _clean_text_for_pdf(safe_title, is_ttf=is_ttf)

    margin_x = 18 * mm
    page_w, _page_h = A4
    avail_width = page_w - 2 * margin_x

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=margin_x,
        rightMargin=margin_x,
        topMargin=19 * mm,
        bottomMargin=19 * mm,
        title=clean_title_for_canvas,
        author="Bacen Fintech Advisor (Google ADK)",
        subject="Inteligência Competitiva & Regulatória — Banco Central do Brasil",
    )

    story: list[Any] = []

    # 1. Google-style Eyebrow & Main Title
    story.append(
        Paragraph("BACEN FINTECH ADVISOR  ·  RELATÓRIO EXECUTIVO", styles["Eyebrow"])
    )
    story.append(Paragraph(_md_inline_to_rl(safe_title, mono, is_ttf), styles["DocTitle"]))

    generated_ts = meta.generated_at or dt.datetime.now(dt.UTC).strftime("%d/%m/%Y %H:%M UTC")
    subtitle_parts = [f"Gerado em {generated_ts}"]
    if meta.latency_s is not None:
        subtitle_parts.append(f"Latência do pipeline: {meta.latency_s:.1f}s")
    if meta.tool_calls_count:
        subtitle_parts.append(f"{meta.tool_calls_count} consulta(s) MCP BCB")
    story.append(Paragraph(_md_inline_to_rl("  ·  ".join(subtitle_parts), mono, is_ttf), styles["DocSubtitle"]))

    # 2. AgentOps Governance & Grounding Strip (when pipeline metadata is present)
    meta_cells: list[tuple[str, str, Any | None]] = []
    if meta.agents:
        meta_cells.append(("ORQUESTRAÇÃO MULTI-AGENTE", " → ".join(meta.agents), None))
    if meta.models:
        meta_cells.append(("ROTEAMENTO GEMINI", ", ".join(meta.models), None))
    if meta.critic_verdict:
        approved = bool(meta.critic_verdict.get("approved"))
        score = meta.critic_verdict.get("groundedness_score")
        status_label = "Aprovado" if approved else "Revisado com ressalvas"
        verdict_txt = f"{status_label}" + (f" · Groundedness {score}/5" if score is not None else "")
        badge_bg = GOOGLE_GREEN_TINT if approved else GOOGLE_AMBER_TINT
        badge_fg = GOOGLE_GREEN_TEXT if approved else GOOGLE_AMBER_TEXT
        meta_cells.append(("QUALITY CRITIC (LLM-AS-JUDGE)", verdict_txt, (badge_bg, badge_fg)))

    if meta_cells:
        col_w = avail_width / len(meta_cells)
        row_top = [Paragraph(k, styles["MetaKey"]) for k, _, _ in meta_cells]
        row_bot = []
        meta_style_cmds: list[Any] = [
            ("BACKGROUND", (0, 0), (-1, -1), GOOGLE_SURFACE_ALT),
            ("BOX", (0, 0), (-1, -1), 0.6, BORDER_SUBTLE),
            ("LINEBEFORE", (1, 0), (-1, -1), 0.5, BORDER_SUBTLE),
            ("TOPPADDING", (0, 0), (-1, 0), 5),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
            ("TOPPADDING", (0, 1), (-1, 1), 1),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        for idx, (_k, val, colors_pair) in enumerate(meta_cells):
            if colors_pair:
                bg, fg = colors_pair
                verdict_style = ParagraphStyle(
                    name=f"VerdictVal{idx}",
                    parent=styles["MetaVal"],
                    fontName=_ensure_fonts()[0][1],
                    textColor=fg,
                )
                row_bot.append(Paragraph(_md_inline_to_rl(val, mono, is_ttf), verdict_style))
                meta_style_cmds.append(("BACKGROUND", (idx, 0), (idx, 1), bg))
            else:
                row_bot.append(Paragraph(_md_inline_to_rl(val, mono, is_ttf), styles["MetaVal"]))

        meta_table = Table([row_top, row_bot], colWidths=[col_w] * len(meta_cells))
        meta_table.setStyle(TableStyle(meta_style_cmds))
        story.append(meta_table)
        story.append(Spacer(1, 7))

    # 3. Original User Prompt Strip
    if safe_prompt:
        prompt_block = Table(
            [
                [Paragraph("CONSULTA ANALISADA", styles["PromptLabel"])],
                [Paragraph(_md_inline_to_rl(safe_prompt, mono, is_ttf), styles["PromptText"])],
            ],
            colWidths=[avail_width],
        )
        prompt_block.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), GOOGLE_BLUE_TINT),
                    ("LINEBEFORE", (0, 0), (0, -1), 3.0, GOOGLE_BLUE),
                    ("TOPPADDING", (0, 0), (-1, 0), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
                    ("TOPPADDING", (0, 1), (-1, 1), 1),
                    ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        story.append(KeepTogether([prompt_block, Spacer(1, 8)]))

    story.append(HRFlowable(width="100%", thickness=0.8, color=BORDER_MEDIUM))
    story.append(Spacer(1, 6))

    # 4. Main Markdown Body (strip redundant leading H1 if it matches the document header title)
    body_md = safe_markdown.lstrip()
    first_line_match = re.match(r"^#\s+([^\n]+)\n?", body_md)
    if first_line_match:
        h1_clean = re.sub(r"[*`_]", "", first_line_match.group(1)).strip().lower()
        if h1_clean == re.sub(r"[*`_]", "", safe_title).strip().lower():
            body_md = body_md[first_line_match.end() :].lstrip()

    body_flowables = _parse_markdown_to_flowables(
        body_md, styles=styles, mono=mono, is_ttf=is_ttf, avail_width=avail_width
    )
    if not body_flowables:
        body_flowables = [Paragraph("Nenhum conteúdo fornecido para exportação.", styles["Body"])]
    story.extend(body_flowables)

    doc.build(
        story,
        canvasmaker=lambda *a, **kw: _GoogleExecutiveCanvas(
            *a, report_title=clean_title_for_canvas, **kw
        ),
    )
    return buf.getvalue()
