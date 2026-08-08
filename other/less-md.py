#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import sys
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.expanduser("~/.local/lib/python3/site-packages"))
import ansi as a
from readkeyraw import ReadKeyRaw


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE_START_RE = re.compile(r"^\s*(`{3,})(?:\s*([^\s`]+))?\s*$")
FENCE_END_RE = re.compile(r"^\s*(`{3,})\s*$")
TABLE_DIVIDER_RE = re.compile(r"^\s*\|?(?:\s*:?[-]{3,}:?\s*\|)+\s*$")
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
LINK_RE = re.compile(r"\[([^\]]+?)\]\(([^)]+?)\)")
INLINE_RE = re.compile(
    r"(`+[^`]+`+|\[([^\]]+?)\]\(([^)]+?)\)|\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_)"
)

BASE_STYLE = a.w + a.K
SEARCH_STYLE = a.k + a.Y + a.d
LINK_STYLE = a.u + a.c
SELECTED_LINK_STYLE = a.v
HELP_STYLE = a.vdbW
PROMPT_STYLE = a.vdbW
ERROR_STYLE = a.dwR
CODE_STYLE = a.vkW
CODE_LANG_STYLE = a.rst + a.b + a.W
BLOCKQUOTE_STYLE = a.db
RULE_STYLE = a.dw
FENCE_STYLE = a.i + a.dw
STRIKE_STYLE = a.s
H1_STYLE = a.vdbW + " "
H2_STYLE = a.dwC + " "
H3_STYLE = " " + a.dwG + " "
H4_STYLE = " " + a.dk + a.Y + " "
H5_STYLE = "  " + a.dwM + " "
H6_STYLE = "  " + a.dk + a.W + " "

HIDE_CURSOR = a.coff
SHOW_CURSOR = a.con
ALT_SCREEN_ON  = a.alton
ALT_SCREEN_OFF = a.altoff


@dataclass
class Span:
    start: int
    end: int
    style: str = ""
    link_id: Optional[int] = None
    target: Optional[str] = None


@dataclass
class LinkRef:
    link_id: int
    line_index: int
    start: int
    end: int
    target: str
    text: str
    intra: bool


@dataclass
class DisplayLine:
    plain: str
    spans: list[Span] = field(default_factory=list)
    source_line: int = 0
    kind: str = "text"
    prefix_len: int = 0  # length of bullet/number prefix for list items


@dataclass
class Document:
    path: str
    display_lines: list[DisplayLine]
    anchors: dict[str, int]
    links: list[LinkRef]


@dataclass
class JumpPos:
    path: str
    line_index: int
    left: int


@dataclass
class SearchState:
    pattern: str = ""
    regex: Optional[re.Pattern] = None
    forward: bool = True
    matches: list[tuple[int, int, int]] = field(default_factory=list)
    current_index: int = -1
    ignore_case: bool = True


def ansi_visible_len(text: str) -> int:
    return len(ANSI_RE.sub("", text))


def terminal_size() -> tuple[int, int]:
    size = shutil.get_terminal_size((80, 24))
    return size.columns, size.lines


def truncate_visible(text: str, width: int) -> str:
    if width <= 0:
        return ""
    out = []
    visible = 0
    i = 0
    while i < len(text) and visible < width:
        if text[i] == "\x1b":
            m = ANSI_RE.match(text, i)
            if m:
                out.append(m.group(0))
                i = m.end()
                continue
        out.append(text[i])
        visible += 1
        i += 1
    out.append(a.rst)
    return "".join(out)


def slugify(text: str) -> str:
    lowered = text.lower().strip()
    lowered = re.sub(r"[^\w\s-]", "", lowered, flags=re.UNICODE)
    lowered = re.sub(r"\s+", "-", lowered)
    lowered = re.sub(r"-+", "-", lowered)
    return lowered.strip("-")


def split_table_row(text: str) -> list[str]:
    stripped = text.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]


def visible_len(text: str) -> int:
    return len(ANSI_RE.sub("", text))


def make_style(text: str, extra: str = "") -> str:
    return f"{BASE_STYLE}{extra}{text}{a.rst}"


def parse_inline(text: str, link_id_start: int = 0) -> tuple[str, list[Span], list[LinkRef], int]:
    plain_parts: list[str] = []
    spans: list[Span] = []
    links: list[LinkRef] = []
    link_id = link_id_start
    i = 0

    def emit(raw: str) -> None:
        if raw:
            plain_parts.append(raw)

    def plain_len() -> int:
        return len("".join(plain_parts))

    def parse_recursive(chunk: str, next_link_id: int) -> tuple[str, list[Span], list[LinkRef], int]:
        return parse_inline(chunk, next_link_id)

    while i < len(text):
        # Backslash escapes for common markdown punctuation.
        if text[i] == "\\" and i + 1 < len(text):
            emit(text[i + 1])
            i += 2
            continue

        # Footnote references: [^id] -> [id]
        if text.startswith("[^", i):
            j = text.find("]", i + 2)
            if j != -1:
                foot_id = text[i + 2:j].strip()
                start = plain_len()
                emit(f"[{foot_id}]")
                end = plain_len()
                spans.append(Span(start, end, a.duy))
                i = j + 1
                continue

        # Link: [label](target)
        if text[i] == "[":
            close_bracket = text.find("]", i + 1)
            if close_bracket != -1 and close_bracket + 1 < len(text) and text[close_bracket + 1] == "(":
                close_paren = text.find(")", close_bracket + 2)
                if close_paren != -1:
                    label = text[i + 1:close_bracket]
                    target = text[close_bracket + 2:close_paren]
                    start = plain_len()
                    label_plain, label_spans, _label_links, link_id = parse_recursive(label, link_id)
                    emit(label_plain)
                    end = plain_len()
                    for span in label_spans:
                        spans.append(Span(start + span.start, start + span.end, span.style, span.link_id, span.target))
                    spans.append(Span(start, end, LINK_STYLE, link_id=link_id, target=target))
                    links.append(
                        LinkRef(
                            link_id=link_id,
                            line_index=0,
                            start=start,
                            end=end,
                            target=target,
                            text=label_plain,
                            intra=target.startswith("#"),
                        )
                    )
                    link_id += 1
                    i = close_paren + 1
                    continue

        # Inline code span: only single backticks in flowing text.
        # Triple-backtick runs are reserved for fenced blocks handled at
        # line level and should remain literal when embedded in text.
        if text[i] == "`":
            run = 1
            while i + run < len(text) and text[i + run] == "`":
                run += 1
            if run != 1:
                emit("`" * run)
                i += run
                continue
            delim = "`" * run
            j = text.find(delim, i + run)
            if j != -1:
                body = text[i + run:j]
                start = plain_len()
                emit(body)
                end = plain_len()
                spans.append(Span(start, end, CODE_STYLE))
                i = j + run
                continue

        # Delimited emphasis/strike in precedence order.
        matched = False
        for delim, style in (
            ("***", a.d + a.l),
            ("___", a.d + a.l),
            ("~~", STRIKE_STYLE),
            ("**", a.d),
            ("__", a.d),
            ("*", a.l),
            ("_", a.l),
        ):
            if text.startswith(delim, i):
                j = text.find(delim, i + len(delim))
                if j != -1 and j > i + len(delim):
                    inner = text[i + len(delim):j]
                    start = plain_len()
                    inner_plain, inner_spans, inner_links, link_id = parse_recursive(inner, link_id)
                    emit(inner_plain)
                    end = plain_len()
                    spans.append(Span(start, end, style))
                    for span in inner_spans:
                        spans.append(Span(start + span.start, start + span.end, span.style, span.link_id, span.target))
                    for link in inner_links:
                        links.append(
                            LinkRef(
                                link_id=link.link_id,
                                line_index=0,
                                start=start + link.start,
                                end=start + link.end,
                                target=link.target,
                                text=link.text,
                                intra=link.intra,
                            )
                        )
                    i = j + len(delim)
                    matched = True
                    break
        if matched:
            continue

        emit(text[i])
        i += 1

    plain = "".join(plain_parts)
    return plain, spans, links, link_id


def parse_heading(line: str, link_id_start: int) -> Optional[tuple[int, str, list[Span], list[LinkRef], int]]:
    match = HEADING_RE.match(line)
    if not match:
        return None
    level = len(match.group(1))
    heading_text = re.sub(r"\s*#+\s*$", " ", match.group(2))
    if not heading_text.endswith(" "):
        heading_text += " "
    plain, spans, links, next_id = parse_inline(heading_text, link_id_start)
    style_map = {
        1: H1_STYLE,
        2: H2_STYLE,
        3: H3_STYLE,
        4: H4_STYLE,
        5: H5_STYLE,
        6: H6_STYLE,
    }
    spans.append(Span(0, len(plain), style_map[level]))
    return level, plain, spans, links, next_id


def parse_list_item(line: str) -> Optional[tuple[str, str]]:
    match = re.match(r"^(\s*)([-*+]\s+|\d+\.\s+)(.*)$", line)
    if not match:
        return None
    return match.group(1) + match.group(2), match.group(3)


def normalize_list_prefix(prefix: str) -> str:
    match = re.match(r"^(\s*)([-*+])(\s+)$", prefix)
    if not match:
        return prefix
    return f"{match.group(1)}•{match.group(3)}"


def parse_blockquote(line: str) -> Optional[tuple[int, str]]:
    match = re.match(r"^\s*((?:>\s*)+)(.*)$", line)
    if not match:
        return None
    prefix = match.group(1)
    depth = prefix.count(">")
    text = match.group(2)
    return depth, text


def blockquote_prefix_len(text: str) -> int:
    i = 0
    saw_bar = False
    while i < len(text) and text[i] in (" ", "│"):
        if text[i] == "│":
            saw_bar = True
        i += 1
    return i if saw_bar else 0


def is_horizontal_rule(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 3:
        return False
    compact = stripped.replace(" ", "")
    if len(compact) < 3:
        return False
    return all(ch == "-" for ch in compact) or all(ch == "*" for ch in compact)


def is_block_element(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if HEADING_RE.match(line):
        return True
    if FENCE_START_RE.match(line) or FENCE_END_RE.match(line):
        return True
    if parse_list_item(line) is not None:
        return True
    if parse_blockquote(line) is not None:
        return True
    if TABLE_ROW_RE.match(line) or TABLE_DIVIDER_RE.match(line):
        return True
    if is_horizontal_rule(line):
        return True
    if re.match(r"^\[\^([^\]]+)\]:", line.strip()):
        return True
    return False


def normalize_text_line(line: str) -> str:
    text = line.strip()
    out: list[str] = []
    in_code = False
    space_pending = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "`":
            in_code = not in_code
            if space_pending and out:
                out.append(" ")
                space_pending = False
            out.append(ch)
            i += 1
            continue
        if not in_code and ch.isspace():
            space_pending = True
            i += 1
            continue
        if space_pending and out:
            out.append(" ")
            space_pending = False
        out.append(ch)
        i += 1
    return "".join(out)


def is_table_block(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    if not TABLE_ROW_RE.match(lines[index]):
        return False
    if not TABLE_DIVIDER_RE.match(lines[index + 1]):
        return False
    return True


def render_table_block(lines: list[str], start_index: int, link_id_start: int) -> tuple[list[DisplayLine], dict[str, int], list[LinkRef], int, int]:
    header_raw = split_table_row(lines[start_index])
    if start_index + 1 >= len(lines) or not TABLE_DIVIDER_RE.match(lines[start_index + 1]):
        return [], {}, [], link_id_start, start_index

    body_rows_raw: list[list[str]] = []
    index = start_index + 2
    while index < len(lines) and TABLE_ROW_RE.match(lines[index]):
        body_rows_raw.append(split_table_row(lines[index]))
        index += 1

    all_rows_raw = [header_raw] + body_rows_raw
    width_count = max(len(r) for r in all_rows_raw)
    widths = [0] * width_count
    current_link_id = link_id_start

    parsed_header: list[tuple[str, list[Span], list[LinkRef]]] = []
    parsed_body: list[list[tuple[str, list[Span], list[LinkRef]]]] = []

    for cell_index in range(width_count):
        cell = header_raw[cell_index] if cell_index < len(header_raw) else ""
        plain, spans, lrefs, current_link_id = parse_inline(cell.strip(), current_link_id)
        parsed_header.append((plain, spans, lrefs))
        widths[cell_index] = max(widths[cell_index], visible_len(plain))

    for raw_row in body_rows_raw:
        parsed_row: list[tuple[str, list[Span], list[LinkRef]]] = []
        for cell_index in range(width_count):
            cell = raw_row[cell_index] if cell_index < len(raw_row) else ""
            plain, spans, lrefs, current_link_id = parse_inline(cell.strip(), current_link_id)
            parsed_row.append((plain, spans, lrefs))
            widths[cell_index] = max(widths[cell_index], visible_len(plain))
        parsed_body.append(parsed_row)

    def make_border(left: str, mid: str, right: str) -> str:
        parts = [left]
        for i, width in enumerate(widths):
            parts.append("─" * (width + 2))
            parts.append(right if i == len(widths) - 1 else mid)
        return "".join(parts)

    def center_pad(text: str, width: int) -> tuple[str, int]:
        pad = max(width - visible_len(text), 0)
        left = pad // 2
        right = pad - left
        return (" " * left) + text + (" " * right), left

    def left_pad(text: str, width: int) -> str:
        pad = max(width - visible_len(text), 0)
        return text + (" " * pad)

    def make_row(
        row_data: list[tuple[str, list[Span], list[LinkRef]]],
        line_index: int,
        header: bool = False,
    ) -> tuple[str, list[Span], list[LinkRef]]:
        pieces = ["│"]
        spans: list[Span] = [Span(0, 1, RULE_STYLE)]
        links: list[LinkRef] = []
        cursor = 1

        for cell_index, width in enumerate(widths):
            plain, cell_spans, cell_links = row_data[cell_index] if cell_index < len(row_data) else ("", [], [])
            if header:
                padded, left_off = center_pad(plain, width)
            else:
                padded = left_pad(plain, width)
                left_off = 0

            cell_text = " " + padded + " "
            pieces.append(cell_text)

            base = cursor + 1
            for span in cell_spans:
                spans.append(Span(base + left_off + span.start, base + left_off + span.end, span.style, span.link_id, span.target))
            for link in cell_links:
                links.append(
                    LinkRef(
                        link_id=link.link_id,
                        line_index=line_index,
                        start=base + left_off + link.start,
                        end=base + left_off + link.end,
                        target=link.target,
                        text=link.text,
                        intra=link.intra,
                    )
                )

            if header:
                spans.append(Span(base, base + len(padded), a.d))

            cursor += len(cell_text)
            pieces.append("│")
            spans.append(Span(cursor, cursor + 1, RULE_STYLE))
            cursor += 1

        return "".join(pieces), spans, links

    display_lines: list[DisplayLine] = []
    anchors: dict[str, int] = {}
    links: list[LinkRef] = []

    top = make_border("┌", "┬", "┐")
    mid = make_border("├", "┼", "┤")
    bottom = make_border("└", "┴", "┘")

    display_lines.append(DisplayLine(top, [Span(0, len(top), RULE_STYLE)], source_line=start_index + 1, kind="table"))
    header_idx = len(display_lines)
    header_plain, header_spans, header_links = make_row(parsed_header, header_idx, header=True)
    display_lines.append(DisplayLine(header_plain, header_spans, source_line=start_index + 1, kind="table"))
    display_lines.append(DisplayLine(mid, [Span(0, len(mid), RULE_STYLE)], source_line=start_index + 1, kind="table"))

    for row in parsed_body:
        row_idx = len(display_lines)
        row_plain, row_spans, row_links = make_row(row, row_idx, header=False)
        display_lines.append(DisplayLine(row_plain, row_spans, source_line=start_index + 1, kind="table"))
        links.extend(row_links)

    display_lines.append(DisplayLine(bottom, [Span(0, len(bottom), RULE_STYLE)], source_line=start_index + 1, kind="table"))
    links.extend(header_links)

    return display_lines, anchors, links, current_link_id, index


def render_document(path: str) -> Document:
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        lines = handle.read().splitlines()

    display_lines: list[DisplayLine] = []
    anchors: dict[str, int] = {}
    anchor_counts: dict[str, int] = {}
    links: list[LinkRef] = []
    footnotes: list[tuple[str, str]] = []
    link_id = 0
    index = 0
    in_comment = False
    list_counters: dict[int, int] = {}   # indent_level -> sequential counter
    last_list_prefix_len: int = 0         # body-start column of last list item

    while index < len(lines):
        line = lines[index]

        # Strip HTML comments.
        if in_comment:
            if "-->" in line:
                in_comment = False
            index += 1
            continue
        if "<!--" in line:
            if "-->" not in line:
                in_comment = True
            index += 1
            continue

        # Capture footnote definitions for footer rendering.
        foot_match = re.match(r"^\[\^([^\]]+)\]:\s*(.*)$", line.strip())
        if foot_match:
            footnotes.append((foot_match.group(1).strip(), normalize_text_line(foot_match.group(2))))
            index += 1
            continue

        # Block elements nested inside list item continuations (indented fences and blockquotes)
        if last_list_prefix_len > 0 and line.strip():
            _li_ind = len(line) - len(line.lstrip())
            if _li_ind >= last_list_prefix_len:
                _inner = line[last_list_prefix_len:]
                _ifm = FENCE_START_RE.match(_inner)
                if _ifm:
                    _fence = _ifm.group(1)
                    _lang  = (_ifm.group(2) or "").strip()
                    _cls: list[str] = []
                    _src = index + 1
                    index += 1
                    while index < len(lines):
                        _r = lines[index]
                        if _r.strip() == "":
                            _cls.append("")
                            index += 1
                            continue
                        if len(_r) - len(_r.lstrip()) < last_list_prefix_len:
                            break
                        _ir = _r[last_list_prefix_len:]
                        _cm = FENCE_END_RE.match(_ir)
                        if _cm and len(_cm.group(1)) >= len(_fence):
                            index += 1
                            break
                        _cls.append(_ir.rstrip("\n"))
                        index += 1
                    _dp = " " * last_list_prefix_len
                    _cw = max([len(x) for x in _cls] + [len(_lang), 1])
                    _lbl = f" {_lang} " if _lang else ""
                    _top = _dp + ("┌─" + _lbl + "─" * max(_cw + 1 - len(_lbl), 0) + "┐" if _lang else "┌" + "─" * (_cw + 2) + "┐")
                    _bot = _dp + "└" + "─" * (_cw + 2) + "┘"
                    _pl = len(_dp)
                    _ts: list[Span] = [Span(_pl, len(_top), CODE_STYLE)]
                    if _lang:
                        _ls = _pl + len("┌─")
                        _ts.append(Span(_ls, _ls + len(_lbl), CODE_LANG_STYLE))
                    display_lines.append(DisplayLine(_top, _ts, source_line=_src, kind="codebox"))
                    for _cl in _cls:
                        _row = _dp + "│ " + _cl + " " * (_cw - len(_cl)) + " │"
                        display_lines.append(DisplayLine(_row, [Span(_pl, len(_row), CODE_STYLE)], source_line=_src, kind="codebox"))
                    display_lines.append(DisplayLine(_bot, [Span(_pl, len(_bot), CODE_STYLE)], source_line=_src, kind="codebox"))
                    continue
                _ibq = parse_blockquote(_inner)
                if _ibq:
                    _depth, _qtext = _ibq
                    _plain, _spans, _nlinks, link_id = parse_inline(normalize_text_line(_qtext), link_id)
                    _bqp = " " * last_list_prefix_len + "│ " * _depth
                    for _s in _spans:
                        _s.start += len(_bqp)
                        _s.end   += len(_bqp)
                    _spans.append(Span(0, len(_bqp) + len(_plain), BLOCKQUOTE_STYLE))
                    for _lnk in _nlinks:
                        _lnk.start += len(_bqp)
                        _lnk.end   += len(_bqp)
                        _lnk.line_index = len(display_lines)
                        links.append(_lnk)
                    display_lines.append(DisplayLine(_bqp + _plain, _spans, source_line=index + 1, kind="blockquote"))
                    index += 1
                    continue

        # Fenced code block with box rendering.
        fence_match = FENCE_START_RE.match(line)
        if fence_match and last_list_prefix_len > 0:
            fence_indent = len(line) - len(line.lstrip())
            if fence_indent >= last_list_prefix_len:
                fence_match = None  # indented fence inside list context; treat as text
        if fence_match:
            last_list_prefix_len = 0
            list_counters.clear()
            fence = fence_match.group(1)
            language = (fence_match.group(2) or "").strip()
            code_lines: list[str] = []
            src_line = index + 1
            index += 1
            while index < len(lines):
                close_match = FENCE_END_RE.match(lines[index])
                if close_match and len(close_match.group(1)) >= len(fence):
                    break
                code_lines.append(lines[index].rstrip("\n"))
                index += 1
            if index < len(lines):
                index += 1

            width = max([len(x) for x in code_lines] + [len(language)])
            width = max(width, 1)
            label = ""
            if language:
                label = f" {language} "
                top_fill = max(width + 1 - len(label), 0)
                top = "  ┌─" + label + ("─" * top_fill) + "┐"
            else:
                top = "  ┌" + ("─" * (width + 2)) + "┐"
            bottom = "  └" + ("─" * (width + 2)) + "┘"
            top_spans = [Span(2, len(top), CODE_STYLE)]
            if language:
                label_start = len("  ┌─")
                top_spans.append(Span(label_start, label_start + len(label), CODE_LANG_STYLE))
            display_lines.append(DisplayLine(top, top_spans, source_line=src_line, kind="codebox"))
            for code_line in code_lines:
                padded = code_line + (" " * (width - len(code_line)))
                row = f"  │ {padded} │"
                display_lines.append(DisplayLine(row, [Span(2, len(row), CODE_STYLE)], source_line=src_line, kind="codebox"))
            display_lines.append(DisplayLine(bottom, [Span(2, len(bottom), CODE_STYLE)], source_line=src_line, kind="codebox"))
            continue

        if is_horizontal_rule(line):
            last_list_prefix_len = 0
            list_counters.clear()
            hr = "─"
            display_lines.append(DisplayLine(hr, [Span(0, len(hr), RULE_STYLE)], source_line=index + 1, kind="hr"))
            index += 1
            continue

        if is_table_block(lines, index):
            last_list_prefix_len = 0
            list_counters.clear()
            table_lines, table_anchors, table_links, link_id, end_index = render_table_block(lines, index, link_id)
            block_start = len(display_lines)
            for line_idx, display_line in enumerate(table_lines):
                display_lines.append(display_line)
            anchors.update(table_anchors)
            for link in table_links:
                link.line_index += block_start
                links.append(link)
            index = end_index + 1
            continue

        heading = parse_heading(line, link_id)
        if heading:
            last_list_prefix_len = 0
            list_counters.clear()
            level, plain, spans, new_links, link_id = heading
            for link in new_links:
                link.line_index = len(display_lines)
                links.append(link)
            anchor = slugify(plain)
            if anchor:
                count = anchor_counts.get(anchor, 0)
                resolved_anchor = anchor if count == 0 else f"{anchor}-{count}"
                anchor_counts[anchor] = count + 1
                anchors[resolved_anchor] = len(display_lines)
            display_lines.append(DisplayLine(plain, spans, source_line=index + 1, kind=f"h{level}"))
            index += 1
            continue

        quoted = parse_blockquote(line)
        if quoted is not None:
            last_list_prefix_len = 0
            list_counters.clear()
            depth, qtext = quoted
            plain, spans, new_links, link_id = parse_inline(normalize_text_line(qtext), link_id)
            qprefix = " " + ("│ " * depth)
            for span in spans:
                span.start += len(qprefix)
                span.end += len(qprefix)
            spans.append(Span(0, len(plain) + len(qprefix), BLOCKQUOTE_STYLE))
            for link in new_links:
                link.start += len(qprefix)
                link.end += len(qprefix)
                link.line_index = len(display_lines)
                links.append(link)
            display_lines.append(DisplayLine(f"{qprefix}{plain}", spans, source_line=index + 1, kind="blockquote"))
            index += 1
            continue

        list_item = parse_list_item(line)
        if list_item is not None:
            raw_prefix, body = list_item
            indent = len(raw_prefix) - len(raw_prefix.lstrip())
            raw_marker = raw_prefix[indent:]
            if re.match(r"^\d+\.\s+$", raw_marker):
                for k in [k for k in list_counters if k > indent]:
                    del list_counters[k]
                list_counters[indent] = list_counters.get(indent, 0) + 1
                display_prefix = " " * indent + f"{list_counters[indent]}. "
            else:
                for k in [k for k in list_counters if k >= indent]:
                    del list_counters[k]
                display_prefix = " " * indent + "• "
            last_list_prefix_len = len(display_prefix)
            body_heading = parse_heading(body.strip(), link_id) if body.strip().startswith("#") else None
            if body_heading:
                level, h_plain, h_spans, h_links, link_id = body_heading
                for span in h_spans:
                    span.start += len(display_prefix)
                    span.end += len(display_prefix)
                h_spans.append(Span(0, len(display_prefix), RULE_STYLE))
                for link in h_links:
                    link.start += len(display_prefix)
                    link.end += len(display_prefix)
                    link.line_index = len(display_lines)
                    links.append(link)
                display_lines.append(DisplayLine(display_prefix + h_plain, h_spans,
                                                  source_line=index + 1, kind="list",
                                                  prefix_len=len(display_prefix)))
            elif FENCE_START_RE.match(body.strip()):
                _fm = FENCE_START_RE.match(body.strip())
                _fence = _fm.group(1)                          # type: ignore[union-attr]
                _lang  = (_fm.group(2) or "").strip()          # type: ignore[union-attr]
                _cls: list[str] = []
                _src = index + 1
                index += 1
                while index < len(lines):
                    _r = lines[index]
                    if _r.strip() == "":
                        _cls.append("")
                        index += 1
                        continue
                    _ri = len(_r) - len(_r.lstrip())
                    if _ri < len(display_prefix):
                        break
                    _ir = _r[len(display_prefix):]
                    _cm = FENCE_END_RE.match(_ir)
                    if _cm and len(_cm.group(1)) >= len(_fence):
                        index += 1
                        break
                    _cls.append(_ir.rstrip("\n"))
                    index += 1
                _cw = max([len(x) for x in _cls] + [len(_lang), 1])
                _lbl = f" {_lang} " if _lang else ""
                _plen = len(display_prefix)
                _top = display_prefix + ("┌─" + _lbl + "─" * max(_cw + 1 - len(_lbl), 0) + "┐" if _lang else "┌" + "─" * (_cw + 2) + "┐")
                _bot = " " * _plen + "└" + "─" * (_cw + 2) + "┘"
                _ts: list[Span] = [Span(0, _plen, RULE_STYLE), Span(_plen, len(_top), CODE_STYLE)]
                if _lang:
                    _ls = _plen + len("┌─")
                    _ts.append(Span(_ls, _ls + len(_lbl), CODE_LANG_STYLE))
                display_lines.append(DisplayLine(_top, _ts, source_line=_src, kind="codebox"))
                for _cl in _cls:
                    _row = " " * _plen + "│ " + _cl + " " * (_cw - len(_cl)) + " │"
                    display_lines.append(DisplayLine(_row, [Span(_plen, len(_row), CODE_STYLE)], source_line=_src, kind="codebox"))
                display_lines.append(DisplayLine(_bot, [Span(_plen, len(_bot), CODE_STYLE)], source_line=_src, kind="codebox"))
                continue  # index already advanced in collection loop
            else:
                plain, spans, new_links, link_id = parse_inline(body, link_id)
                for span in spans:
                    span.start += len(display_prefix)
                    span.end += len(display_prefix)
                spans.append(Span(0, len(display_prefix), RULE_STYLE))
                for link in new_links:
                    link.start += len(display_prefix)
                    link.end += len(display_prefix)
                    link.line_index = len(display_lines)
                    links.append(link)
                display_lines.append(DisplayLine(display_prefix + plain, spans,
                                                  source_line=index + 1, kind="list",
                                                  prefix_len=len(display_prefix)))
            index += 1
            continue

        # Paragraph joining for soft-wrapped markdown lines.
        if line.strip() == "":
            display_lines.append(DisplayLine("", [], source_line=index + 1, kind="blank"))
            index += 1
            continue

        # Detect list-continuation paragraph (indented >= last list body start)
        line_indent = len(line) - len(line.lstrip())
        para_is_list_cont = last_list_prefix_len > 0 and line_indent >= last_list_prefix_len
        para_prefix_len = last_list_prefix_len if para_is_list_cont else 0

        para_source = index + 1
        para_segments: list[str] = []
        current = ""
        while index < len(lines):
            raw = lines[index]
            if raw.strip() == "":
                break
            if index != para_source - 1 and is_block_element(raw):
                break

            hard_break = raw.endswith("\\") or raw.endswith("  ")
            work = raw.rstrip()
            if work.endswith("\\"):
                work = work[:-1].rstrip()
            work = normalize_text_line(work)

            if current:
                if work:
                    current += " " + work
            else:
                current = work

            index += 1
            if hard_break:
                para_segments.append(current)
                current = ""

            if index < len(lines):
                nxt = lines[index]
                if nxt.strip() == "" or is_block_element(nxt):
                    break

        if current:
            para_segments.append(current)

        for seg in para_segments:
            plain, spans, new_links, link_id = parse_inline(seg, link_id)
            for link in new_links:
                link.line_index = len(display_lines)
                links.append(link)
            if para_is_list_cont:
                cont_prefix = " " * para_prefix_len
                for span in spans:
                    span.start += para_prefix_len
                    span.end += para_prefix_len
                display_lines.append(DisplayLine(cont_prefix + plain, spans,
                                                  source_line=para_source, kind="list",
                                                  prefix_len=para_prefix_len))
            else:
                last_list_prefix_len = 0
                display_lines.append(DisplayLine(plain, spans, source_line=para_source, kind="text"))

    # Render footnotes at document end.
    if footnotes:
        display_lines.append(DisplayLine("", [], source_line=max(1, len(lines)), kind="blank"))
        header = "Footnotes"
        display_lines.append(DisplayLine(header, [Span(0, len(header), a.duw)], source_line=max(1, len(lines)), kind="footnote"))
        for foot_id, foot_text in footnotes:
            plain, spans, new_links, link_id = parse_inline(foot_text, link_id)
            prefix = f"[{foot_id}] "
            for span in spans:
                span.start += len(prefix)
                span.end += len(prefix)
            spans.insert(0, Span(0, len(prefix), a.duy))
            for link in new_links:
                link.start += len(prefix)
                link.end += len(prefix)
                link.line_index = len(display_lines)
                links.append(link)
            display_lines.append(DisplayLine(prefix + plain, spans, source_line=max(1, len(lines)), kind="footnote"))

    return Document(path=path, display_lines=display_lines, anchors=anchors, links=links)


def compile_search(pattern: str) -> tuple[re.Pattern, bool]:
    ignore_case = not any(ch.isupper() for ch in pattern)
    flags = re.IGNORECASE if ignore_case else 0
    return re.compile(pattern, flags), ignore_case


def line_matches(regex: re.Pattern, line: str) -> list[tuple[int, int]]:
    matches: list[tuple[int, int]] = []
    for match in regex.finditer(line):
        if match.end() == match.start():
            continue
        matches.append((match.start(), match.end()))
    return matches


def render_line(display_line: DisplayLine, seg_start: int, seg_end: int, search_spans: list[tuple[int, int]], selected_link: Optional[LinkRef]) -> str:
    if seg_end <= seg_start:
        return BASE_STYLE + a.rst
    if seg_start >= len(display_line.plain):
        return BASE_STYLE + a.rst

    prefix_len = blockquote_prefix_len(display_line.plain) if display_line.kind == "blockquote" else 0
    list_cont = display_line.kind == "list" and display_line.prefix_len > 0 and seg_start >= display_line.prefix_len
    if display_line.kind == "blockquote" and prefix_len > 0 and seg_start >= prefix_len:
        begin = max(seg_start, prefix_len)
        end = min(seg_end, len(display_line.plain))
        if end <= begin:
            return ""
        visible = display_line.plain[:prefix_len] + display_line.plain[begin:end]
    elif list_cont:
        begin = seg_start
        end = min(seg_end, len(display_line.plain))
        if end <= begin:
            return ""
        visible = " " * display_line.prefix_len + display_line.plain[begin:end]
    else:
        begin = max(seg_start, 0)
        end = min(seg_end, len(display_line.plain))
        if end <= begin:
            return ""
        visible = display_line.plain[begin:end]
    if not visible:
        return BASE_STYLE + a.rst

    out: list[str] = [a.rst + BASE_STYLE]
    current_style = a.rst + BASE_STYLE
    for idx, ch in enumerate(visible):
        if display_line.kind == "blockquote" and prefix_len > 0 and seg_start >= prefix_len and idx < prefix_len:
            pos = idx
        elif display_line.kind == "blockquote" and prefix_len > 0 and seg_start >= prefix_len:
            pos = begin + (idx - prefix_len)
        elif list_cont:
            pos = -1 if idx < display_line.prefix_len else begin + (idx - display_line.prefix_len)
        else:
            pos = begin + idx
        styles: list[str] = [BASE_STYLE]
        for span in display_line.spans:
            if span.start <= pos < span.end and span.style:
                styles.append(span.style)
        for start, stop in search_spans:
            if start <= pos < stop:
                styles.append(SEARCH_STYLE)
                break
        if selected_link is not None:
            for span in display_line.spans:
                if span.link_id is not None and span.link_id == selected_link.link_id and span.start <= pos < span.end:
                    styles.append(SELECTED_LINK_STYLE)
                    break
        style = a.rst + "".join(styles)
        if style != current_style:
            out.append(style)
            current_style = style
        out.append(ch)
    out.append(a.rst)
    return "".join(out)


def highlight_ranges_for_line(regex: Optional[re.Pattern], plain: str) -> list[tuple[int, int]]:
    if regex is None:
        return []
    return line_matches(regex, plain)


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def status_text(width: int, message: str) -> str:
    text = f"{PROMPT_STYLE}{message}{a.rst}"
    return truncate_visible(text, width)


def format_status(
    doc: Document,
    top: int,
    left: int,
    height: int,
    width: int,
    search_state: SearchState,
    visual_lines: list[tuple[int, int, int]],
    message: str = "",
    hint: str = "",
    file_index: int = 0,
    file_count: int = 1,
) -> str:
    total = max(len(visual_lines), 1)
    visible_count = max(height - 1, 1)
    bottom = min(top + visible_count, total)
    percent = int((bottom / total) * 100)
    filename = os.path.basename(doc.path)
    if file_count > 1:
        filename = f"{filename} ({file_index + 1}/{file_count})"
    if visual_lines:
        first_doc_idx = visual_lines[min(top, len(visual_lines) - 1)][0]
        last_doc_idx = visual_lines[max(0, bottom - 1)][0]
        first_line = doc.display_lines[first_doc_idx].source_line
        last_line = doc.display_lines[last_doc_idx].source_line
    else:
        first_line = 0
        last_line = 0
    total_lines = max((line.source_line for line in doc.display_lines), default=0)
    search_part = ""
    if search_state.pattern:
        search_part = f"  /{search_state.pattern}/ {search_state.current_index + 1 if search_state.current_index >= 0 else 0}/{len(search_state.matches)}"
    extra = f" {message}" if message else ""
    hint_part = f" {hint}" if hint else ""
    text = f" {filename}  lines {first_line}-{last_line}/{total_lines}  {percent}%  col {left + 1}{search_part}{extra}{hint_part}"
    text = truncate_visible(f"{PROMPT_STYLE}{text}{a.rst}", width)
    return text


def wrap_search_message(pattern: str, direction: str) -> str:
    return f"search {direction}: {pattern}"


def input_line(keys: ReadKeyRaw, prompt: str, initial: str = "") -> Optional[str]:
    buffer = list(initial)
    while True:
        cols, rows = terminal_size()
        sys.stdout.write("\r")
        sys.stdout.write(status_text(cols, f"{prompt}{''.join(buffer)}"))
        sys.stdout.write("\x1b[K")
        sys.stdout.flush()
        key = keys.read_key_raw(timeout=None)
        if key in ("#ESC",):
            return None
        if key in ("#LF", "#CR"):
            return "".join(buffer)
        if key in ("#BS", "\x7f"):
            if buffer:
                buffer.pop()
            continue
        if len(key) == 1 and key.isprintable():
            buffer.append(key)
            continue


def prompt_help(doc_name: str) -> str:
    lines = [
        f"          {HELP_STYLE}less-md help{a.rst}\n",
        "    q                quit",
        "    h                help",
        "    Ctrl-L           repaint",
        "    Home | <         top of document",
        "    End | <          bottom of document",
        "    PgUp | PgDn      page up and down",
        "    Space | f        scroll down one page",
        "    b                scroll backward one page",
        "    d | u            scroll down/up half a page",
        "    Arrows           move up, down, left, right",
        "    Enter | f        scroll down one line",
        "    /                regex search forward",
        "    ?                regex search backward",
        "    n | N            repeat search, reverse repeat",
        "    m<letter>        set mark",
        "    '<letter>        jump mark",
        "    ''               previous jump",
        "    Ctrl-X Ctrl-X    toggle",
        "    :e [file]        open file",
        "    :n | :p          next/previous file",
        "    :x               reset to argv files",
        "    :d               delete current file",
        "    TAB | Shift-TAB  move between links",
        "                     Enter follows selected intra-document link",
        "\n              Press any key to return.",
    ]
    return "\n".join(lines)


def render_help_screen(doc_name: str, keys: ReadKeyRaw) -> None:
    cols, rows = terminal_size()
    sys.stdout.write(a.cls)
    sys.stdout.write(BASE_STYLE)
    help_lines = prompt_help(doc_name).splitlines()
    pad_top = max((rows - len(help_lines)) // 2, 0)
    for _ in range(pad_top):
        sys.stdout.write("\n")
    for line in help_lines:
        text = line[:cols]
        sys.stdout.write(text)
        sys.stdout.write("\n")
    sys.stdout.flush()
    keys.read_key_raw(timeout=None)


def normalize_path(path: str, base: Optional[str] = None) -> str:
    if os.path.isabs(path):
        return os.path.abspath(path)
    root = base if base else os.getcwd()
    return os.path.abspath(os.path.join(root, path))


class Pager:
    def __init__(self, argv_files: list[str]) -> None:
        self.original_files = [normalize_path(path) for path in argv_files]
        self.files = self.original_files.copy()
        self.index = 0
        self.documents: dict[str, Document] = {}
        self.top = 0
        self.left = 0
        self.resize_pending = True
        self.message = ""
        self.search_state = SearchState()
        self.marks: dict[tuple[str, str], JumpPos] = {}
        self.jump_stack: list[JumpPos] = []
        self.pending_mark: Optional[str] = None
        self.pending_quote: bool = False
        self.pending_ctrl_x: bool = False
        self.pending_colon: bool = False
        self.colon_buffer: list[str] = []
        self.pending_search: Optional[bool] = None
        self.pending_link_jump: bool = False
        self.selected_link_idx: int = -1
        self.running = True
        self.keys: Optional[ReadKeyRaw] = None
        self.file_positions: dict[str, tuple[int, int]] = {}

    def current_path(self) -> str:
        return self.files[self.index]

    def current_document(self) -> Document:
        path = self.current_path()
        if path not in self.documents:
            self.documents[path] = render_document(path)
        return self.documents[path]

    def current_link(self) -> Optional[LinkRef]:
        doc = self.current_document()
        if 0 <= self.selected_link_idx < len(doc.links):
            return doc.links[self.selected_link_idx]
        return None

    def set_message(self, message: str) -> None:
        self.message = message

    def push_jump(self) -> None:
        self.jump_stack.append(JumpPos(self.current_path(), self.top, self.left))
        if len(self.jump_stack) > 2:
            self.jump_stack = self.jump_stack[-2:]

    def go_back_jump(self) -> None:
        if len(self.jump_stack) < 2:
            self.set_message("no previous jump")
            return
        current = self.jump_stack.pop()
        prev = self.jump_stack.pop()
        self.jump_stack.append(current)
        self.jump_stack.append(prev)
        self._restore_pos(prev)

    def _restore_pos(self, pos: JumpPos) -> None:
        if pos.path in self.files:
            self.index = self.files.index(pos.path)
        else:
            self.files.append(pos.path)
            self.index = len(self.files) - 1
        self.top = pos.line_index
        self.left = pos.left

    def _save_file_pos(self) -> None:
        self.file_positions[self.current_path()] = (self.top, self.left)

    def _load_file_pos(self) -> None:
        saved = self.file_positions.get(self.current_path())
        self.top, self.left = saved if saved else (0, 0)

    def build_visual_lines(self, cols: int) -> tuple[list[tuple[int, int, int]], dict[int, int]]:
        doc = self.current_document()
        width = max(cols, 1)
        visual_lines: list[tuple[int, int, int]] = []
        first_visual_for_doc: dict[int, int] = {}

        for doc_idx, line in enumerate(doc.display_lines):
            line_len = len(line.plain)
            start = self.left

            if line.kind == "blockquote":
                prefix_len = blockquote_prefix_len(line.plain)
                if prefix_len > 0 and line_len > prefix_len:
                    body_start = prefix_len
                    body_len = line_len - body_start
                    body_offset = max(0, self.left)
                    seg_width = max(width - prefix_len, 1)
                    first = True

                    while body_offset < body_len:
                        abs_start = body_start + body_offset
                        limit = min(abs_start + seg_width, line_len)
                        end = limit
                        if limit < line_len:
                            split = line.plain.rfind(" ", abs_start, limit + 1)
                            if split > abs_start:
                                end = split
                        if end <= abs_start:
                            end = limit

                        seg_start = 0 if first else abs_start
                        first_visual_for_doc.setdefault(doc_idx, len(visual_lines))
                        visual_lines.append((doc_idx, seg_start, end))

                        body_offset = end - body_start
                        while body_offset < body_len and line.plain[body_start + body_offset] == " ":
                            body_offset += 1
                        first = False

                    continue

            if line.kind == "list" and line.prefix_len > 0 and line_len > line.prefix_len and self.left == 0:
                # First segment: full width; continuation: indented so rendered width fits
                cont_width = max(width - line.prefix_len, 1)
                seg_start = 0
                first_visual_for_doc.setdefault(doc_idx, len(visual_lines))
                limit = min(seg_start + width, line_len)
                end = limit
                if limit < line_len:
                    split = line.plain.rfind(" ", line.prefix_len, limit + 1)
                    if split > line.prefix_len:
                        end = split
                if end <= seg_start:
                    end = limit
                visual_lines.append((doc_idx, seg_start, end))
                next_start = end
                while next_start < line_len and line.plain[next_start] == " ":
                    next_start += 1
                while next_start < line_len:
                    limit = min(next_start + cont_width, line_len)
                    end = limit
                    if limit < line_len:
                        split = line.plain.rfind(" ", next_start, limit + 1)
                        if split > next_start:
                            end = split
                    if end <= next_start:
                        end = limit
                    visual_lines.append((doc_idx, next_start, end))
                    ns = end
                    while ns < line_len and line.plain[ns] == " ":
                        ns += 1
                    next_start = ns
                continue

                first_visual_for_doc.setdefault(doc_idx, len(visual_lines))
                visual_lines.append((doc_idx, line_len, line_len))
                continue

            while start < line_len:
                limit = min(start + width, line_len)
                end = limit
                if limit < line_len:
                    split = line.plain.rfind(" ", start, limit + 1)
                    if split > start:
                        end = split
                if end <= start:
                    end = limit
                first_visual_for_doc.setdefault(doc_idx, len(visual_lines))
                visual_lines.append((doc_idx, start, end))
                start = end
                while start < line_len and line.plain[start] == " ":
                    start += 1

            if line_len == 0:
                first_visual_for_doc.setdefault(doc_idx, len(visual_lines))
                visual_lines.append((doc_idx, 0, 0))

        return visual_lines, first_visual_for_doc

    def clamp_view(self) -> None:
        doc = self.current_document()
        cols, rows = terminal_size()
        visible = max(rows - 1, 1)
        self.left = max(0, self.left)
        max_width = max((ansi_visible_len(line.plain) for line in doc.display_lines), default=0)
        if max_width <= cols:
            self.left = 0
        else:
            self.left = clamp(self.left, 0, max_width - cols)

        visual_lines, _first_visual = self.build_visual_lines(cols)
        self.top = clamp(self.top, 0, max(len(visual_lines) - 1, 0))
        if len(visual_lines) <= visible:
            self.top = 0
        else:
            self.top = clamp(self.top, 0, len(visual_lines) - visible)

    def visible_matches(self) -> list[tuple[int, int, int]]:
        doc = self.current_document()
        if self.search_state.regex is None:
            return []
        matches: list[tuple[int, int, int]] = []
        for idx, line in enumerate(doc.display_lines):
            for start, end in line_matches(self.search_state.regex, line.plain):
                matches.append((idx, start, end))
        return matches

    def update_search(self, pattern: str, forward: bool) -> None:
        try:
            regex, ignore_case = compile_search(pattern)
        except re.error as exc:
            self.set_message(f"invalid regex: {exc}")
            return
        self.search_state.pattern = pattern
        self.search_state.regex = regex
        self.search_state.forward = forward
        self.search_state.ignore_case = ignore_case
        self.search_state.matches = self.visible_matches()
        self.search_state.current_index = -1
        self.jump_to_next_match(forward=forward)

    def jump_to_next_match(self, forward: Optional[bool] = None) -> None:
        if not self.search_state.matches:
            self.set_message("no matches")
            return
        direction = self.search_state.forward if forward is None else forward
        ordered = self.search_state.matches
        if self.search_state.current_index >= 0:
            step = 1 if direction else -1
            next_idx = (self.search_state.current_index + step) % len(ordered)
            self.search_state.current_index = next_idx
            self._goto_match(ordered[next_idx])
            return

        cols, _rows = terminal_size()
        visual_lines, _first_visual = self.build_visual_lines(cols)
        current_line = visual_lines[self.top][0] if visual_lines else 0
        if direction:
            for idx, (line_idx, _start, _end) in enumerate(ordered):
                if line_idx >= current_line:
                    self.search_state.current_index = idx
                    self._goto_match(ordered[idx])
                    return
            self.search_state.current_index = 0
            self._goto_match(ordered[0])
            return

        for idx in range(len(ordered) - 1, -1, -1):
            line_idx, _start, _end = ordered[idx]
            if line_idx <= current_line:
                self.search_state.current_index = idx
                self._goto_match(ordered[idx])
                return
        self.search_state.current_index = len(ordered) - 1
        self._goto_match(ordered[-1])

    def _goto_match(self, match: tuple[int, int, int]) -> None:
        self.push_jump()
        line_idx, start, _end = match
        cols, _rows = terminal_size()
        visual_lines, first_visual = self.build_visual_lines(cols)
        self.top = first_visual.get(line_idx, 0)
        seg_offset = start // max(cols, 1)
        self.top += seg_offset
        self.left = 0
        self.clamp_view()
        self.set_message(f"match at line {line_idx + 1}")

    def move(self, delta_lines: int = 0, delta_cols: int = 0) -> None:
        self.top += delta_lines
        self.left += delta_cols
        self.clamp_view()

    def page(self, direction: int) -> None:
        _cols, rows = terminal_size()
        step = max(rows - 1, 1)
        self.move(delta_lines=direction * step)

    def half_page(self, direction: int) -> None:
        _cols, rows = terminal_size()
        step = max((rows - 1) // 2, 1)
        self.move(delta_lines=direction * step)

    def jump_home(self) -> None:
        self.top = 0
        self.left = 0

    def jump_end(self) -> None:
        cols, rows = terminal_size()
        visual_lines, _first_visual = self.build_visual_lines(cols)
        visible = max(rows - 1, 1)
        self.top = max(len(visual_lines) - visible, 0)

    def next_file(self) -> None:
        if self.index + 1 < len(self.files):
            self._save_file_pos()
            self.index += 1
            self._load_file_pos()
        else:
            self.set_message("last file")

    def prev_file(self) -> None:
        if self.index > 0:
            self._save_file_pos()
            self.index -= 1
            self._load_file_pos()
        else:
            self.set_message("first file")

    def reset_files(self) -> None:
        self._save_file_pos()
        self.files = self.original_files.copy()
        self.index = 0
        self._load_file_pos()
        self.set_message("reset to argv files")

    def delete_current_file(self) -> None:
        if not self.files:
            return
        removed = self.files.pop(self.index)
        self.documents.pop(removed, None)
        if not self.files:
            self.running = False
            return
        if self.index >= len(self.files):
            self.index = len(self.files) - 1
        self._load_file_pos()

    def open_file(self, path: str) -> None:
        resolved = normalize_path(path, base=os.path.dirname(self.current_path()))
        if not os.path.exists(resolved):
            self.set_message(f"no such file: {resolved}")
            return
        self._save_file_pos()
        if resolved not in self.files:
            self.files.append(resolved)
        self.index = self.files.index(resolved)
        self._load_file_pos()

    def select_link(self, step: int) -> None:
        doc = self.current_document()
        if not doc.links:
            self.set_message("no links")
            return
        if self.selected_link_idx < 0:
            self.selected_link_idx = 0 if step > 0 else len(doc.links) - 1
        else:
            self.selected_link_idx = (self.selected_link_idx + step) % len(doc.links)
        link = doc.links[self.selected_link_idx]
        cols, _rows = terminal_size()
        _visual_lines, first_visual = self.build_visual_lines(cols)
        self.top = first_visual.get(link.line_index, 0) + (link.start // max(cols, 1))
        self.clamp_view()
        self.set_message(f"link {self.selected_link_idx + 1}/{len(doc.links)}")

    def follow_link(self) -> None:
        link = self.current_link()
        if link is None:
            self.set_message("no link selected")
            return
        if not link.intra:
            self.set_message("external links are not followed")
            return
        anchor = link.target[1:] if link.target.startswith("#") else link.target
        anchor = urllib.parse.unquote(anchor)
        doc = self.current_document()
        if anchor not in doc.anchors:
            self.set_message(f"anchor not found: {anchor}")
            return
        self.push_jump()
        cols, _rows = terminal_size()
        _visual_lines, first_visual = self.build_visual_lines(cols)
        self.top = first_visual.get(doc.anchors[anchor], 0)
        self.left = 0
        self.clamp_view()
        self.set_message(f"anchor {anchor}")

    def set_mark(self, name: str) -> None:
        self.marks[(self.current_path(), name)] = JumpPos(self.current_path(), self.top, self.left)
        self.set_message(f"mark {name} set")

    def jump_mark(self, name: str) -> None:
        pos = self.marks.get((self.current_path(), name))
        if pos is None:
            self.set_message(f"mark not found: {name}")
            return
        self.push_jump()
        self._restore_pos(pos)
        self.set_message(f"mark {name}")

    def render(self) -> None:
        doc = self.current_document()
        cols, rows = terminal_size()
        visible_rows = max(rows - 1, 1)
        self.clamp_view()
        visual_lines, _first_visual = self.build_visual_lines(cols)
        self.search_state.matches = self.visible_matches() if self.search_state.regex is not None else []
        sys.stdout.write(a.cls)
        sys.stdout.write(HIDE_CURSOR)
        sys.stdout.write(BASE_STYLE)
        selected = self.current_link()
        for row_offset in range(visible_rows):
            idx = self.top + row_offset
            if idx < len(visual_lines):
                doc_idx, seg_start, seg_end = visual_lines[idx]
                line = doc.display_lines[doc_idx]
                if line.kind == "hr":
                    rendered = a.rst + BASE_STYLE + RULE_STYLE + ("─" * max(cols, 1)) + a.rst
                else:
                    search_ranges = highlight_ranges_for_line(self.search_state.regex, line.plain)
                    rendered = render_line(line, seg_start, seg_end, search_ranges, selected)
                sys.stdout.write(rendered)
            sys.stdout.write("\n")
        view_bottom = min(self.top + visible_rows, len(visual_lines))
        at_end = view_bottom >= len(visual_lines)
        hint = ""
        if at_end:
            hint = "(END)"
            if self.index + 1 < len(self.files):
                hint = f"(END) - Next: {os.path.basename(self.files[self.index + 1])}"
        sys.stdout.write(
            format_status(
                doc,
                self.top,
                self.left,
                rows,
                cols,
                self.search_state,
                visual_lines,
                self.message,
                hint,
                file_index=self.index,
                file_count=len(self.files),
            )
        )
        sys.stdout.write(a.rst)
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()
        self.message = ""

    def handle_colon_command(self, cmd: str) -> None:
        cmd = cmd.strip()
        if not cmd:
            return
        if cmd.startswith("e"):
            arg = cmd[1:].strip()
            if not arg:
                self.set_message("missing file")
                return
            self.open_file(arg)
            return
        if cmd == "n":
            self.next_file()
            return
        if cmd == "p":
            self.prev_file()
            return
        if cmd == "x":
            self.reset_files()
            return
        if cmd == "d":
            self.delete_current_file()
            return
        self.set_message(f"unknown command: :{cmd}")

    def handle_search_command(self, forward: bool) -> None:
        assert self.keys is not None
        pattern = input_line(self.keys, "/" if forward else "?")
        if pattern is None:
            self.set_message("search cancelled")
            return
        if not pattern:
            self.set_message("empty search")
            return
        self.update_search(pattern, forward)

    def handle_command_mode(self) -> None:
        assert self.keys is not None
        cols, _rows = terminal_size()
        sys.stdout.write("\r" + status_text(cols, ":") + "\x1b[K")
        sys.stdout.flush()
        first = self.keys.read_key_raw(timeout=None)
        if first in ("#ESC", "#LF", "#CR"):
            return
        if first == "n":
            self.next_file()
            return
        if first == "p":
            self.prev_file()
            return
        if first == "x":
            self.reset_files()
            return
        if first == "d":
            self.delete_current_file()
            return
        if first == "e":
            arg = input_line(self.keys, ":e ", initial="")
            if arg is not None and arg.strip():
                self.open_file(arg.strip())
            return
        initial = first if (len(first) == 1 and first.isprintable()) else ""
        cmd = input_line(self.keys, ":", initial=initial)
        if cmd is None:
            self.set_message("command cancelled")
            return
        self.handle_colon_command(cmd)

    def process_key(self, key: str) -> None:
        if key == "q" or key == "#C-C":
            self.running = False
            return
        if key == "h":
            assert self.keys is not None
            render_help_screen(os.path.basename(self.current_path()), self.keys)
            self.resize_pending = True
            return
        if key == "#C-L":
            self.resize_pending = True
            return
        if key in ("#UP",):
            self.move(delta_lines=-1)
            return
        if key in ("#DN",):
            self.move(delta_lines=1)
            return
        if key in ("#RT",):
            self.move(delta_cols=10)
            return
        if key in ("#LT",):
            self.move(delta_cols=-10)
            return
        if key in ("#PUP",):
            self.page(-1)
            return
        if key in ("#PDN",):
            self.page(1)
            return
        if key == " ":
            self.page(1)
            return
        if key == "d":
            self.half_page(1)
            return
        if key == "u":
            self.half_page(-1)
            return
        if key == "f":
            self.page(1)
            return
        if key == "b":
            self.page(-1)
            return
        if key in ("#HOM",):
            self.jump_home()
            return
        if key in ("#END",):
            self.jump_end()
            return
        if key == "<":
            self.jump_home()
            return
        if key == ">":
            self.jump_end()
            return
        if key == "/":
            self.handle_search_command(True)
            return
        if key == "?":
            self.handle_search_command(False)
            return
        if key == "n":
            if not self.search_state.pattern:
                self.set_message("no previous search")
            else:
                self.jump_to_next_match()
            return
        if key == "N":
            if not self.search_state.pattern:
                self.set_message("no previous search")
            else:
                self.jump_to_next_match(not self.search_state.forward)
            return
        if key == "m":
            self.pending_mark = ""
            return
        if key == "'":
            self.pending_quote = True
            return
        if key == "#C-X":
            if self.pending_ctrl_x:
                self.pending_ctrl_x = False
                self.go_back_jump()
            else:
                self.pending_ctrl_x = True
            return
        if key == ":":
            self.handle_command_mode()
            return
        if key == "#TAB":
            self.select_link(1)
            return
        if key in ("[Z", "#S-TAB"):
            self.select_link(-1)
            return
        if key in ("#LF", "#CR"):
            if self.current_link() is not None:
                self.follow_link()
                self.selected_link_idx = -1
            else:
                self.move(delta_lines=1)
            return
        if key == ".":
            self.set_message(".")
            return
        if len(key) == 1 and key.isprintable():
            self.set_message(f"ignored: {key}")

    def run(self) -> int:
        if not self.files:
            print("less-md: no input files", file=sys.stderr)
            return 1

        def on_winch(_signum: int, _frame) -> None:
            self.resize_pending = True

        try:
            signal.signal(signal.SIGWINCH, on_winch)
        except Exception:
            pass

        with ReadKeyRaw() as keys:
            self.keys = keys
            sys.stdout.write(ALT_SCREEN_ON)
            sys.stdout.flush()
            try:
                while self.running:
                    if self.resize_pending:
                        self.resize_pending = False
                    self.render()
                    key = keys.read_key_raw(timeout=None)
                    if key == "#TIMEOUT":
                        continue
                    if self.pending_mark == "":
                        if len(key) == 1 and key.isalpha():
                            self.set_mark(key)
                        else:
                            self.set_message("expected mark letter")
                        self.pending_mark = None
                        continue
                    if self.pending_quote:
                        if key == "'":
                            self.go_back_jump()
                        elif len(key) == 1 and key.isalpha():
                            self.jump_mark(key)
                        else:
                            self.set_message("expected mark letter")
                        self.pending_quote = False
                        continue
                    if self.pending_ctrl_x:
                        self.pending_ctrl_x = False
                        if key == "#C-X":
                            self.go_back_jump()
                            continue
                    self.process_key(key)
            finally:
                sys.stdout.write(ALT_SCREEN_OFF)
                sys.stdout.write(SHOW_CURSOR)
                sys.stdout.write(a.rst)
                sys.stdout.flush()
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="A small markdown-aware less-like pager")
    parser.add_argument("files", nargs="*", help="Files to view")
    args = parser.parse_args()
    pager = Pager(args.files)
    return pager.run()


if __name__ == "__main__":
    raise SystemExit(main())
