#!/usr/bin/env python3
"""Convert an EWOT Word update into the approved static archive page.

The importer preserves the source wording, links, inline emphasis, lists, and
embedded media. It only reorganizes the document into the Course Update
sections used by the Rizzo-Hours site.
"""

from __future__ import annotations

import argparse
import copy
import shutil
import subprocess
import tempfile
from pathlib import Path

from lxml import etree, html


SECTION_LABELS = {
    "course": "Course timing and readings",
    "assignments": "Assignments and due dates",
    "exam": "Exam information",
    "recitation": "Recitation information",
    "admin": "Other class admin, TA hours",
    "events": "Upcoming Special Events",
    "attention": "Some Items That Caught Our Attention",
    "chart": "Chart of the Week",
    "photo": "Photo of the Week",
    "culture": "Film, music, cultural item of the Week",
    "quote": "They Said It",
}

NAV_ORDER = [
    "course",
    "assignments",
    "exam",
    "recitation",
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


def clean_text(element: etree._Element) -> str:
    return " ".join(element.text_content().split())


def is_divider(element: etree._Element) -> bool:
    return clean_text(element).replace(" ", "") in {"*****", "-----"}


def add_class(element: etree._Element, class_name: str) -> None:
    classes = element.get("class", "").split()
    if class_name not in classes:
        classes.append(class_name)
    element.set("class", " ".join(classes))


def remove_strong(element: etree._Element, strong: etree._Element) -> None:
    parent = strong.getparent()
    if parent is None:
        return
    index = parent.index(strong)
    tail = strong.tail or ""
    parent.remove(strong)
    if index == 0:
        parent.text = (parent.text or "") + tail
    elif index - 1 < len(parent):
        previous = parent[index - 1]
        previous.tail = (previous.tail or "") + tail


def strip_redundant_section_labels(sections: dict[str, list[etree._Element]]) -> None:
    removable = {
        "course": ("readings and topics this week:",),
        "assignments": ("weekly assignments:",),
        "recitation": ("recitation:",),
        "chart": ("chart of the week:",),
        "photo": ("photo of the week",),
    }
    for section_id, labels in removable.items():
        for element in sections[section_id]:
            strongs = element.xpath("./strong[1]")
            if not strongs:
                continue
            strong = strongs[0]
            strong_text = clean_text(strong).lower()
            if any(strong_text.startswith(label) for label in labels):
                remove_strong(element, strong)
                if element.text:
                    element.text = element.text.lstrip(" :")
                add_class(element, "source-subhead")
                break

    sections["events"] = [
        element
        for element in sections["events"]
        if clean_text(element).lower().rstrip(" :–-") != "upcoming special events"
    ]

    attention_label = "some items that caught our attention"
    for element in list(sections["attention"]):
        text = clean_text(element).lower().rstrip(" :–-")
        if text == attention_label:
            sections["attention"].remove(element)
            break
        if text.startswith(attention_label):
            for strong in element.xpath("./strong"):
                if clean_text(strong).lower().rstrip(" :–-") == attention_label:
                    remove_strong(element, strong)
                    if element.text:
                        element.text = element.text.lstrip(" :–-")
                    add_class(element, "source-subhead")
                    break
            break

    for element in sections["attention"]:
        if element.tag == "p":
            add_class(element, "source-subhead")

    for section_id in ("exam", "admin", "events"):
        for element in sections[section_id]:
            if element.tag == "p" and element.xpath("./strong[1]"):
                add_class(element, "source-subhead")


def marker_for(element: etree._Element) -> str | None:
    text = clean_text(element).lower()
    if text.startswith("readings and topics this week:"):
        return "course"
    if text.startswith("recitation:"):
        return "recitation"
    if text.startswith("weekly assignments:"):
        return "assignments"
    if text.startswith("exam:") or text.startswith("exam brief update:"):
        return "exam"
    if text.startswith("ta office hours:"):
        return "admin"
    if text.startswith("upcoming special events"):
        return "events"
    if text.startswith("some items that caught our attention"):
        return "attention"
    if text.startswith("chart of the week:"):
        return "chart"
    if text.startswith("photo of the week"):
        return "photo"
    if "video/documentary/book/cartoon of the week:" in text:
        return "culture"
    return None


def remove_redundant_culture_heading(elements: list[etree._Element]) -> str | None:
    if not elements:
        return None
    paragraph = elements[0]
    strongs = paragraph.xpath(".//strong")
    if not strongs:
        return None
    heading = strongs[0]
    heading_text = clean_text(heading)
    if "Video/Documentary/Book/Cartoon of the Week:" not in heading_text:
        return None
    links = heading.xpath(".//a[@href]")
    heading_link = links[0].get("href") if links else None
    suffix = heading_text.split("of the Week:", 1)[1].strip()
    tail = heading.tail or ""
    parent = heading.getparent()
    index = parent.index(heading)
    heading.tail = ""
    parent.remove(heading)
    if suffix:
        if index == 0:
            parent.text = (parent.text or "") + suffix
        elif index - 1 < len(parent):
            previous = parent[index - 1]
            previous.tail = (previous.tail or "") + suffix
    if tail:
        if index == 0:
            parent.text = (parent.text or "") + tail
        elif index - 1 < len(parent):
            previous = parent[index - 1]
            previous.tail = (previous.tail or "") + tail
    if not clean_text(paragraph) and not paragraph.xpath(".//img"):
        elements.pop(0)
    return heading_link


def attach_preserved_link(elements: list[etree._Element], href: str | None) -> None:
    if not href:
        return
    for element in elements:
        if element.xpath(f'.//a[@href="{href}"]'):
            return
    for element in elements:
        images = element.xpath(".//img[not(ancestor::a)]")
        if images:
            image = images[0]
            parent = image.getparent()
            index = parent.index(image)
            anchor = etree.Element("a", href=href)
            parent.remove(image)
            anchor.append(image)
            parent.insert(index, anchor)
            return


def normalize_media(elements: list[etree._Element], output_assets: Path, media_root: Path) -> None:
    output_assets.mkdir(parents=True, exist_ok=True)
    for element in elements:
        for image in element.xpath(".//img"):
            source = Path(image.get("src", ""))
            if not source.is_absolute():
                source = media_root / source
            if not source.is_file():
                raise FileNotFoundError(f"Missing extracted image: {source}")
            destination = output_assets / source.name
            shutil.copy2(source, destination)
            image.set("src", f"assets/{destination.name}")
            image.attrib.pop("style", None)
            image.set("loading", "lazy")
            if not image.get("alt"):
                image.set("alt", "Image from the original course update")


def render_elements(elements: list[etree._Element]) -> str:
    return "\n".join(
        html.tostring(element, encoding="unicode", method="html") for element in elements
    )


def section_classes(section_id: str) -> str:
    classes = ["issue-section", "source-update"]
    if section_id == "exam":
        classes.append("exam-alert")
    if section_id == "attention":
        classes.append("attention-archive")
    if section_id in {"chart", "photo", "culture"}:
        classes.append("visual-archive")
    return " ".join(classes)


def make_page(week: int, date_range: str, sections: dict[str, list[etree._Element]]) -> str:
    week_label = NUMBER_WORDS.get(week, str(week))
    nav = "\n".join(
        f'          <li><a href="#{section_id}">{SECTION_LABELS[section_id]}</a></li>'
        for section_id in NAV_ORDER
        if sections.get(section_id)
    )
    bodies = []
    for section_id in NAV_ORDER:
        elements = sections.get(section_id, [])
        if not elements:
            continue
        bodies.append(
            f'''        <section class="{section_classes(section_id)}" id="{section_id}">
          <h2>{SECTION_LABELS[section_id]}</h2>
{render_elements(elements)}
        </section>'''
        )
    body = "\n\n".join(bodies)
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Week {week_label} Course Update | EWOT Fall 2025</title>
  <meta name="description" content="ECON 108 course update for {date_range}.">
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
      <div class="issue-masthead issue-masthead--archive">
        <p class="kicker">ECON 108 · EWOT · Fall 2025</p>
        <h1>Week {week_label} Course Update</h1>
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
{body}
      </article>
    </main>

    <footer class="site-footer">
      <p><strong>EWOT Weekly Course Updates</strong><br>ECON 108 · Fall 2025</p>
      <p><a href="../index.html">Fall 2025 archive</a> · <a href="../../index.html">EWOT course updates</a></p>
    </footer>
  </div>

  <a class="back-to-top" href="#top" aria-label="Back to top">↑</a>
</body>
</html>
'''


def import_update(source: Path, output: Path, week: int, date_range: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"ewot-week-{week:02d}-") as temporary:
        temporary_path = Path(temporary)
        extracted = temporary_path / "extracted"
        raw_html = temporary_path / "raw.html"
        subprocess.run(
            [
                "pandoc",
                str(source),
                "-f",
                "docx",
                "-t",
                "html5",
                f"--extract-media={extracted}",
                "-o",
                str(raw_html),
            ],
            check=True,
        )
        fragment = html.fragment_fromstring(raw_html.read_text(encoding="utf-8"), create_parent="div")
        elements = [copy.deepcopy(child) for child in fragment]

        if elements and "WEEKLY REMINDERS/ANNOUNCEMENTS" in clean_text(elements[0]):
            elements.pop(0)

        sections: dict[str, list[etree._Element]] = {key: [] for key in NAV_ORDER}
        current: str | None = None
        for element in elements:
            text = clean_text(element)
            if text.startswith("INTERNSHIP OPPORTUNITIES"):
                current = "admin"
            marker = marker_for(element)
            if marker:
                current = marker
            elif is_divider(element):
                if current == "attention":
                    continue
                if current == "culture":
                    current = "quote"
                    continue

            if current is None:
                lowered = text.lower()
                if lowered.startswith("exam"):
                    sections["exam"].append(element)
                elif lowered.startswith("recitaion") or lowered.startswith("recitation"):
                    sections["recitation"].append(element)
                else:
                    sections["course"].append(element)
                continue

            sections[current].append(element)

        strip_redundant_section_labels(sections)
        heading_link = remove_redundant_culture_heading(sections["culture"])
        attach_preserved_link(sections["culture"], heading_link)

        all_elements = [element for key in NAV_ORDER for element in sections[key]]
        normalize_media(all_elements, output / "assets", extracted)
        page = make_page(week, date_range, sections)
        (output / "index.html").write_text(page, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--dates", required=True)
    args = parser.parse_args()
    import_update(args.source, args.output, args.week, args.dates)


if __name__ == "__main__":
    main()
