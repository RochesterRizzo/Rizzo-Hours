#!/usr/bin/env python3
"""Convert a tagged ECON 238 PDF announcement into a Course Update page.

The Fall 2025 PDFs were created from Word with Adobe PDFMaker. Their tagged
structure preserves paragraphs, list bodies, links, type emphasis, colors, and
figures. This importer uses those tags instead of flattening the source into
plain text or page screenshots.
"""

from __future__ import annotations

import argparse
import html as html_lib
import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz
import pdfplumber


SECTION_TITLES = {
    "course": "Course timing and readings",
    "assignments": "Assignments and due dates",
    "projects": "Course projects",
    "admin": "Other class administration and availability",
    "events": "Upcoming Special Events",
    "attention": "Some Things That Captured Our Attention",
    "chart": "Chart of the Week",
    "photo": "Photo of the Week",
    "culture": "Film, music, cultural item of the Week",
    "quote": "They Said It",
}

SECTION_ORDER = [
    "course",
    "assignments",
    "projects",
    "admin",
    "events",
    "attention",
    "chart",
    "photo",
    "culture",
    "quote",
]

NUMBER_WORDS = {
    1: "One",
    2: "Two",
    3: "Three",
    4: "Four",
    5: "Five",
    6: "Six",
    7: "Seven",
    8: "Eight",
    9: "Nine",
    10: "Ten",
    11: "Eleven",
    12: "Twelve",
    13: "Thirteen",
}

TITLE_RE = re.compile(
    r"^WEEKLY\s+REMINDERS/ANNOUNCEMENTS\s*[–-]\s*Eco\s*238,\s*Week\s+\d+",
    re.I,
)


@dataclass
class Atom:
    kind: str
    tag: str
    page: int
    mcid: int
    chars: list[dict] = field(default_factory=list)
    image_name: str | None = None
    image_href: str | None = None
    top: float = 0.0
    left: float = 0.0

    @property
    def text(self) -> str:
        return "".join(char.get("text", "") for char in self.chars)


@dataclass
class Unit:
    kind: str
    tag: str
    atoms: list[Atom] = field(default_factory=list)
    image_name: str | None = None
    image_href: str | None = None
    section_href: str | None = None

    @property
    def chars(self) -> list[dict]:
        return [char for atom in self.atoms for char in atom.chars]

    @property
    def text(self) -> str:
        return "".join(atom.text for atom in self.atoms)


def normalize(text: str) -> str:
    return " ".join(text.replace("\uf0a7", "•").split())


def rect_overlap(a: tuple[float, float, float, float], b: fitz.Rect) -> float:
    x0 = max(a[0], b.x0)
    y0 = max(a[1], b.y0)
    x1 = min(a[2], b.x1)
    y1 = min(a[3], b.y1)
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def link_for_bbox(links: list[dict], bbox: tuple[float, float, float, float]) -> str | None:
    candidates = [
        (rect_overlap(bbox, link["from"]), link.get("uri"))
        for link in links
        if link.get("kind") == fitz.LINK_URI and link.get("uri")
    ]
    candidates = [candidate for candidate in candidates if candidate[0] > 0]
    return max(candidates, default=(0, None))[1]


def image_bytes_for_bbox(page: fitz.Page, bbox: tuple[float, float, float, float]):
    best = None
    best_score = 0.0
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 1:
            continue
        score = rect_overlap(bbox, fitz.Rect(block["bbox"]))
        if score > best_score:
            best = block
            best_score = score
    if not best:
        raise ValueError(f"Could not match PDF figure at {bbox}")
    return best["image"], best["ext"]


def extract_atoms(source: Path, assets: Path) -> list[Atom]:
    assets.mkdir(parents=True, exist_ok=True)
    atoms: list[Atom] = []
    image_counter = 0

    fitz_doc = fitz.open(source)
    with pdfplumber.open(source) as plumber_doc:
        for page_index, plumber_page in enumerate(plumber_doc.pages):
            fitz_page = fitz_doc[page_index]
            links = fitz_page.get_links()
            by_mcid: dict[int, list[dict]] = {}
            tags: dict[int, str] = {}
            order: list[int] = []
            for char in plumber_page.chars:
                mcid = char.get("mcid")
                if mcid is None:
                    continue
                if mcid not in by_mcid:
                    by_mcid[mcid] = []
                    tags[mcid] = char.get("tag") or "Span"
                    order.append(mcid)
                by_mcid[mcid].append(char)

            images_by_mcid = {
                image.get("mcid"): image
                for image in plumber_page.images
                if image.get("mcid") is not None
            }
            for mcid in images_by_mcid:
                if mcid not in order:
                    order.append(mcid)

            page_atoms: list[Atom] = []
            for mcid in order:
                if mcid in images_by_mcid:
                    image = images_by_mcid[mcid]
                    bbox = (
                        float(image["x0"]),
                        float(image["top"]),
                        float(image["x1"]),
                        float(image["bottom"]),
                    )
                    data, extension = image_bytes_for_bbox(fitz_page, bbox)
                    image_counter += 1
                    filename = f"image{image_counter}.{extension}"
                    (assets / filename).write_bytes(data)
                    page_atoms.append(
                        Atom(
                            kind="image",
                            tag="Figure",
                            page=page_index,
                            mcid=mcid,
                            image_name=filename,
                            image_href=link_for_bbox(links, bbox),
                            top=bbox[1],
                            left=bbox[0],
                        )
                    )
                    continue

                chars = by_mcid.get(mcid, [])
                if not chars:
                    continue
                tag = tags[mcid]
                if tag == "Link":
                    bbox = (
                        min(char["x0"] for char in chars),
                        min(char["top"] for char in chars),
                        max(char["x1"] for char in chars),
                        max(char["bottom"] for char in chars),
                    )
                    uri = link_for_bbox(links, bbox)
                    for char in chars:
                        char["uri"] = uri
                page_atoms.append(
                    Atom(
                        kind="text",
                        tag=tag,
                        page=page_index,
                        mcid=mcid,
                        chars=chars,
                        top=min(char["top"] for char in chars),
                        left=min(char["x0"] for char in chars),
                    )
                )
            atoms.extend(sorted(page_atoms, key=lambda atom: (round(atom.top, 1), atom.left, atom.mcid)))

    fitz_doc.close()
    return atoms


def atoms_to_units(atoms: list[Atom]) -> list[Unit]:
    units: list[Unit] = []
    current: Unit | None = None
    for atom in atoms:
        if atom.kind == "image":
            units.append(
                Unit(
                    kind="image",
                    tag="Figure",
                    image_name=atom.image_name,
                    image_href=atom.image_href,
                )
            )
            current = None
            continue

        if atom.tag in {"P", "LBody"} or current is None:
            current = Unit(kind="text", tag=atom.tag, atoms=[atom])
            units.append(current)
        else:
            current.atoms.append(atom)
    return [unit for unit in units if unit.kind == "image" or normalize(unit.text)]


def color_hex(char: dict) -> str | None:
    color = char.get("non_stroking_color")
    if color is None:
        return None
    if not isinstance(color, tuple):
        color = (color,)
    if len(color) == 1:
        rgb = (color[0],) * 3
    elif len(color) == 3:
        rgb = color
    elif len(color) == 4:
        c, m, y, k = color
        rgb = (1 - min(1, c + k), 1 - min(1, m + k), 1 - min(1, y + k))
    else:
        return None
    values = tuple(max(0, min(255, round(value * 255))) for value in rgb)
    result = "#%02x%02x%02x" % values
    return None if result in {"#000000", "#010101"} else result


def char_style(char: dict) -> tuple:
    font = char.get("fontname", "").lower()
    return (
        "bold" in font,
        "italic" in font or "oblique" in font,
        float(char.get("size") or 0) < 9.5,
        color_hex(char),
        char.get("uri"),
    )


def render_run(text: str, style: tuple) -> str:
    bold, italic, superscript, color, uri = style
    value = html_lib.escape(text)
    if color:
        value = f'<span class="source-color" style="color: {color}">{value}</span>'
    if italic:
        value = f"<em>{value}</em>"
    if bold:
        value = f"<strong>{value}</strong>"
    if superscript:
        value = f"<sup>{value}</sup>"
    if uri:
        value = f'<a href="{html_lib.escape(uri, quote=True)}">{value}</a>'
    return value


def render_chars(chars: list[dict], skip_characters: int = 0) -> str:
    if skip_characters:
        remaining = skip_characters
        trimmed: list[dict] = []
        for char in chars:
            if remaining:
                remaining -= 1
                continue
            trimmed.append(char)
        chars = trimmed

    runs: list[tuple[tuple, str]] = []
    for char in chars:
        style = char_style(char)
        text = char.get("text", "")
        if runs and runs[-1][0] == style:
            runs[-1] = (style, runs[-1][1] + text)
        else:
            runs.append((style, text))
    return "".join(render_run(text, style) for style, text in runs).strip()


def list_level(unit: Unit) -> int:
    x0 = min((char["x0"] for char in unit.chars if char.get("text", "").strip()), default=90)
    return max(0, min(3, round((x0 - 90) / 36)))


def strip_marker(unit: Unit) -> tuple[int, str]:
    text = unit.text.lstrip()
    leading_spaces = len(unit.text) - len(text)
    match = re.match(r"(?:[•o\uf0a7]|\d+[.)]|[a-z][.)])\s+", text, re.I)
    if not match:
        return leading_spaces, ""
    return leading_spaces + match.end(), match.group(0).strip()


def section_marker(text: str) -> tuple[str | None, str | None, bool]:
    cleaned = normalize(text)
    lowered = cleaned.lower()
    if TITLE_RE.match(cleaned) or lowered == "class updates":
        return None, None, True
    if lowered.startswith("topics and readings this week"):
        label = re.match(r"Topics and Readings This Week\s*:?\s*", cleaned, re.I)
        return "course", label.group(0) if label else None, False
    if lowered.startswith("for tuesday’s class") or lowered.startswith("for tuesday's class"):
        return "course", None, False
    if lowered.startswith("weekly assignment") or lowered.startswith("week one assignment"):
        label = re.match(r"(?:Weekly|Week One) Assignment\s*:?\s*", cleaned, re.I)
        return "assignments", label.group(0) if label else None, False
    if lowered.startswith("mark your class calendars"):
        return "admin", None, False
    if lowered.startswith(("eett ", "eett:", "group project cheat sheet", "form your groups")):
        return "projects", None, False
    if lowered.startswith(("ta office hours", "my availability", "discussion portions")):
        return "admin", None, False
    if lowered == "upcoming special events" or lowered.startswith("upcoming special events "):
        return "events", "UPCOMING SPECIAL EVENTS", lowered == "upcoming special events"
    if lowered.startswith(("some things that captured our attention", "some things that capture our attention")):
        label = re.match(r"Some Things That Capture(?:d)? Our Attention\s*:?\s*", cleaned, re.I)
        remainder = cleaned[len(label.group(0)):] if label else cleaned
        return "attention", label.group(0) if label else None, not remainder
    if lowered.startswith("chart(s) of the week") or lowered.startswith("chart of the week"):
        label = re.match(r"Chart(?:\(s\))? of the Week\s*:?\s*", cleaned, re.I)
        return "chart", label.group(0) if label else None, False
    if lowered.startswith(("photo of the week", "photo(s) of the week")):
        label = re.match(r"Photo(?:\(s\))? of the Week\s*:?\s*", cleaned, re.I)
        return "photo", label.group(0) if label else None, False
    if lowered.startswith("video/documentary/book/cartoon"):
        label = re.match(
            r"Video/Documentary/Book/Cartoon,?\s*(?:Etc\.?\s*)?of the Week\s*:?\s*",
            cleaned,
            re.I,
        )
        return "culture", label.group(0) if label else None, False
    return None, None, False


def trim_prefix_chars(unit: Unit, prefix: str | None) -> int:
    if not prefix:
        return 0
    compact_prefix = normalize(prefix)
    raw = unit.text
    position = 0
    seen = ""
    while position < len(raw) and len(normalize(seen)) < len(compact_prefix):
        seen += raw[position]
        position += 1
    while position < len(raw) and raw[position].isspace():
        position += 1
    return position


def is_heading_unit(unit: Unit) -> bool:
    text = normalize(unit.text).rstrip(":")
    return text.lower() in {
        "group project cheat sheet",
        "ta office hours and info",
        "for tuesday’s class",
        "for tuesday's class",
    }


def mostly_red(unit: Unit) -> bool:
    colored = [color_hex(char) for char in unit.chars if char.get("text", "").strip()]
    if not colored:
        return False
    red = sum(1 for color in colored if color and int(color[1:3], 16) > 140 and int(color[3:5], 16) < 100)
    return red / len(colored) > 0.35


def organize(units: list[Unit]):
    sections: dict[str, list[tuple[Unit, int]]] = {key: [] for key in SECTION_ORDER}
    current = "course"
    preserved_culture_href = None
    for unit in units:
        if unit.kind == "image":
            sections[current].append((unit, 0))
            continue
        if normalize(unit.text).replace(" ", "") in {"*****", "******", "*******"}:
            current = "quote"
            continue
        section, prefix, skip = section_marker(unit.text)
        if section:
            current = section
        if skip:
            continue
        skip_chars = trim_prefix_chars(unit, prefix)
        if current == "culture" and prefix:
            preserved_culture_href = next(
                (char.get("uri") for char in unit.chars[:skip_chars] if char.get("uri")),
                preserved_culture_href,
            )
        if normalize(unit.text[skip_chars:]):
            sections[current].append((unit, skip_chars))
    if preserved_culture_href:
        for unit, _skip in sections["culture"]:
            if unit.kind == "image":
                if unit.image_href and unit.image_href != preserved_culture_href:
                    sections["culture"][0][0].section_href = preserved_culture_href
                else:
                    unit.image_href = preserved_culture_href
                break
    return {key: values for key, values in sections.items() if values}


def render_section_items(items: list[tuple[Unit, int]], week: int) -> str:
    output: list[str] = []
    list_open = False
    for unit, skip in items:
        if unit.kind == "image":
            if list_open:
                output.append("</ul>")
                list_open = False
            image = (
                f'<img src="assets/{unit.image_name}" loading="lazy" '
                f'alt="Image from the original Week {week} Environmental Economics course update">'
            )
            if unit.image_href:
                image = f'<a href="{html_lib.escape(unit.image_href, quote=True)}">{image}</a>'
            output.append(f"<p>{image}</p>")
            continue

        if unit.tag == "LBody":
            if not list_open:
                output.append('<ul class="source-list">')
                list_open = True
            marker_skip, marker = strip_marker(unit)
            body = render_chars(unit.chars, max(skip, marker_skip))
            marker_html = f'<span class="source-list__marker">{html_lib.escape(marker)}</span> ' if marker and marker not in {"•", "o", "\uf0a7"} else ""
            output.append(f'<li class="source-list__level-{list_level(unit)}">{marker_html}{body}</li>')
            continue

        if list_open:
            output.append("</ul>")
            list_open = False
        body = render_chars(unit.chars, skip)
        if not body:
            continue
        if is_heading_unit(unit):
            output.append(f"<h3>{body}</h3>")
        else:
            class_name = ' class="source-deadline"' if mostly_red(unit) else ""
            output.append(f"<p{class_name}>{body}</p>")
    if list_open:
        output.append("</ul>")
    return "\n".join(output)


def page_html(week: int, date_range: str, sections: dict[str, list[tuple[Unit, int]]]) -> str:
    week_word = NUMBER_WORDS[week]
    nav = "\n".join(
        f'          <li><a href="#{section_id}">{SECTION_TITLES[section_id]}</a></li>'
        for section_id in SECTION_ORDER
        if section_id in sections
    )
    def section_heading(section_id: str) -> str:
        href = next(
            (unit.section_href for unit, _skip in sections[section_id] if unit.section_href),
            None,
        )
        title = SECTION_TITLES[section_id]
        return f'<a class="section-source-link" href="{html_lib.escape(href, quote=True)}">{title}</a>' if href else title

    content = "\n\n".join(
        f'''        <section class="issue-section source-update{' attention-archive' if section_id == 'attention' else ''}{' visual-archive' if section_id in {'chart', 'photo', 'culture'} else ''}{' quote-archive' if section_id == 'quote' else ''}" id="{section_id}">
          <h2>{section_heading(section_id)}</h2>
{render_section_items(sections[section_id], week)}
        </section>'''
        for section_id in SECTION_ORDER
        if section_id in sections
    )
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Week {week_word} Course Update | Environmental Economics Fall 2025</title>
  <meta name="description" content="ECON 238 Environmental Economics course update for {date_range}.">
  <link rel="stylesheet" href="../../../assets/weekly.css">
</head>
<body id="top">
  <a class="skip-link" href="#main">Skip to the course update</a>
  <div class="site-shell">
    <header class="site-header">
      <div class="site-header__bar">
        <a href="../../../../index.html">← Office Hours &amp; Student Information</a>
        <a href="../index.html">Fall 2025 archive</a>
      </div>
      <div class="issue-masthead issue-masthead--archive issue-masthead--environmental">
        <p class="kicker">ECON 238 · Environmental Economics · Fall 2025</p>
        <h1>Week {week_word} Course Update</h1>
        <div class="issue-masthead__meta"><span>{date_range}</span></div>
      </div>
    </header>
    <main class="issue-shell" id="main">
      <nav class="toc" aria-label="In this update">
        <h2>In this update</h2>
        <ol>
{nav}
        </ol>
      </nav>
      <article class="issue-content">
{content}
      </article>
    </main>
    <footer class="site-footer">
      <p><strong>Environmental Economics Course Updates</strong><br>ECON 238 · Fall 2025</p>
      <p><a href="../index.html">Return to the Fall 2025 archive</a></p>
    </footer>
  </div>
  <a class="back-to-top" href="#top" aria-label="Back to top">↑</a>
</body>
</html>
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--date-range", required=True)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    assets = args.output / "assets"
    atoms = extract_atoms(args.source, assets)
    sections = organize(atoms_to_units(atoms))
    (args.output / "index.html").write_text(
        page_html(args.week, args.date_range, sections), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
