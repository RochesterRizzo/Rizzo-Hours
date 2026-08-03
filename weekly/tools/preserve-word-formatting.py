#!/usr/bin/env python3
"""Restore meaningful Word text colors in an imported Course Update.

Pandoc preserves links, bold, italics, lists, and images well, but it drops
run-level Word colors. This helper uses LibreOffice's HTML export only as a
formatting reference, aligns that text with an already structured Course
Update page, and restores manual colors without importing Word fonts, sizes,
spacing, or page layout.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from lxml import etree, html


WORD_RE = re.compile(r"\w+(?:[’']\w+)*", re.UNICODE)

# These colors are Word's automatic body/link colors. The website supplies
# those consistently. All other explicit source colors are treated as manual.
AUTOMATIC_COLORS = {"#000000", "#0563c1", "#954f72"}


def text_slots(element: etree._Element):
    """Return mutable text/tail slots and their offsets in text_content()."""
    slots = []
    position = 0

    def visit(node: etree._Element):
        nonlocal position
        if node.text:
            slots.append((node, "text", node.text, position, position + len(node.text)))
            position += len(node.text)
        for child in node:
            visit(child)
            if child.tail:
                slots.append(
                    (child, "tail", child.tail, position, position + len(child.tail))
                )
                position += len(child.tail)

    visit(element)
    return slots, "".join(slot[2] for slot in slots)


def effective_source_color(owner: etree._Element, attribute: str):
    node = owner if attribute == "text" else owner.getparent()
    while node is not None:
        if node.tag == "font" and node.get("color"):
            return node.get("color").lower()
        node = node.getparent()
    return None


def tokens(element: etree._Element, source: bool = False):
    slots, raw_text = text_slots(element)
    result = []
    for match in WORD_RE.finditer(raw_text):
        color = None
        if source:
            votes = Counter()
            for owner, attribute, _text, start, end in slots:
                overlap_start = max(start, match.start())
                overlap_end = min(end, match.end())
                if overlap_start >= overlap_end:
                    continue
                candidate = effective_source_color(owner, attribute)
                if candidate and candidate not in AUTOMATIC_COLORS:
                    votes[candidate] += overlap_end - overlap_start
            if votes:
                color = votes.most_common(1)[0][0]
        result.append((match.group(0).lower(), match.start(), match.end(), color))
    return result


def source_blocks(document: etree._Element):
    return [element for element in document.xpath("//body/*") if tokens(element)]


def target_blocks(document: etree._Element):
    sections = document.xpath(
        '//section[contains(concat(" ", normalize-space(@class), " "), '
        '" source-update ")]'
    )
    return [
        element
        for section in sections
        for element in section
        if element.tag != "h2" and tokens(element)
    ]


def unwrap_previous_colors(document: etree._Element):
    for span in document.xpath(
        '//span[contains(concat(" ", normalize-space(@class), " "), '
        '" source-color ")]'
    ):
        span.drop_tag()


def best_source_match(target, candidates):
    target_words = [token[0] for token in tokens(target)]
    best_score = -1.0
    best = None
    best_tokens = None
    for source in candidates:
        source_tokens = tokens(source, source=True)
        score = SequenceMatcher(
            None,
            [token[0] for token in source_tokens],
            target_words,
            autojunk=False,
        ).ratio()
        if score > best_score:
            best_score = score
            best = source
            best_tokens = source_tokens
    return best_score, best, best_tokens


def color_ranges(source_token_list, target_token_list):
    matcher = SequenceMatcher(
        None,
        [token[0] for token in source_token_list],
        [token[0] for token in target_token_list],
        autojunk=False,
    )
    source_to_target = {
        source_start + offset: target_start + offset
        for operation, source_start, source_end, target_start, _target_end
        in matcher.get_opcodes()
        if operation == "equal"
        for offset in range(source_end - source_start)
    }

    colored_target_tokens = {}
    for source_index, source_token in enumerate(source_token_list):
        color = source_token[3]
        target_index = source_to_target.get(source_index)
        if color and target_index is not None:
            colored_target_tokens[target_index] = color

    ranges = []
    active_start = None
    active_end = None
    active_color = None
    previous_index = None
    for target_index in sorted(colored_target_tokens):
        color = colored_target_tokens[target_index]
        start, end = target_token_list[target_index][1:3]
        if (
            active_start is not None
            and color == active_color
            and target_index == previous_index + 1
        ):
            active_end = end
        else:
            if active_start is not None:
                ranges.append((active_start, active_end, active_color))
            active_start, active_end, active_color = start, end, color
        previous_index = target_index
    if active_start is not None:
        ranges.append((active_start, active_end, active_color))
    return ranges, len(colored_target_tokens)


def replace_text_slot(owner, attribute, pieces):
    """Replace one text/tail slot with text and source-color spans."""
    if attribute == "text":
        owner.text = pieces[0][1] if pieces and pieces[0][0] is None else ""
        insertion_index = 0
        start_at = 1 if pieces and pieces[0][0] is None else 0
        previous_span = None
        for color, text in pieces[start_at:]:
            if color is None:
                if previous_span is None:
                    owner.text = (owner.text or "") + text
                else:
                    previous_span.tail = (previous_span.tail or "") + text
                continue
            span = etree.Element("span", {"class": "source-color", "style": f"color: {color}"})
            span.text = text
            owner.insert(insertion_index, span)
            insertion_index += 1
            previous_span = span
        return

    parent = owner.getparent()
    if parent is None:
        return
    owner.tail = pieces[0][1] if pieces and pieces[0][0] is None else ""
    insertion_index = parent.index(owner) + 1
    start_at = 1 if pieces and pieces[0][0] is None else 0
    previous_span = None
    for color, text in pieces[start_at:]:
        if color is None:
            if previous_span is None:
                owner.tail = (owner.tail or "") + text
            else:
                previous_span.tail = (previous_span.tail or "") + text
            continue
        span = etree.Element("span", {"class": "source-color", "style": f"color: {color}"})
        span.text = text
        parent.insert(insertion_index, span)
        insertion_index += 1
        previous_span = span


def apply_ranges(element: etree._Element, ranges):
    slots, _raw_text = text_slots(element)
    intervals_by_slot = defaultdict(list)
    for range_start, range_end, color in ranges:
        for slot_index, (_owner, _attribute, _text, start, end) in enumerate(slots):
            overlap_start = max(range_start, start)
            overlap_end = min(range_end, end)
            if overlap_start < overlap_end:
                intervals_by_slot[slot_index].append(
                    (overlap_start - start, overlap_end - start, color)
                )

    for slot_index in sorted(intervals_by_slot, reverse=True):
        owner, attribute, text, _start, _end = slots[slot_index]
        intervals = sorted(intervals_by_slot[slot_index])
        pieces = []
        cursor = 0
        for start, end, color in intervals:
            if start > cursor:
                pieces.append((None, text[cursor:start]))
            pieces.append((color, text[start:end]))
            cursor = end
        if cursor < len(text):
            pieces.append((None, text[cursor:]))
        replace_text_slot(owner, attribute, pieces)


def convert_source(source_path: Path, output_directory: Path):
    profile = output_directory / "libreoffice-profile"
    profile.mkdir()
    command = [
        "soffice",
        "--headless",
        f"-env:UserInstallation=file://{profile}",
        "--convert-to",
        "html",
        "--outdir",
        str(output_directory),
        str(source_path.resolve()),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    candidates = [
        path
        for path in output_directory.glob("*.html")
        if path.name != source_path.with_suffix(".html").name or path.is_file()
    ]
    if not candidates:
        raise RuntimeError(f"LibreOffice did not create HTML for {source_path}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Original DOCX or RTF update")
    parser.add_argument("page", type=Path, help="Structured Course Update index.html")
    args = parser.parse_args()

    if not args.source.is_file():
        parser.error(f"source not found: {args.source}")
    if not args.page.is_file():
        parser.error(f"page not found: {args.page}")

    target_document = html.parse(str(args.page)).getroot()
    unwrap_previous_colors(target_document)

    with tempfile.TemporaryDirectory(prefix="course-update-format-") as temporary:
        converted = convert_source(args.source, Path(temporary))
        source_document = html.parse(str(converted)).getroot()

        candidates = source_blocks(source_document)
        blocks_matched = 0
        colored_tokens = 0
        for target in target_blocks(target_document):
            score, _source, source_token_list = best_source_match(target, candidates)
            if score < 0.72:
                continue
            target_token_list = tokens(target)
            ranges, matched_colored_tokens = color_ranges(
                source_token_list, target_token_list
            )
            if ranges:
                apply_ranges(target, ranges)
                colored_tokens += matched_colored_tokens
            blocks_matched += 1

    rendered = html.tostring(
        target_document,
        encoding="unicode",
        method="html",
        doctype="<!DOCTYPE html>",
        pretty_print=False,
    )
    args.page.write_text(rendered + "\n", encoding="utf-8")
    print(
        f"{args.page}: matched {blocks_matched} content blocks; "
        f"restored color to {colored_tokens} words"
    )


if __name__ == "__main__":
    main()
