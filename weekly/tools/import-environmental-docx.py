#!/usr/bin/env python3
"""Convert an ECON 238 Word announcement into the Course Update layout."""

from __future__ import annotations

import argparse
import copy
import html as html_lib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from lxml import etree, html


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
SECTION_ORDER = list(SECTION_TITLES)
NUMBER_WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten", 11: "Eleven", 12: "Twelve", 13: "Thirteen"}


def text(element: etree._Element) -> str:
    return " ".join(element.text_content().split())


def marker(value: str) -> tuple[str | None, str | None, bool]:
    lowered = value.lower()
    if "weekly reminders/announcements" in lowered or lowered == "class updates":
        return None, None, True
    if lowered.startswith("topics and readings this week"):
        return "course", "Topics and Readings This Week", False
    if lowered.startswith(("weekly assignment", "week one assignment")):
        return "assignments", "Weekly Assignment", False
    if lowered.startswith(("eett ", "eett:", "group project cheat sheet", "form your groups")):
        return "projects", None, False
    if lowered.startswith(("ta office hours", "my availability", "discussion portions")):
        return "admin", None, False
    if lowered == "upcoming special events":
        return "events", None, True
    if lowered.startswith(("some things that captured our attention", "some things that capture our attention")):
        return "attention", None, lowered.rstrip(":") in {"some things that captured our attention", "some things that capture our attention"}
    if lowered.startswith(("chart(s) of the week", "chart of the week")):
        match = re.match(r"Chart(?:\(s\))? of the Week\s*:?\s*", value, re.I)
        return "chart", match.group(0) if match else None, False
    if lowered.startswith(("photo of the week", "photo(s) of the week")):
        match = re.match(r"Photo(?:\(s\))? of the Week\s*:?\s*", value, re.I)
        return "photo", match.group(0) if match else None, False
    if lowered.startswith("video/documentary/book/cartoon"):
        match = re.match(
            r"Video/Documentary/Book/Cartoon,?\s*(?:Etc\.?\s*)?of the Week\s*:?\s*",
            value,
            re.I,
        )
        return "culture", match.group(0) if match else None, False
    return None, None, False


def remove_prefix(element: etree._Element, prefix: str | None) -> None:
    if not prefix:
        return
    remaining = len(prefix)
    slots = []
    if element.text:
        slots.append((element, "text"))
    for child in element.iterdescendants():
        if child.text:
            slots.append((child, "text"))
        if child.tail:
            slots.append((child, "tail"))
    for owner, attribute in slots:
        value = getattr(owner, attribute) or ""
        if remaining >= len(value):
            setattr(owner, attribute, "")
            remaining -= len(value)
            continue
        setattr(owner, attribute, value[remaining:].lstrip(" :–-"))
        break


def normalize_media(elements, output_assets: Path, media_root: Path) -> None:
    output_assets.mkdir(parents=True, exist_ok=True)
    for element in elements:
        for image in element.xpath(".//img"):
            source = Path(image.get("src", ""))
            if not source.is_absolute():
                source = media_root / source
            if not source.is_file():
                raise FileNotFoundError(source)
            destination = output_assets / source.name
            shutil.copy2(source, destination)
            image.set("src", f"assets/{destination.name}")
            image.attrib.pop("style", None)
            image.set("loading", "lazy")
            image.set("alt", "Image from the original Week 9 Environmental Economics course update")


def serialize(elements) -> str:
    return "\n".join(html.tostring(element, encoding="unicode", method="html") for element in elements)


def make_page(week: int, date_range: str, sections) -> str:
    word = NUMBER_WORDS[week]
    nav = "\n".join(
        f'          <li><a href="#{key}">{SECTION_TITLES[key]}</a></li>'
        for key in SECTION_ORDER if sections[key]
    )
    bodies = []
    for key in SECTION_ORDER:
        if not sections[key]:
            continue
        classes = ["issue-section", "source-update"]
        if key == "attention": classes.append("attention-archive")
        if key in {"chart", "photo", "culture"}: classes.append("visual-archive")
        if key == "quote": classes.append("quote-archive")
        bodies.append(f'''        <section class="{' '.join(classes)}" id="{key}">
          <h2>{SECTION_TITLES[key]}</h2>
{serialize(sections[key])}
        </section>''')
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Week {word} Course Update | Environmental Economics Fall 2025</title>
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
        <h1>Week {word} Course Update</h1>
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
{chr(10).join(bodies)}
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

    with tempfile.TemporaryDirectory(prefix="environmental-docx-") as tmp:
        tmp_path = Path(tmp)
        media = tmp_path / "media"
        raw = tmp_path / "raw.html"
        subprocess.run([
            "pandoc", str(args.source), "-f", "docx", "-t", "html5",
            f"--extract-media={media}", "-o", str(raw)
        ], check=True)
        fragment = html.fragment_fromstring(raw.read_text(encoding="utf-8"), create_parent="div")
        elements = [copy.deepcopy(child) for child in fragment]
        sections = {key: [] for key in SECTION_ORDER}
        current = "course"
        preserved_culture_href = None
        for element in elements:
            value = text(element)
            if value.replace(" ", "") in {"*****", "******", "*******"}:
                current = "quote"
                continue
            section, prefix, skip = marker(value)
            if section:
                current = section
            if skip:
                continue
            if current == "culture" and prefix:
                heading_links = element.xpath(".//a[@href]")
                if heading_links:
                    preserved_culture_href = heading_links[0].get("href")
            remove_prefix(element, prefix)
            for empty_link in element.xpath('.//a[@href][not(normalize-space())]'):
                empty_link.drop_tag()
            for empty_inline in element.xpath('.//*[self::strong or self::em or self::span][not(normalize-space()) and not(.//img)]'):
                empty_inline.drop_tag()
            if text(element) or element.xpath(".//img"):
                sections[current].append(element)

        if preserved_culture_href:
            images = [
                image for element in sections["culture"]
                for image in element.xpath(".//img[not(ancestor::a)]")
            ]
            if images:
                image = images[0]
                parent = image.getparent()
                position = parent.index(image)
                anchor = etree.Element("a", href=preserved_culture_href)
                parent.remove(image)
                anchor.append(image)
                parent.insert(position, anchor)

        all_elements = [element for key in SECTION_ORDER for element in sections[key]]
        normalize_media(all_elements, args.output / "assets", media)
        page_path = args.output / "index.html"
        page_path.write_text(make_page(args.week, args.date_range, sections), encoding="utf-8")
        subprocess.run([
            sys.executable, str(Path(__file__).with_name("preserve-word-formatting.py")),
            str(args.source), str(page_path)
        ], check=True)


if __name__ == "__main__":
    main()
