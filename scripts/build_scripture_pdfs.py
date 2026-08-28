#!/usr/bin/env python3
"""Build book-style A5 PDFs for scriptures in this repository.

The script intentionally uses only Python's standard library plus the Microsoft
Edge installation bundled with Windows.  This keeps the build reproducible in
the repository's WSL/Windows environment without adding a package dependency.
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "불교_경전" / "PDF"
EDGE = Path("/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")


@dataclass(frozen=True)
class Book:
    key: str
    source: Path
    output: Path
    title: str
    subtitle: str
    running_title: str
    cover_text: str
    composite: str = "single"
    footer_text: str = "한자 원문과 쉬운 우리말 풀이\n산스크리트어 핵심 용어 해설 수록"


BOOKS = (
    Book(
        key="금강경",
        source=ROOT / "불교_경전" / "금강경.md",
        output=OUTPUT_DIR / "금강경_원문_우리말풀이_해설.pdf",
        title="금강반야바라밀경",
        subtitle="원문 · 우리말 풀이 · 구절별 해설",
        running_title="금강반야바라밀경",
        cover_text="應無所住 而生其心",
    ),
    Book(
        key="반야심경",
        source=ROOT / "불교_경전" / "반야심경.md",
        output=OUTPUT_DIR / "반야심경_원문_우리말풀이_해설.pdf",
        title="반야바라밀다심경",
        subtitle="전문 · 우리말 풀이 · 구절별 해설",
        running_title="반야바라밀다심경",
        cover_text="照見五蘊皆空 度一切苦厄",
    ),
    Book(
        key="법구경",
        source=ROOT / "불교_경전" / "법구경_책머리.md",
        output=OUTPUT_DIR / "법구경_39품_원문_우리말풀이_해설.pdf",
        title="법구경",
        subtitle="39품 · 원문 · 우리말 풀이 · 게송별 해설",
        running_title="법구경",
        cover_text="諸惡莫作 諸善奉行 自淨其意",
        composite="dhammapada",
        footer_text="한역 T210 39품 전문 수록\n원문과 우리말 풀이 · 수행 해설",
    ),
)


def inline_markup(text: str) -> str:
    """Convert the small inline Markdown subset used by the source files."""
    tokens: list[str] = []

    def hold(value: str) -> str:
        tokens.append(value)
        return f"\x00{len(tokens) - 1}\x00"

    text = re.sub(
        r"`([^`]+)`",
        lambda m: hold(f"<code>{html.escape(m.group(1))}</code>"),
        text,
    )
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: hold(
            f'<a href="{html.escape(m.group(2), quote=True)}">'
            f"{html.escape(m.group(1))}</a>"
        ),
        text,
    )
    text = html.escape(text, quote=False)
    text = text.replace("&lt;br&gt;", "<br>").replace("&lt;br/&gt;", "<br>")
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    for index, value in enumerate(tokens):
        text = text.replace(f"\x00{index}\x00", value)
    return text


def slug(text: str, used: set[str]) -> str:
    value = re.sub(r"[^0-9A-Za-z가-힣]+", "-", text).strip("-").lower()
    value = value or "section"
    candidate = value
    serial = 2
    while candidate in used:
        candidate = f"{value}-{serial}"
        serial += 1
    used.add(candidate)
    return candidate


def is_table_separator(line: str) -> bool:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def dhammapada_chapter_files() -> list[Path]:
    pattern = re.compile(r"법구경_제(\d+)품_.+_문장별_풀이_해설\.md$")
    numbered: list[tuple[int, Path]] = []
    for path in (ROOT / "불교_경전").glob("법구경_제*품_*_문장별_풀이_해설.md"):
        match = pattern.fullmatch(path.name)
        if match:
            numbered.append((int(match.group(1)), path))
    numbered.sort()
    numbers = [number for number, _ in numbered]
    if numbers != list(range(1, 40)):
        raise RuntimeError(f"법구경 품별 파일이 1~39품과 일치하지 않습니다: {numbers}")
    return [path for _, path in numbered]


def prepare_dhammapada_chapter(path: Path) -> str:
    """Remove repeated file metadata and promote one file to a book chapter."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("# 법구경 제"):
        raise RuntimeError(f"법구경 품 제목을 확인할 수 없습니다: {path}")
    title = lines[0].removeprefix("# 법구경 ").replace(" — 게송별 풀이·해설", "")
    source_title = next(
        (line for line in lines if line.startswith("> **원전 품 표제:**")),
        None,
    )
    try:
        content_start = lines.index("## 품 해제")
        content_end = lines.index("## 편집 확인")
    except ValueError as error:
        raise RuntimeError(f"법구경 품의 구성 표제를 확인할 수 없습니다: {path}") from error
    content = []
    for line in lines[content_start:content_end]:
        if line.startswith("## "):
            content.append("### " + line[3:])
        else:
            content.append(line)
    parts = [f"## {title}"]
    if source_title:
        parts.extend(["", source_title])
    parts.extend(["", *content, ""])
    return "\n".join(parts)


def book_markdown(book: Book) -> str:
    introduction = book.source.read_text(encoding="utf-8")
    if book.composite != "dhammapada":
        return introduction
    chapters = [prepare_dhammapada_chapter(path) for path in dhammapada_chapter_files()]
    return introduction.rstrip() + "\n\n---\n\n" + "\n\n---\n\n".join(chapters)


def markdown_to_html(markdown: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Render the block Markdown used by the scripture files.

    Returns the body HTML and a level/title/id list used for the printed table
    of contents.  The first H1 is omitted because the designed cover replaces it.
    """
    lines = markdown.splitlines()
    output: list[str] = []
    toc: list[tuple[int, str, str]] = []
    used_ids: set[str] = set()
    subsection_open = False
    subsection_role = ""
    index = 0

    def close_subsection() -> None:
        nonlocal subsection_open, subsection_role
        if subsection_open:
            output.append("</section>")
            subsection_open = False
            subsection_role = ""

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            if level == 1:
                index += 1
                continue
            anchor = slug(re.sub(r"[`*_]", "", title), used_ids)
            if level == 2:
                close_subsection()
                toc.append((level, title, anchor))
                output.append(f'<h2 id="{anchor}">{inline_markup(title)}</h2>')
            else:
                close_subsection()
                role_map = {
                    "원문": "original-section",
                    "우리말 풀이": "translation-section",
                    "해설": "commentary-section",
                }
                subsection_role = role_map.get(title, "general-section")
                output.append(f'<section class="subsection {subsection_role}">')
                output.append(f'<h3 id="{anchor}">{inline_markup(title)}</h3>')
                subsection_open = True
            index += 1
            continue

        if stripped == "---":
            output.append('<div class="ornament" aria-hidden="true">◆</div>')
            index += 1
            continue

        if stripped.startswith(">"):
            block: list[str] = []
            while index < len(lines) and lines[index].lstrip().startswith(">"):
                value = lines[index].lstrip()[1:]
                block.append(value[1:] if value.startswith(" ") else value)
                index += 1
            block_html = "<br>".join(inline_markup(value) for value in block)
            class_name = "original" if subsection_role == "original-section" else "quotation"
            output.append(f'<blockquote class="{class_name}">{block_html}</blockquote>')
            continue

        if stripped.startswith("|") and index + 1 < len(lines) and is_table_separator(lines[index + 1]):
            headers = split_table_row(line)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(split_table_row(lines[index]))
                index += 1
            output.append("<table><thead><tr>")
            output.extend(f"<th>{inline_markup(cell)}</th>" for cell in headers)
            output.append("</tr></thead><tbody>")
            for row in rows:
                output.append("<tr>")
                output.extend(f"<td>{inline_markup(cell)}</td>" for cell in row)
                output.append("</tr>")
            output.append("</tbody></table>")
            continue

        list_match = re.match(r"^\s*(-|\*)\s+(.+)$", line)
        ordered_match = re.match(r"^\s*\d+\.\s+(.+)$", line)
        if list_match or ordered_match:
            ordered = bool(ordered_match)
            tag = "ol" if ordered else "ul"
            items: list[str] = []
            while index < len(lines):
                current = lines[index]
                match = re.match(r"^\s*\d+\.\s+(.+)$", current) if ordered else re.match(
                    r"^\s*(-|\*)\s+(.+)$", current
                )
                if not match:
                    break
                items.append(match.group(1) if ordered else match.group(2))
                index += 1
            class_name = " commentary-list" if subsection_role == "commentary-section" else ""
            output.append(f'<{tag} class="{class_name.strip()}">')
            output.extend(f"<li>{inline_markup(item)}</li>" for item in items)
            output.append(f"</{tag}>")
            continue

        labeled = re.match(r"^\*\*(원문|우리말 풀이|해설)\*\*\s+(.+)$", stripped)
        if labeled:
            label = labeled.group(1)
            role = {
                "원문": "original",
                "우리말 풀이": "translation",
                "해설": "commentary",
            }[label]
            output.append(
                f'<div class="labeled labeled-{role}">'
                f'<div class="labeled-title">{label}</div>'
                f'<p>{inline_markup(labeled.group(2))}</p></div>'
            )
            index += 1
            continue

        paragraph = [stripped]
        index += 1
        while index < len(lines):
            upcoming = lines[index].strip()
            if not upcoming:
                break
            if (
                re.match(r"^#{1,3}\s+", lines[index])
                or upcoming == "---"
                or upcoming.startswith(">")
                or re.match(r"^\s*(-|\*)\s+", lines[index])
                or re.match(r"^\s*\d+\.\s+", lines[index])
                or (upcoming.startswith("|") and index + 1 < len(lines) and is_table_separator(lines[index + 1]))
            ):
                break
            paragraph.append(upcoming)
            index += 1
        output.append(f"<p>{inline_markup(' '.join(paragraph))}</p>")

    close_subsection()
    return "\n".join(output), toc


def make_toc(items: list[tuple[int, str, str]]) -> str:
    rows = []
    for _, title, anchor in items:
        chapter = re.match(r"^제(\d+)(품)?\s*", title)
        numbered = re.match(r"^(\d+)\.\s*", title)
        if chapter:
            marker = "품 " if chapter.group(2) else ""
            short_title = f"{chapter.group(1)}. {marker}{title[chapter.end():]}"
        elif numbered:
            short_title = f"{numbered.group(1)}. {title[numbered.end():]}"
        else:
            short_title = title
        rows.append(f'<li><a href="#{anchor}">{inline_markup(short_title)}</a></li>')
    compact = " compact" if len(rows) > 18 else ""
    return f'<nav class="toc{compact}"><h2>차례</h2><ol>{"".join(rows)}</ol></nav>'


def stylesheet(running_title: str) -> str:
    safe_title = running_title.replace('"', "")
    return f"""
@font-face {{
  font-family: 'Book Serif';
  src: url('file:///C:/Windows/Fonts/NotoSerifKR-VF.ttf') format('truetype');
  font-weight: 100 900;
}}
@font-face {{
  font-family: 'Book Sans';
  src: url('file:///C:/Windows/Fonts/NotoSansKR-VF.ttf') format('truetype');
  font-weight: 100 900;
}}
@page {{
  size: A5;
  margin: 18mm 16mm 19mm 18mm;
  @top-center {{
    content: '{safe_title}';
    font-family: 'Book Sans', sans-serif;
    font-size: 7.5pt;
    color: #756f65;
    letter-spacing: .12em;
  }}
  @bottom-center {{
    content: counter(page);
    font-family: 'Book Sans', sans-serif;
    font-size: 8pt;
    color: #756f65;
  }}
}}
@page cover {{
  margin: 0;
  @top-center {{ content: none; }}
  @bottom-center {{ content: none; }}
}}
* {{ box-sizing: border-box; }}
html {{ background: #efede7; }}
body {{
  margin: 0;
  color: #25231f;
  background: white;
  font-family: 'Book Serif', 'Noto Serif KR', 'Batang', serif;
  font-size: 9.4pt;
  line-height: 1.86;
  word-break: keep-all;
  overflow-wrap: break-word;
  text-rendering: optimizeLegibility;
}}
.cover {{
  page: cover;
  width: 148mm;
  height: 210mm;
  padding: 26mm 18mm 22mm;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  text-align: center;
  color: #f8f2e6;
  background:
    radial-gradient(circle at 50% 28%, rgba(217,178,88,.28), transparent 27%),
    linear-gradient(155deg, #3d241b 0%, #6c3524 55%, #291b18 100%);
  break-after: page;
}}
.cover::before {{
  content: '';
  position: absolute;
  inset: 9mm;
  border: .35mm solid rgba(236,211,156,.65);
  pointer-events: none;
}}
.cover-kicker {{ font: 500 8.5pt/1.5 'Book Sans', sans-serif; letter-spacing: .36em; }}
.cover-main {{ margin: auto 0; }}
.cover h1 {{ margin: 0; font-size: 25pt; line-height: 1.45; letter-spacing: .12em; font-weight: 650; }}
.cover .subtitle {{ margin: 7mm 0 0; font: 400 10pt/1.8 'Book Sans', sans-serif; letter-spacing: .12em; }}
.cover .seal {{
  display: inline-block;
  margin-top: 15mm;
  padding: 3mm 5mm;
  border: .3mm solid #d4b46e;
  color: #e6ce98;
  font-size: 12.5pt;
  letter-spacing: .18em;
}}
.cover-footer {{ font: 400 8pt/1.7 'Book Sans', sans-serif; color: #e1cfae; letter-spacing: .08em; }}
.toc {{ break-after: page; padding-top: 7mm; }}
.toc h2 {{ break-before: auto; margin-top: 0; }}
.toc ol {{ list-style: none; padding: 0; margin: 8mm 0 0; }}
.toc li {{ margin: 0; border-bottom: .2mm solid #ddd6ca; break-inside: avoid; }}
.toc a {{ display: block; padding: 1.4mm 0; color: inherit; text-decoration: none; font: 500 8.7pt/1.45 'Book Sans', sans-serif; }}
.toc.compact ol {{ columns: 2; column-gap: 8mm; column-rule: .2mm solid #e4ded3; }}
.toc.compact li {{ break-inside: avoid-column; }}
h2 {{
  break-before: page;
  break-after: avoid;
  margin: 0 0 9mm;
  padding-top: 9mm;
  color: #5a2f24;
  font-size: 17pt;
  line-height: 1.52;
  font-weight: 680;
  letter-spacing: -.025em;
}}
h2::after {{ content: ''; display: block; width: 20mm; margin-top: 4mm; border-bottom: .55mm solid #a87945; }}
h3 {{
  break-after: avoid;
  margin: 7mm 0 3mm;
  color: #5f493b;
  font: 650 11.5pt/1.55 'Book Sans', sans-serif;
  letter-spacing: .03em;
}}
p {{ margin: 0 0 3.7mm; text-align: justify; orphans: 3; widows: 3; }}
a {{ color: #6b4432; text-decoration-thickness: .2mm; text-underline-offset: .5mm; }}
code {{
  font-family: 'Book Sans', sans-serif;
  font-size: .9em;
  color: #61402f;
  background: #f3eee6;
  padding: .15em .32em;
  border-radius: .6mm;
}}
blockquote {{ break-inside: avoid; margin: 4mm 0 5mm; }}
blockquote.quotation {{ padding: 4mm 5mm; border-left: 1mm solid #ad8352; background: #faf7f0; color: #554b40; }}
blockquote.original {{
  padding: 5mm 5.5mm;
  border: .25mm solid #d7c7ad;
  border-left: 1.2mm solid #8f6236;
  background: #fbf7ed;
  font-family: 'Noto Serif KR', 'Book Serif', 'Batang', serif;
  font-size: 10.4pt;
  line-height: 2;
  text-align: justify;
}}
.translation-section p {{ padding-left: 4mm; border-left: .7mm solid #c7aa7a; }}
.labeled {{ margin: 0 0 4mm; padding: 3.2mm 4mm; break-inside: avoid; }}
.labeled-title {{
  margin-bottom: 1.4mm;
  color: #654838;
  font: 700 8.5pt/1.4 'Book Sans', sans-serif;
  letter-spacing: .06em;
}}
.labeled p {{ margin: 0; }}
.labeled-original {{
  border: .25mm solid #d7c7ad;
  border-left: 1.1mm solid #8f6236;
  background: #fbf7ed;
  font-size: 10.1pt;
  line-height: 1.95;
}}
.labeled-translation {{ border-left: .7mm solid #c7aa7a; background: #fcfaf6; }}
.labeled-commentary {{ background: #f5f1e9; color: #453f38; }}
ul, ol {{ margin: 0 0 4mm; padding-left: 5.7mm; }}
li {{ margin: 0 0 2.1mm; padding-left: .7mm; orphans: 3; widows: 3; }}
.commentary-list li::marker {{ color: #a06b3e; }}
.commentary-list li:has(strong:first-child) {{
  margin-top: 3mm;
  padding: 3mm 3.5mm;
  border-left: .8mm solid #9e7950;
  background: #f7f2e9;
  list-style-position: inside;
}}
table {{ width: 100%; margin: 4mm 0 6mm; border-collapse: collapse; font: 400 8.5pt/1.58 'Book Sans', sans-serif; }}
thead {{ display: table-header-group; }}
tr {{ break-inside: avoid; }}
th {{ color: #fff; background: #73503c; font-weight: 650; }}
th, td {{ padding: 2.2mm 2.5mm; border: .2mm solid #d8d0c4; vertical-align: top; }}
tbody tr:nth-child(even) {{ background: #f8f5ef; }}
.ornament {{ margin: 8mm 0; text-align: center; color: #a87945; break-after: avoid; }}
.subsection {{ break-inside: auto; }}
strong {{ font-weight: 700; }}
@media screen {{
  body {{ width: 148mm; margin: 10mm auto; box-shadow: 0 2mm 9mm rgba(0,0,0,.15); }}
}}
"""


def book_html(book: Book) -> str:
    body, headings = markdown_to_html(book_markdown(book))
    toc = make_toc(headings)
    footer = "<br>".join(html.escape(line) for line in book.footer_text.splitlines())
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(book.title)}</title>
<style>{stylesheet(book.running_title)}</style>
</head>
<body>
<section class="cover">
  <div class="cover-kicker">불교 경전 우리말 해설</div>
  <div class="cover-main">
    <h1>{html.escape(book.title)}</h1>
    <p class="subtitle">{html.escape(book.subtitle)}</p>
    <div class="seal">{html.escape(book.cover_text)}</div>
  </div>
  <div class="cover-footer">{footer}</div>
</section>
{toc}
<main>{body}</main>
</body>
</html>"""


def windows_path(path: Path) -> str:
    result = subprocess.run(
        ["wslpath", "-w", str(path.resolve())],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def windows_file_uri(path: Path) -> str:
    value = windows_path(path).replace("\\", "/")
    return "file:///" + quote(value, safe="/:~")


def render_pdf(book: Book, keep_html: bool = False) -> Path:
    if not EDGE.exists():
        raise FileNotFoundError(f"Microsoft Edge를 찾을 수 없습니다: {EDGE}")
    if not book.source.exists():
        raise FileNotFoundError(f"원본 문서를 찾을 수 없습니다: {book.source}")
    if book.composite == "dhammapada":
        dhammapada_chapter_files()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html_path = OUTPUT_DIR / f".{book.output.stem}.html"
    html_path.write_text(book_html(book), encoding="utf-8")
    profile = Path(tempfile.mkdtemp(prefix=".edge-profile-", dir=OUTPUT_DIR))
    command = [
        str(EDGE),
        "--headless=new",
        "--disable-gpu",
        "--disable-extensions",
        "--no-first-run",
        "--no-pdf-header-footer",
        f"--user-data-dir={windows_path(profile)}",
        f"--print-to-pdf={windows_path(book.output)}",
        windows_file_uri(html_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=180)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
        if not keep_html:
            html_path.unlink(missing_ok=True)
    if not book.output.exists() or book.output.stat().st_size < 10_000:
        raise RuntimeError(f"PDF 생성에 실패했습니다: {book.output}")
    return book.output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep-html",
        action="store_true",
        help="검토를 위해 PDF와 함께 중간 HTML도 남깁니다.",
    )
    parser.add_argument(
        "--book",
        choices=["all", *(book.key for book in BOOKS)],
        default="all",
        help="특정 경전만 만들려면 경전 이름을 지정합니다.",
    )
    args = parser.parse_args()
    selected = BOOKS if args.book == "all" else tuple(book for book in BOOKS if book.key == args.book)
    for book in selected:
        output = render_pdf(book, keep_html=args.keep_html)
        print(f"생성: {output.relative_to(ROOT)} ({output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
