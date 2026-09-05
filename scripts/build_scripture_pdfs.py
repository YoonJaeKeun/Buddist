#!/usr/bin/env python3
"""Build book-style PDFs for scriptures in this repository.

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
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "불교_경전" / "PDF"
EDGE_CANDIDATES = (
    Path("/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    Path("/mnt/c/Program Files/Microsoft/Edge/Application/msedge.exe"),
    Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
)


def find_edge() -> Path:
    """Locate Microsoft Edge under WSL or under native Windows Python."""
    for candidate in EDGE_CANDIDATES:
        if candidate.exists():
            return candidate
    located = shutil.which("msedge") or shutil.which("msedge.exe")
    if located:
        return Path(located)
    raise FileNotFoundError(
        "Microsoft Edge를 찾을 수 없습니다: " + ", ".join(str(p) for p in EDGE_CANDIDATES)
    )


AI_BADGE = "AI 해석본"
AI_NOTICE = (
    "이 책의 우리말 풀이와 해설은 AI가 한문 원문을 읽고 만든 것입니다. "
    "원문은 저본을 그대로 옮겼으나, 풀이와 해설은 전통 주석서를 대신하지 않으며 "
    "잘못 읽은 곳이 있을 수 있습니다."
)


@dataclass(frozen=True)
class Book:
    key: str
    source: Path
    output: Path
    title: str
    subtitle: str
    running_title: str
    cover_text: str
    paper_size: str = "A5"
    composite: str = "single"
    footer_text: str = "한자 원문과 쉬운 우리말 풀이\n산스크리트어 핵심 용어 해설 수록"
    cover_ground: str = ""
    cover_palette: str = "ocean"
    cover_motif: str = "worlds"
    cover_hanja: str = ""
    cover_mark: str = ""
    render_timeout: float = 300.0
    group: str = ""
    fascicles: tuple[int, int] | None = None
    introduction: bool = True

    @property
    def selector(self) -> str:
        """The ``--book`` name that builds this volume along with its set."""
        return self.group or self.key


AVATAMSAKA_VOLUMES = (
    # 저본 권 범위, 회 번호, 회 이름, 상·중·하, 표지 색조, 표지 도형
    (1, 11, 1, "적멸도량회", "", "ocean", "worlds"),
    (12, 15, 2, "보광명전회", "", "radiance", "rays"),
    (16, 18, 3, "도리천궁회", "", "summit", "summit"),
    (19, 21, 4, "야마천궁회", "", "store", "store"),
    (22, 27, 5, "도솔천궁회", "상", "turning", "turning"),
    (28, 33, 5, "도솔천궁회", "하", "returning", "returning"),
    (34, 39, 6, "타화자재천궁회", "", "grounds", "terraces"),
    (40, 45, 7, "보광명전중회", "상", "countless", "countless"),
    (46, 52, 7, "보광명전중회", "하", "emergence", "emergence"),
    (53, 59, 8, "보광명전삼회", "", "beyond", "beyond"),
    (60, 66, 9, "서다림회", "상", "setting", "setting"),
    (67, 73, 9, "서다림회", "중", "meetings", "meetings"),
    (74, 80, 9, "서다림회", "하", "tower", "tower"),
)


def avatamsaka_books() -> tuple[Book, ...]:
    """Expand the 九會 table into one Book per printed volume.

    The 80권 printed as a single PDF ran to 6,918 pages and 132MB — past
    GitHub's file limit, and far past the 25~713쪽 the rest of this series
    occupies.  Splitting on the assemblies keeps every volume inside that band
    without ever cutting a 저본 권 in half.  Only the first volume carries the
    guide document; repeating it thirteen times would cost dozens of pages a
    book.
    """
    total = len(AVATAMSAKA_VOLUMES)
    volumes = []
    for index, (first, last, assembly, name, part, palette, motif) in enumerate(
        AVATAMSAKA_VOLUMES, 1
    ):
        label = f"제{assembly}회 {name}" + (f" {part}" if part else "")
        stem = f"화엄경_{index:02d}책_제{assembly}회_{name}" + (f"_{part}" if part else "")
        volumes.append(
            Book(
                key=f"화엄경{index:02d}",
                group="화엄경",
                source=ROOT / "불교_경전" / "화엄경.md",
                output=OUTPUT_DIR / f"{stem}.pdf",
                title="대방광불화엄경",
                subtitle=f"{label} · 권{first}~{last} · 원문 · 우리말 풀이 · 문장별 해설",
                running_title=f"대방광불화엄경 · {label}",
                cover_text="初發心時 便成正覺",
                paper_size="A4",
                composite="avatamsaka",
                footer_text=(
                    f"실차난타 한역 T279 80권 39품 가운데 권{first}~{last}\n"
                    f"전 {total}책 중 제{index}책 · 문장별 우리말 풀이 · 확장 해설"
                ),
                cover_ground="net",
                cover_palette=palette,
                cover_motif=motif,
                cover_hanja="大方廣佛華嚴經",
                cover_mark="華嚴",
                render_timeout=1200.0,
                fascicles=(first, last),
                introduction=first == 1,
            )
        )
    return tuple(volumes)


BOOKS = (
    Book(
        key="금강경",
        source=ROOT / "불교_경전" / "금강경.md",
        output=OUTPUT_DIR / "금강경.pdf",
        title="금강반야바라밀경",
        subtitle="원문 · 우리말 풀이 · 구절별 해설",
        running_title="금강반야바라밀경",
        cover_text="應無所住 而生其心",
        paper_size="A4",
        cover_palette="vajra",
        cover_motif="facets",
        cover_hanja="金剛般若波羅蜜經",
        cover_mark="金剛",
    ),
    Book(
        key="반야심경",
        source=ROOT / "불교_경전" / "반야심경.md",
        output=OUTPUT_DIR / "반야심경.pdf",
        title="반야바라밀다심경",
        subtitle="전문 · 우리말 풀이 · 구절별 해설",
        running_title="반야바라밀다심경",
        cover_text="照見五蘊皆空 度一切苦厄",
        paper_size="A4",
        cover_palette="void",
        cover_motif="enso",
        cover_hanja="般若波羅蜜多心經",
        cover_mark="心經",
    ),
    Book(
        key="법구경",
        source=ROOT / "불교_경전" / "법구경_책머리.md",
        output=OUTPUT_DIR / "법구경_39품.pdf",
        title="법구경",
        subtitle="39품 · 원문 · 우리말 풀이 · 게송별 해설",
        running_title="법구경",
        cover_text="諸惡莫作 諸善奉行 自淨其意",
        paper_size="A4",
        composite="dhammapada",
        footer_text="한역 T210 39품 전문 수록\n원문과 우리말 풀이 · 수행 해설",
        cover_palette="earth",
        cover_motif="verses",
        cover_hanja="法句經",
        cover_mark="法句",
    ),
    Book(
        key="법화경",
        source=ROOT / "불교_경전" / "법화경.md",
        output=OUTPUT_DIR / "법화경_28품.pdf",
        title="묘법연화경",
        subtitle="28품 · 원문 · 우리말 풀이 · 문장별 해설",
        running_title="묘법연화경",
        cover_text="開示悟入 佛之知見",
        paper_size="A4",
        composite="lotus",
        footer_text="구마라집 한역 T262 28품 전문 수록\n문장별 우리말 풀이 · 확장 해설",
        cover_palette="lotus",
        cover_motif="petals",
        cover_hanja="妙法蓮華經",
        cover_mark="法華",
    ),
    Book(
        key="유마경",
        source=ROOT / "불교_경전" / "유마경.md",
        output=OUTPUT_DIR / "유마경_14품.pdf",
        title="유마힐소설경",
        subtitle="14품 · 원문 · 우리말 풀이 · 문장별 해설",
        running_title="유마힐소설경",
        cover_text="以一切眾生病 是故我病",
        paper_size="A4",
        composite="vimalakirti",
        footer_text="구마라집 한역 T475 14품 전문 수록\n문장별 우리말 풀이 · 확장 해설",
        cover_palette="silence",
        cover_motif="chamber",
        cover_hanja="維摩詰所說經",
        cover_mark="維摩",
    ),
    Book(
        key="정토삼부경",
        source=ROOT / "불교_경전" / "정토삼부경_책머리.md",
        output=OUTPUT_DIR / "정토삼부경.pdf",
        title="정토삼부경",
        subtitle="무량수경 · 관무량수경 · 아미타경 — 원문 · 우리말 풀이 · 문장별 해설",
        running_title="정토삼부경",
        cover_text="設我得佛 十方眾生 至心信樂",
        paper_size="A4",
        composite="pureland",
        footer_text="T12 No. 360 · 365 · 366 경 본문 전문 수록\n문장별 우리말 풀이 · 확장 해설",
        cover_palette="sunset",
        cover_motif="horizon",
        cover_hanja="淨土三部經",
        cover_mark="淨土",
    ),
    *avatamsaka_books(),
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


def prepare_dhammapada_preface() -> str:
    """Promote the separate T210 preface to one PDF book chapter."""
    path = ROOT / "불교_경전" / "법구경서.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("# 법구경서"):
        raise RuntimeError(f"법구경서 제목을 확인할 수 없습니다: {path}")
    prepared = ["## " + lines[0].removeprefix("# ")]
    for line in lines[1:]:
        prepared.append("### " + line[3:] if line.startswith("## ") else line)
    return "\n".join(prepared)


CHAPTER_BOOKS = {
    "lotus": ("법화경", 28),
    "vimalakirti": ("유마경", 14),
}


def chapter_files(scripture: str, count: int) -> list[Path]:
    """Return one scripture's numbered 품별 보강본 files, in reading order."""
    pattern = re.compile(rf"{scripture}_제(\d+)품_.+_문장별_풀이_해설\.md$")
    numbered: list[tuple[int, Path]] = []
    for path in (ROOT / "불교_경전").glob(f"{scripture}_제*품_*_문장별_풀이_해설.md"):
        match = pattern.fullmatch(path.name)
        if match:
            numbered.append((int(match.group(1)), path))
    numbered.sort()
    numbers = [number for number, _ in numbered]
    if numbers != list(range(1, count + 1)):
        raise RuntimeError(
            f"{scripture} 품별 파일이 1~{count}품과 일치하지 않습니다: {numbers}"
        )
    return [path for _, path in numbered]


def prepare_introduction(path: Path, scripture: str) -> str:
    """Keep the print-worthy introduction and omit the repeated link index."""
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        chapter_start = next(
            index for index, line in enumerate(lines) if line.startswith("## 제1품 ")
        )
    except StopIteration as error:
        raise RuntimeError(f"{scripture} 제1품의 시작을 확인할 수 없습니다: {path}") from error

    front = lines[1:chapter_start]
    prepared = [f"## {scripture}을 읽기 전에"]
    skipping_links = False
    for line in front:
        if line.strip() == "문장별 풀이·해설 보강본:":
            skipping_links = True
            continue
        if skipping_links:
            # The index is a run of numbered links, sometimes split by blank lines.
            if not line.strip() or re.match(r"^\d+\. \[", line.strip()):
                continue
            skipping_links = False
        if line.startswith("## "):
            prepared.append("### " + line[3:])
        else:
            prepared.append(line)
    while prepared and prepared[-1].strip() in {"", "---"}:
        prepared.pop()
    return "\n".join(prepared)


def prepare_chapter(path: Path, scripture: str) -> str:
    """Promote one expanded 품별 보강본 file to a print book chapter."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith(f"# {scripture} 제"):
        raise RuntimeError(f"{scripture} 품 제목을 확인할 수 없습니다: {path}")
    required = ("**원문**", "**우리말 풀이**", "**해설**")
    if any(not any(line.startswith(label) for line in lines) for label in required):
        raise RuntimeError(f"{scripture} 원문·풀이·해설 구성을 확인할 수 없습니다: {path}")

    title = lines[0].removeprefix(f"# {scripture} ").replace(" — 확장 해설본", "")
    prepared = [f"## {title}"]
    for line in lines[1:]:
        prepared.append("### " + line[3:] if line.startswith("## ") else line)
    return "\n".join(prepared).rstrip()


AVATAMSAKA_CHAPTERS = 39
AVATAMSAKA_FASCICLES = 80


def avatamsaka_fascicle_map() -> dict[str, int]:
    """Map each 원고 file name to the 저본 권 it belongs to.

    화엄경.md already tabulates every manuscript against its 권, so the volume
    split reads that table instead of repeating the 94-row mapping here.
    """
    path = ROOT / "불교_경전" / "화엄경.md"
    mapping: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        link = re.search(r"\((화엄경_제\d+품_[^)]+\.md)\)", line)
        fascicle = re.search(r"\|\s*권(\d+)\s*\|", line)
        if link and fascicle:
            mapping[link.group(1)] = int(fascicle.group(1))
    found = sorted(set(mapping.values()))
    if found != list(range(1, AVATAMSAKA_FASCICLES + 1)):
        raise RuntimeError(
            f"화엄경 원고 표의 저본 권이 1~{AVATAMSAKA_FASCICLES}권과 이어지지 않습니다: {found}"
        )
    return mapping


def avatamsaka_chapter_files(fascicles: tuple[int, int] | None = None) -> list[Path]:
    """Return the 화엄경 품별 보강본 files in reading order.

    Unlike 법화경 and 유마경, one 화엄경 품 can run across several 저본 권, and
    those are kept in separate files with a trailing part number.  Sort by
    (품, 부분) so 제25품 십회향품 1~11 stay in numeric — not lexical — order.

    With ``fascicles`` given, only the manuscripts inside that 저본 권 range are
    returned — one printed volume's worth.
    """
    pattern = re.compile(r"화엄경_제(\d+)품_([^_]+)(?:_(\d+))?_문장별_풀이_해설\.md$")
    numbered: list[tuple[int, int, Path]] = []
    for path in (ROOT / "불교_경전").glob("화엄경_제*품_*_문장별_풀이_해설.md"):
        match = pattern.fullmatch(path.name)
        if match:
            part = int(match.group(3)) if match.group(3) else 0
            numbered.append((int(match.group(1)), part, path))
    numbered.sort()
    chapters = sorted({number for number, _, _ in numbered})
    if chapters != list(range(1, AVATAMSAKA_CHAPTERS + 1)):
        raise RuntimeError(
            f"화엄경 품별 파일이 1~{AVATAMSAKA_CHAPTERS}품과 일치하지 않습니다: {chapters}"
        )
    for chapter in chapters:
        parts = sorted(part for number, part, _ in numbered if number == chapter)
        expected = [0] if parts == [0] else list(range(1, len(parts) + 1))
        if parts != expected:
            raise RuntimeError(
                f"화엄경 제{chapter}품의 부분 번호가 이어지지 않습니다: {parts}"
            )
    ordered = [path for _, _, path in numbered]
    if fascicles is None:
        return ordered

    mapping = avatamsaka_fascicle_map()
    unmapped = [path.name for path in ordered if path.name not in mapping]
    if unmapped:
        raise RuntimeError(f"화엄경 원고 표에 저본 권이 없는 원고가 있습니다: {unmapped}")
    # 품 order must track 권 order, or a 권 range would not be a contiguous run.
    sequence = [mapping[path.name] for path in ordered]
    if sequence != sorted(sequence):
        raise RuntimeError(f"화엄경 원고의 품 순서가 저본 권 순서와 어긋납니다: {sequence}")
    first, last = fascicles
    selected = [path for path in ordered if first <= mapping[path.name] <= last]
    if not selected:
        raise RuntimeError(f"화엄경 권{first}~{last}에 해당하는 원고가 없습니다.")
    return selected


AVATAMSAKA_SKIPPED_SECTIONS = ("문장별 풀이·해설 보강본",)


def prepare_avatamsaka_introduction() -> str:
    """Promote 화엄경.md to the printed book's opening chapter.

    The manuscript's own H1 is dropped because the cover carries the title, its
    ``##`` sections become ``###`` under one chapter heading, and the section
    that only indexes the 94 품별 원고 files is omitted because those chapters
    follow in full.
    """
    path = ROOT / "불교_경전" / "화엄경.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("# 대방광불화엄경"):
        raise RuntimeError(f"화엄경 안내 문서의 제목을 확인할 수 없습니다: {path}")

    prepared = ["## 화엄경을 읽기 전에"]
    skipping = False
    for line in lines[1:]:
        if line.startswith("## "):
            skipping = line[3:].strip() in AVATAMSAKA_SKIPPED_SECTIONS
            if skipping:
                continue
            prepared.append("### " + line[3:])
            continue
        if skipping:
            continue
        prepared.append(line)
    while prepared and prepared[-1].strip() in {"", "---"}:
        prepared.pop()
    return "\n".join(prepared)


PURELAND_VOLUMES = (
    ("무량수경 권상", "무량수경_권상_문장별_풀이_해설.md"),
    ("무량수경 권하", "무량수경_권하_문장별_풀이_해설.md"),
    ("관무량수경", "관무량수경_문장별_풀이_해설.md"),
    ("아미타경", "아미타경_문장별_풀이_해설.md"),
)

PURELAND_SECTION_PREFIXES = ("제1부 불설무량수경 상권 — ", "권하 ")


def prepare_pureland_volume(volume: str, name: str) -> str:
    """Promote one 정토삼부경 manuscript to printed book sections.

    Each manuscript uses ``#`` for its own title, ``##`` for sections and ``###``
    for numbered passages.  The printed book drops the title, keeps sections at
    ``##`` so every one of them starts a new page and reaches the table of
    contents, and leaves passages at ``###``.  Section titles are prefixed with
    the volume so that the contents page names its sutra on every line.
    """
    path = ROOT / "불교_경전" / name
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("# "):
        raise RuntimeError(f"정토삼부경 원고 제목을 확인할 수 없습니다: {path}")
    required = ("**원문**", "**우리말 풀이**", "**해설**")
    if any(not any(line.startswith(label) for line in lines) for label in required):
        raise RuntimeError(f"정토삼부경 원문·풀이·해설 구성을 확인할 수 없습니다: {path}")

    prepared: list[str] = []
    for line in lines[1:]:
        if line.startswith("## "):
            title = line[3:].strip()
            for prefix in PURELAND_SECTION_PREFIXES:
                if title.startswith(prefix):
                    title = title[len(prefix):]
                    break
            prepared.append(f"## {volume} · {title}")
        else:
            prepared.append(line)
    return "\n".join(prepared).rstrip()


def pureland_sections() -> list[str]:
    return [prepare_pureland_volume(volume, name) for volume, name in PURELAND_VOLUMES]


def book_markdown(book: Book) -> str:
    introduction = book.source.read_text(encoding="utf-8")
    if book.composite == "dhammapada":
        preface = prepare_dhammapada_preface()
        chapters = [prepare_dhammapada_chapter(path) for path in dhammapada_chapter_files()]
        sections = [preface, *chapters]
        return introduction.rstrip() + "\n\n---\n\n" + "\n\n---\n\n".join(sections)
    if book.composite == "pureland":
        sections = pureland_sections()
        return introduction.rstrip() + "\n\n---\n\n" + "\n\n---\n\n".join(sections)
    if book.composite == "avatamsaka":
        chapters = [
            prepare_chapter(path, "화엄경")
            for path in avatamsaka_chapter_files(book.fascicles)
        ]
        sections = (
            [prepare_avatamsaka_introduction(), *chapters]
            if book.introduction
            else chapters
        )
        return "\n\n---\n\n".join(sections)
    if book.composite in CHAPTER_BOOKS:
        scripture, count = CHAPTER_BOOKS[book.composite]
        introduction = prepare_introduction(book.source, scripture)
        chapters = [
            prepare_chapter(path, scripture) for path in chapter_files(scripture, count)
        ]
        return introduction + "\n\n---\n\n" + "\n\n---\n\n".join(chapters)
    return introduction


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
                subsection_role = (
                    "verse-section"
                    if re.fullmatch(r"제\d+게송", title)
                    else "passage-section"
                    if re.fullmatch(r"\d+", title)
                    else role_map.get(title, "general-section")
                )
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


COVER_BASE_CSS = r"""
.cover {
  page: cover;
  position: relative;
  width: COVER_WIDTH;
  height: COVER_HEIGHT;
  padding: COVER_PADDING;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  overflow: hidden;
  text-align: left;
  color: var(--ink);
  break-after: page;
}
.cover-ground, .cover-motif { position: absolute; inset: 0; }
.cover-top {
  position: relative;
  display: flex;
  align-items: center;
  gap: 5mm;
}
.cover-mark {
  padding: 2.4mm 3.2mm 2mm;
  border-radius: 1.2mm;
  background: var(--mark-fill);
  color: var(--mark-ink);
  font: 650 9.5pt/1 'Noto Serif KR', serif;
  letter-spacing: .16em;
}
.cover-kicker {
  font: 500 8pt/1.5 'Noto Sans KR', sans-serif;
  letter-spacing: .34em;
  color: var(--muted);
}
.cover-main {
  position: relative;
  margin: auto 0 0;
  padding-bottom: 13mm;
}
.cover .cover-eyebrow {
  margin: 0 0 6mm;
  font: 400 12pt/1.5 'Noto Serif KR', serif;
  letter-spacing: .44em;
  color: var(--accent);
}
.cover h1 {
  margin: 0;
  font-size: COVER_TITLE_SIZE;
  line-height: 1.3;
  letter-spacing: -.005em;
  font-weight: 700;
  color: var(--ink);
}
.cover .cover-rule {
  width: 28mm;
  height: .55mm;
  margin: 9mm 0 6mm;
  background: linear-gradient(90deg, var(--accent) 0%, var(--fade) 100%);
}
.cover .subtitle {
  max-width: 116mm;
  margin: 0;
  font: 400 10.5pt/1.85 'Noto Sans KR', sans-serif;
  letter-spacing: .04em;
  color: var(--muted);
}
.cover .seal {
  display: inline-block;
  margin-top: 13mm;
  padding: .5mm 0 .5mm 4.5mm;
  border-left: .55mm solid var(--accent);
  color: var(--accent);
  font-size: 13pt;
  line-height: 1.6;
  letter-spacing: .2em;
}
.cover-footer {
  position: relative;
  padding-top: 4.5mm;
  border-top: .2mm solid var(--hairline);
  font: 400 8pt/1.75 'Noto Sans KR', sans-serif;
  color: var(--muted);
  letter-spacing: .06em;
}
.cover-ai {
  display: inline-block;
  margin-bottom: 3.4mm;
  padding: 1.5mm 2.8mm 1.2mm;
  border: .22mm solid var(--accent);
  border-radius: 1mm;
  font: 500 7pt/1 'Noto Sans KR', sans-serif;
  letter-spacing: .2em;
  color: var(--accent);
}
"""


# Each palette paints the whole field and hands the base stylesheet its colours.
# Each motif draws one figure taken from the sutra itself, using ::before,
# ::after and the span inside .cover-motif — up to four shapes without an image.
COVER_PALETTES = {
    "vajra": r"""
.cover {
  --ink: #f4f7fa;
  --muted: rgba(198,210,224,.74);
  --accent: #cfd8e3;
  --fade: rgba(207,216,227,0);
  --hairline: rgba(226,236,246,.18);
  --mark-fill: linear-gradient(135deg, #e8eef5 0%, #9fb0c4 100%);
  --mark-ink: #10151c;
  background:
    radial-gradient(72% 48% at 78% 8%, rgba(176,196,220,.24) 0%, rgba(176,196,220,0) 62%),
    linear-gradient(152deg, #10141a 0%, #242e3b 52%, #0b0e13 100%);
}
""",
    "void": r"""
.cover {
  --ink: #f7f4fc;
  --muted: rgba(212,204,230,.74);
  --accent: #e2d8f2;
  --fade: rgba(226,216,242,0);
  --hairline: rgba(230,222,246,.18);
  --mark-fill: linear-gradient(135deg, #efe8fb 0%, #b3a3d4 100%);
  --mark-ink: #16121f;
  background:
    radial-gradient(66% 46% at 72% 14%, rgba(150,132,196,.28) 0%, rgba(150,132,196,0) 62%),
    linear-gradient(160deg, #15121f 0%, #2c2545 50%, #0f0d17 100%);
}
""",
    "earth": r"""
.cover {
  --ink: #fbf5e8;
  --muted: rgba(224,208,178,.74);
  --accent: #dcbc7c;
  --fade: rgba(220,188,124,0);
  --hairline: rgba(238,224,196,.18);
  --mark-fill: linear-gradient(135deg, #f2dcae 0%, #c79c52 100%);
  --mark-ink: #1a1710;
  background:
    radial-gradient(74% 50% at 22% 6%, rgba(216,184,119,.20) 0%, rgba(216,184,119,0) 62%),
    linear-gradient(156deg, #1a1710 0%, #3b3020 54%, #110f09 100%);
}
""",
    "lotus": r"""
.cover {
  --ink: #fdf3f6;
  --muted: rgba(232,204,214,.76);
  --accent: #f0c987;
  --fade: rgba(240,201,135,0);
  --hairline: rgba(246,224,232,.18);
  --mark-fill: linear-gradient(135deg, #f7dcb2 0%, #d4915c 100%);
  --mark-ink: #1d0f1a;
  background:
    radial-gradient(68% 48% at 80% 6%, rgba(226,128,150,.26) 0%, rgba(226,128,150,0) 62%),
    linear-gradient(158deg, #1d0f1a 0%, #4b1c34 52%, #140912 100%);
}
""",
    "silence": r"""
.cover {
  --ink: #f0faf6;
  --muted: rgba(186,214,202,.74);
  --accent: #a8ccbd;
  --fade: rgba(168,204,189,0);
  --hairline: rgba(214,238,228,.18);
  --mark-fill: linear-gradient(135deg, #d6efe3 0%, #7fae9c 100%);
  --mark-ink: #0b1a18;
  background:
    radial-gradient(70% 46% at 76% 10%, rgba(120,190,172,.22) 0%, rgba(120,190,172,0) 60%),
    linear-gradient(154deg, #0b1a18 0%, #173630 52%, #071211 100%);
}
""",
    "sunset": r"""
.cover {
  --ink: #fdf6ec;
  --muted: rgba(214,214,236,.76);
  --accent: #f2c078;
  --fade: rgba(242,192,120,0);
  --hairline: rgba(238,230,248,.18);
  --mark-fill: linear-gradient(135deg, #fbdcab 0%, #d99a4e 100%);
  --mark-ink: #0e1730;
  background:
    radial-gradient(60% 42% at 74% 20%, rgba(242,192,120,.30) 0%, rgba(242,192,120,0) 58%),
    linear-gradient(160deg, #0e1730 0%, #263457 50%, #090e1e 100%);
}
""",
    # 화엄경 — one field per 회, all of them jewel-lit but none the same colour.
    "ocean": r"""
.cover {
  --ink: #fcfeff; --muted: rgba(206,226,240,.74); --accent: #8fd4dc;
  --fade: rgba(143,212,220,0); --hairline: rgba(226,240,250,.18);
  --mark-fill: linear-gradient(135deg, #cbeef2 0%, #5aa8b4 100%); --mark-ink: #08202a;
  background:
    radial-gradient(84% 56% at 78% 8%, rgba(96,196,214,.28) 0%, rgba(96,196,214,0) 62%),
    linear-gradient(158deg, #08151f 0%, #0f2e42 50%, #061119 100%);
}
""",
    "radiance": r"""
.cover {
  --ink: #fdfbf5; --muted: rgba(222,226,236,.76); --accent: #f2d79a;
  --fade: rgba(242,215,154,0); --hairline: rgba(240,238,246,.18);
  --mark-fill: linear-gradient(135deg, #fbeac2 0%, #d3a961 100%); --mark-ink: #0a1826;
  background:
    radial-gradient(62% 46% at 76% 10%, rgba(242,215,154,.30) 0%, rgba(242,215,154,0) 62%),
    linear-gradient(158deg, #0a1826 0%, #183c58 50%, #071220 100%);
}
""",
    "summit": r"""
.cover {
  --ink: #faf7ff; --muted: rgba(214,206,238,.76); --accent: #d8cef2;
  --fade: rgba(216,206,242,0); --hairline: rgba(232,226,250,.18);
  --mark-fill: linear-gradient(135deg, #e9e2fa 0%, #9f92c8 100%); --mark-ink: #14112a;
  background:
    radial-gradient(64% 44% at 74% 12%, rgba(160,142,206,.28) 0%, rgba(160,142,206,0) 62%),
    linear-gradient(158deg, #14112a 0%, #2e2752 50%, #0f0d1f 100%);
}
""",
    "store": r"""
.cover {
  --ink: #f4fbf6; --muted: rgba(190,220,204,.76); --accent: #c6e8d6;
  --fade: rgba(198,232,214,0); --hairline: rgba(220,242,230,.18);
  --mark-fill: linear-gradient(135deg, #dcf3e6 0%, #86b8a0 100%); --mark-ink: #08201a;
  background:
    radial-gradient(66% 46% at 76% 10%, rgba(120,196,166,.24) 0%, rgba(120,196,166,0) 60%),
    linear-gradient(156deg, #08201a 0%, #123f33 52%, #061713 100%);
}
""",
    "turning": r"""
.cover {
  --ink: #fdf4ef; --muted: rgba(230,202,192,.76); --accent: #f0be8c;
  --fade: rgba(240,190,140,0); --hairline: rgba(246,224,214,.18);
  --mark-fill: linear-gradient(135deg, #fadcbe 0%, #cf8a58 100%); --mark-ink: #24101a;
  background:
    radial-gradient(66% 46% at 78% 8%, rgba(224,132,110,.26) 0%, rgba(224,132,110,0) 62%),
    linear-gradient(158deg, #24101a 0%, #5a2130 50%, #180a11 100%);
}
""",
    "returning": r"""
.cover {
  --ink: #fbf0f2; --muted: rgba(226,192,200,.76); --accent: #e5a0a8;
  --fade: rgba(229,160,168,0); --hairline: rgba(242,214,220,.18);
  --mark-fill: linear-gradient(135deg, #f6ccd2 0%, #b8707c 100%); --mark-ink: #1c0a13;
  background:
    radial-gradient(62% 44% at 74% 10%, rgba(190,90,110,.26) 0%, rgba(190,90,110,0) 60%),
    linear-gradient(158deg, #1c0a13 0%, #431424 52%, #120610 100%);
}
""",
    "grounds": r"""
.cover {
  --ink: #fbf8ec; --muted: rgba(214,212,180,.76); --accent: #d8c484;
  --fade: rgba(216,196,132,0); --hairline: rgba(238,234,208,.18);
  --mark-fill: linear-gradient(135deg, #eee2b4 0%, #a89354 100%); --mark-ink: #101c14;
  background:
    radial-gradient(66% 46% at 76% 8%, rgba(180,190,110,.20) 0%, rgba(180,190,110,0) 60%),
    linear-gradient(156deg, #101c14 0%, #223a26 52%, #0b140f 100%);
}
""",
    "countless": r"""
.cover {
  --ink: #f6faff; --muted: rgba(198,214,232,.76); --accent: #d6e4f4;
  --fade: rgba(214,228,244,0); --hairline: rgba(226,238,250,.18);
  --mark-fill: linear-gradient(135deg, #e6eefa 0%, #91a8c2 100%); --mark-ink: #0a1420;
  background:
    radial-gradient(70% 48% at 78% 10%, rgba(150,182,216,.24) 0%, rgba(150,182,216,0) 62%),
    linear-gradient(154deg, #0a1420 0%, #1b2f45 52%, #070d16 100%);
}
""",
    "emergence": r"""
.cover {
  --ink: #fdf7ee; --muted: rgba(216,212,224,.76); --accent: #f6c47c;
  --fade: rgba(246,196,124,0); --hairline: rgba(240,232,238,.18);
  --mark-fill: linear-gradient(135deg, #fbdfb4 0%, #cf9550 100%); --mark-ink: #101528;
  background:
    radial-gradient(60% 44% at 74% 16%, rgba(246,196,124,.30) 0%, rgba(246,196,124,0) 60%),
    linear-gradient(160deg, #101528 0%, #2b2b48 50%, #0b0d1a 100%);
}
""",
    "beyond": r"""
.cover {
  --ink: #f7f6f0; --muted: rgba(198,196,180,.76); --accent: #c8b07c;
  --fade: rgba(200,176,124,0); --hairline: rgba(230,228,216,.18);
  --mark-fill: linear-gradient(135deg, #e4d6b0 0%, #94804e 100%); --mark-ink: #0c1114;
  background:
    radial-gradient(64% 44% at 76% 10%, rgba(150,150,140,.20) 0%, rgba(150,150,140,0) 60%),
    linear-gradient(156deg, #0c1114 0%, #1e262a 52%, #080b0d 100%);
}
""",
    "setting": r"""
.cover {
  --ink: #fbfaf2; --muted: rgba(206,216,220,.76); --accent: #e6d6a6;
  --fade: rgba(230,214,166,0); --hairline: rgba(234,238,238,.18);
  --mark-fill: linear-gradient(135deg, #f2e6c2 0%, #a89a64 100%); --mark-ink: #0a1a20;
  background:
    radial-gradient(64% 44% at 74% 12%, rgba(150,200,206,.24) 0%, rgba(150,200,206,0) 60%),
    linear-gradient(158deg, #0a1a20 0%, #1a3a42 52%, #071216 100%);
}
""",
    "meetings": r"""
.cover {
  --ink: #f9f7fd; --muted: rgba(208,200,228,.76); --accent: #e0d4f6;
  --fade: rgba(224,212,246,0); --hairline: rgba(234,228,246,.18);
  --mark-fill: linear-gradient(135deg, #ece2fb 0%, #9c8cc0 100%); --mark-ink: #131630;
  background:
    radial-gradient(64% 44% at 76% 12%, rgba(140,138,206,.26) 0%, rgba(140,138,206,0) 60%),
    linear-gradient(158deg, #131630 0%, #2c2a58 52%, #0d0e20 100%);
}
""",
    "tower": r"""
.cover {
  --ink: #fdf6ee; --muted: rgba(226,204,196,.76); --accent: #f2ce96;
  --fade: rgba(242,206,150,0); --hairline: rgba(244,226,214,.18);
  --mark-fill: linear-gradient(135deg, #fae0bc 0%, #c48f52 100%); --mark-ink: #1e1220;
  background:
    radial-gradient(64% 46% at 76% 10%, rgba(216,140,120,.24) 0%, rgba(216,140,120,0) 60%),
    linear-gradient(158deg, #1e1220 0%, #46243c 52%, #140c16 100%);
}
""",
}


# The Indra's-net lattice every 화엄경 volume shares, under its own figure.
COVER_GROUNDS = {
    "": "",
    "net": r"""
.cover-ground {
  background-image: radial-gradient(rgba(226,214,186,.30) .26mm, rgba(0,0,0,0) .27mm);
  background-size: 6.4mm 6.4mm;
  -webkit-mask-image: radial-gradient(96% 68% at 80% 10%, #000 0%, rgba(0,0,0,.38) 46%, rgba(0,0,0,0) 80%);
  mask-image: radial-gradient(96% 68% at 80% 10%, #000 0%, rgba(0,0,0,.38) 46%, rgba(0,0,0,0) 80%);
}
""",
}


COVER_MOTIFS = {
    # 금강경 — cut facets of the diamond that cuts everything else.
    "facets": r"""
.cover-motif::before, .cover-motif::after, .cover-motif span::before {
  content: '';
  position: absolute;
  border: .3mm solid rgba(207,216,227,.32);
  transform: rotate(45deg);
}
.cover-motif::before { top: -22mm; right: -18mm; width: 92mm; height: 92mm; }
.cover-motif::after { top: 8mm; right: 14mm; width: 46mm; height: 46mm; border-color: rgba(207,216,227,.5); }
.cover-motif span::before { top: 24mm; right: 32mm; width: 16mm; height: 16mm; border-color: rgba(232,240,250,.66); }
""",
    # 반야심경 — one unclosed stroke: the circle that holds nothing.
    "enso": r"""
.cover-motif::before {
  content: '';
  position: absolute;
  top: -20mm;
  right: -20mm;
  width: 100mm;
  height: 100mm;
  border-radius: 50%;
  border: .55mm solid rgba(232,226,242,.44);
  border-right-color: rgba(0,0,0,0);
  transform: rotate(122deg);
}
.cover-motif::after {
  content: '';
  position: absolute;
  top: 26mm;
  right: 26mm;
  width: 8mm;
  height: 8mm;
  border-radius: 50%;
  background: rgba(232,226,242,.22);
}
""",
    # 법구경 — verse after verse, ruled lines fading out at both edges.
    "verses": r"""
.cover-motif::before {
  content: '';
  position: absolute;
  top: 20mm;
  right: -8mm;
  width: 98mm;
  height: 78mm;
  background: repeating-linear-gradient(180deg,
    rgba(220,188,124,.38) 0 .3mm, rgba(0,0,0,0) .3mm 7.2mm);
  -webkit-mask-image: linear-gradient(90deg, rgba(0,0,0,0) 0%, #000 42%, #000 76%, rgba(0,0,0,0) 100%);
  mask-image: linear-gradient(90deg, rgba(0,0,0,0) 0%, #000 42%, #000 76%, rgba(0,0,0,0) 100%);
}
""",
    # 법화경 — three ellipses crossing at one centre make the opened lotus.
    "petals": r"""
.cover-motif::before, .cover-motif::after, .cover-motif span::before {
  content: '';
  position: absolute;
  top: -16mm;
  right: 4mm;
  width: 58mm;
  height: 98mm;
  border-radius: 50%;
  border: .3mm solid rgba(240,201,135,.36);
}
.cover-motif::after { transform: rotate(60deg); }
.cover-motif span::before { transform: rotate(-60deg); }
""",
    # 유마경 — two squares, neither inside nor outside the other: 不二.
    "chamber": r"""
.cover-motif::before, .cover-motif::after {
  content: '';
  position: absolute;
  width: 64mm;
  height: 64mm;
  border: .32mm solid rgba(168,204,189,.42);
}
.cover-motif::before { top: 0; right: 28mm; }
.cover-motif::after { top: 22mm; right: 6mm; border-color: rgba(168,204,189,.24); }
""",
    # 정토삼부경 — the sun setting due west, and the land beneath it.
    "horizon": r"""
.cover-motif::before {
  content: '';
  position: absolute;
  top: 12mm;
  right: 18mm;
  width: 54mm;
  height: 54mm;
  border-radius: 50%;
  border: .3mm solid rgba(242,192,120,.52);
  background: radial-gradient(circle, rgba(242,192,120,.30) 0%, rgba(242,192,120,.05) 60%, rgba(242,192,120,0) 70%);
}
.cover-motif::after {
  content: '';
  position: absolute;
  top: 39mm;
  left: 0;
  right: 0;
  height: .3mm;
  background: linear-gradient(90deg, rgba(242,192,120,0) 0%, rgba(242,192,120,.55) 38%, rgba(242,192,120,.55) 78%, rgba(242,192,120,0) 100%);
}
""",
    # 제1회 적멸도량회 — 향수해 위에 겹겹이 뜬 화장장엄세계.
    "worlds": r"""
.cover-motif::before, .cover-motif::after, .cover-motif span::before {
  content: ''; position: absolute; border-radius: 50%;
  border: .28mm solid rgba(143,212,220,.34);
}
.cover-motif::before { top: -34mm; right: -30mm; width: 122mm; height: 122mm; }
.cover-motif::after { top: -12mm; right: -8mm; width: 78mm; height: 78mm; border-color: rgba(143,212,220,.24); }
.cover-motif span::before { top: 8mm; right: 12mm; width: 38mm; height: 38mm; border-color: rgba(206,242,246,.52); }
""",
    # 제2회 보광명전회 — 부처의 발바닥에서 나가 시방을 치는 광명.
    "rays": r"""
.cover-motif::before {
  content: ''; position: absolute; top: -44mm; right: -44mm;
  width: 136mm; height: 136mm; border-radius: 50%;
  background: repeating-conic-gradient(from 4deg at 50% 50%,
    rgba(242,215,154,.34) 0deg .45deg, rgba(0,0,0,0) .45deg 11deg);
  -webkit-mask-image: radial-gradient(circle at 50% 50%, #000 10%, rgba(0,0,0,.46) 50%, rgba(0,0,0,0) 74%);
  mask-image: radial-gradient(circle at 50% 50%, #000 10%, rgba(0,0,0,.46) 50%, rgba(0,0,0,0) 74%);
}
.cover-motif::after {
  content: ''; position: absolute; top: 12mm; right: 14mm;
  width: 16mm; height: 16mm; border-radius: 50%;
  background: radial-gradient(circle, rgba(250,236,200,.5) 0%, rgba(250,236,200,0) 70%);
}
""",
    # 제3회 도리천궁회 — 수미산 꼭대기로 오르는 자리.
    "summit": r"""
.cover-motif::before, .cover-motif::after {
  content: ''; position: absolute; width: 0; height: 0;
  border-left: 46mm solid rgba(0,0,0,0); border-right: 46mm solid rgba(0,0,0,0);
  border-bottom: 56mm solid rgba(198,186,238,.13);
}
.cover-motif::before { top: 4mm; right: -18mm; }
.cover-motif::after {
  top: 26mm; right: 14mm;
  border-left-width: 28mm; border-right-width: 28mm;
  border-bottom-width: 34mm; border-bottom-color: rgba(224,216,250,.20);
}
""",
    # 제4회 야마천궁회 — 십행과 다함없는 열 곳간이 나란히 선다.
    "store": r"""
.cover-motif::before {
  content: ''; position: absolute; top: 8mm; right: -4mm; width: 92mm; height: 66mm;
  background: repeating-linear-gradient(90deg,
    rgba(198,232,214,.36) 0 .3mm, rgba(0,0,0,0) .3mm 9.1mm);
  -webkit-mask-image: linear-gradient(180deg, #000 0%, #000 52%, rgba(0,0,0,0) 100%);
  mask-image: linear-gradient(180deg, #000 0%, #000 52%, rgba(0,0,0,0) 100%);
}
.cover-motif::after {
  content: ''; position: absolute; top: 8mm; right: -4mm; width: 92mm; height: .28mm;
  background: linear-gradient(90deg, rgba(198,232,214,0) 0%, rgba(198,232,214,.5) 24%, rgba(198,232,214,.5) 88%, rgba(198,232,214,0) 100%);
}
""",
    # 제5회 상 — 회향(廻向), 공덕이 바깥으로 돌아 나간다.
    "turning": r"""
.cover-motif::before, .cover-motif::after, .cover-motif span::before {
  content: ''; position: absolute; top: -14mm; right: 2mm;
  width: 54mm; height: 92mm; border-radius: 50%;
  border: .3mm solid rgba(240,190,140,.36);
}
.cover-motif::after { transform: rotate(42deg) scale(.76); border-color: rgba(240,190,140,.26); }
.cover-motif span::before { transform: rotate(84deg) scale(.54); border-color: rgba(250,220,190,.5); }
""",
    # 제5회 하 — 같은 회향이 안으로 돌아 든다. 상권의 거울상.
    "returning": r"""
.cover-motif::before, .cover-motif::after, .cover-motif span::before {
  content: ''; position: absolute; top: -14mm; right: 2mm;
  width: 54mm; height: 92mm; border-radius: 50%;
  border: .3mm solid rgba(229,160,168,.36);
}
.cover-motif::after { transform: rotate(-42deg) scale(.76); border-color: rgba(229,160,168,.26); }
.cover-motif span::before { transform: rotate(-84deg) scale(.54); border-color: rgba(246,204,210,.5); }
""",
    # 제6회 타화자재천궁회 — 환희지에서 법운지까지 열 층의 지(地).
    "terraces": r"""
.cover-motif::before, .cover-motif::after, .cover-motif span::before {
  content: ''; position: absolute; border-radius: 1.6mm;
  border: .3mm solid rgba(216,196,132,.34);
}
.cover-motif::before { top: 0; right: -10mm; width: 100mm; height: 26mm; }
.cover-motif::after { top: 21mm; right: 2mm; width: 76mm; height: 26mm; border-color: rgba(230,214,160,.26); }
.cover-motif span::before { top: 42mm; right: 16mm; width: 50mm; height: 26mm; border-color: rgba(244,232,190,.46); }
""",
    # 제7회 상 — 아승기, 헤아려도 끝나지 않는 수의 되풀이.
    "countless": r"""
.cover-motif::before, .cover-motif::after, .cover-motif span::before, .cover-motif span::after {
  content: ''; position: absolute; border: .26mm solid rgba(214,228,244,.34);
}
.cover-motif::before { top: -12mm; right: -14mm; width: 100mm; height: 100mm; }
.cover-motif::after { top: 10mm; right: 8mm; width: 56mm; height: 56mm; }
.cover-motif span::before { top: 25mm; right: 23mm; width: 26mm; height: 26mm; border-color: rgba(226,238,250,.5); }
.cover-motif span::after { top: 32mm; right: 30mm; width: 12mm; height: 12mm; border-color: rgba(238,246,255,.66); }
""",
    # 제7회 하 — 여래출현품, 몸이 광배를 두르고 나타난다.
    "emergence": r"""
.cover-motif::before {
  content: ''; position: absolute; top: 10mm; right: 14mm;
  width: 56mm; height: 56mm; border-radius: 50%;
  border: .3mm solid rgba(246,196,124,.52);
  background: radial-gradient(circle, rgba(246,196,124,.30) 0%, rgba(246,196,124,.04) 60%, rgba(246,196,124,0) 72%);
}
.cover-motif::after {
  content: ''; position: absolute; top: -8mm; right: -4mm;
  width: 88mm; height: 88mm; border-radius: 50%;
  border: .24mm solid rgba(246,196,124,.26);
}
""",
    # 제8회 보광명전 삼회 — 이세간품, 선이 틀을 넘어 지나간다.
    "beyond": r"""
.cover-motif::before {
  content: ''; position: absolute; top: 4mm; right: 12mm;
  width: 64mm; height: 64mm; border: .32mm solid rgba(200,176,124,.42);
}
.cover-motif::after, .cover-motif span::before {
  content: ''; position: absolute; right: -18mm; width: 112mm; height: .28mm;
  background: linear-gradient(90deg, rgba(200,176,124,0) 0%, rgba(200,176,124,.55) 28%, rgba(200,176,124,.55) 72%, rgba(200,176,124,0) 100%);
}
.cover-motif::after { top: 20mm; }
.cover-motif span::before { top: 50mm; opacity: .66; }
""",
    # 제9회 상 — 선재가 문수를 만나고 남쪽으로 길을 떠난다.
    "setting": r"""
.cover-motif::before {
  content: ''; position: absolute; top: -24mm; right: -34mm;
  width: 126mm; height: 126mm; border-radius: 50%;
  border: .32mm solid rgba(230,214,166,.32);
  border-top-color: rgba(0,0,0,0); border-left-color: rgba(0,0,0,0);
}
.cover-motif::after {
  content: ''; position: absolute; top: 12mm; right: 20mm;
  width: 5mm; height: 5mm; border-radius: 50%;
  background: rgba(244,232,196,.78);
}
""",
    # 제9회 중 — 선지식에서 선지식으로, 만남이 이어진다.
    "meetings": r"""
.cover-motif::before {
  content: ''; position: absolute; top: 16mm; right: -8mm; width: 100mm; height: 7mm;
  background-image: radial-gradient(circle, rgba(224,212,246,.62) .72mm, rgba(0,0,0,0) .74mm);
  background-size: 9.4mm 7mm;
  -webkit-mask-image: linear-gradient(90deg, rgba(0,0,0,0) 0%, #000 26%, #000 86%, rgba(0,0,0,0) 100%);
  mask-image: linear-gradient(90deg, rgba(0,0,0,0) 0%, #000 26%, #000 86%, rgba(0,0,0,0) 100%);
}
.cover-motif::after {
  content: ''; position: absolute; top: 19.4mm; right: -8mm; width: 100mm; height: .24mm;
  background: linear-gradient(90deg, rgba(224,212,246,0) 0%, rgba(224,212,246,.42) 26%, rgba(224,212,246,.42) 86%, rgba(224,212,246,0) 100%);
}
""",
    # 제9회 하 — 미륵의 누각이 열리자 그 안에 또 누각이 있다.
    "tower": r"""
.cover-motif::before, .cover-motif::after, .cover-motif span::before {
  content: ''; position: absolute; border: .3mm solid rgba(242,206,150,.38);
  border-bottom: none; border-radius: 50% 50% 0 0 / 24% 24% 0 0;
}
.cover-motif::before { top: 0; right: 4mm; width: 84mm; height: 80mm; }
.cover-motif::after { top: 15mm; right: 19mm; width: 54mm; height: 65mm; border-color: rgba(246,222,180,.3); }
.cover-motif span::before { top: 31mm; right: 32mm; width: 28mm; height: 49mm; border-color: rgba(252,238,212,.52); }
""",
}


def cover_css(book: Book, paper: dict[str, str]) -> str:
    """Return one book's cover stylesheet: shared layout, own palette and motif."""
    if book.cover_palette not in COVER_PALETTES:
        raise ValueError(f"지원하지 않는 표지 색조입니다: {book.cover_palette}")
    if book.cover_motif not in COVER_MOTIFS:
        raise ValueError(f"지원하지 않는 표지 도형입니다: {book.cover_motif}")
    if book.cover_ground not in COVER_GROUNDS:
        raise ValueError(f"지원하지 않는 표지 바탕입니다: {book.cover_ground}")
    base = (
        COVER_BASE_CSS.replace("COVER_WIDTH", paper["width"])
        .replace("COVER_HEIGHT", paper["height"])
        .replace("COVER_PADDING", paper["cover_padding_modern"])
        .replace("COVER_TITLE_SIZE", paper["cover_title_size_modern"])
    )
    return (
        base
        + COVER_PALETTES[book.cover_palette]
        + COVER_GROUNDS[book.cover_ground]
        + COVER_MOTIFS[book.cover_motif]
    )


def stylesheet(book: Book) -> str:
    paper = {
        "A4": {
            "width": "210mm",
            "height": "297mm",
            "page_margin": "22mm 20mm 23mm 22mm",
            "cover_padding": "34mm 25mm 28mm",
            "cover_padding_modern": "26mm 24mm 24mm",
            "cover_title_size": "31pt",
            "cover_title_size_modern": "37pt",
            "body_size": "10pt",
            "original_size": "10.8pt",
            "table_size": "8.8pt",
        },
        "A5": {
            "width": "148mm",
            "height": "210mm",
            "page_margin": "18mm 16mm 19mm 18mm",
            "cover_padding": "26mm 18mm 22mm",
            "cover_padding_modern": "20mm 17mm 18mm",
            "cover_title_size": "25pt",
            "cover_title_size_modern": "29pt",
            "body_size": "9.4pt",
            "original_size": "10.4pt",
            "table_size": "8.5pt",
        },
    }.get(book.paper_size)
    if paper is None:
        raise ValueError(f"지원하지 않는 용지 규격입니다: {book.paper_size}")
    safe_title = book.running_title.replace('"', "")
    return f"""
/* Noto Serif KR and Noto Sans KR are installed in Windows, so name them
   directly rather than wrapping them in an @font-face.  Edge subsets and
   embeds them into the PDF; Batang and the generic families only catch the
   few glyphs Noto does not carry. */
@page {{
  size: {book.paper_size};
  margin: {paper["page_margin"]};
  @top-center {{
    content: '{safe_title}';
    font-family: 'Noto Sans KR', sans-serif;
    font-size: 7.5pt;
    color: #756f65;
    letter-spacing: .12em;
  }}
  @bottom-center {{
    content: counter(page);
    font-family: 'Noto Sans KR', sans-serif;
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
  font-family: 'Noto Serif KR', 'Batang', serif;
  font-size: {paper["body_size"]};
  line-height: 1.86;
  word-break: keep-all;
  overflow-wrap: break-word;
  text-rendering: optimizeLegibility;
}}
{cover_css(book, paper)}.ai-notice {{
  margin: 0 0 9mm;
  padding: 4mm 5mm;
  border-left: .6mm solid #b08d4a;
  background: #f6f1e4;
  font: 400 8.6pt/1.7 'Noto Sans KR', sans-serif;
  color: #5c5346;
}}
.toc {{ break-after: page; padding-top: 7mm; }}
.toc h2 {{ break-before: auto; margin-top: 0; }}
.toc ol {{ list-style: none; padding: 0; margin: 8mm 0 0; }}
.toc li {{ margin: 0; border-bottom: .2mm solid #ddd6ca; break-inside: avoid; }}
.toc a {{ display: block; padding: 1.4mm 0; color: inherit; text-decoration: none; font: 500 8.7pt/1.45 'Noto Sans KR', sans-serif; }}
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
  font: 650 11.5pt/1.55 'Noto Sans KR', sans-serif;
  letter-spacing: .03em;
}}
p {{ margin: 0 0 3.7mm; text-align: justify; orphans: 3; widows: 3; }}
a {{ color: #6b4432; text-decoration-thickness: .2mm; text-underline-offset: .5mm; }}
code {{
  font-family: 'Noto Sans KR', sans-serif;
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
  font-family: 'Noto Serif KR', 'Batang', serif;
  font-size: {paper["original_size"]};
  line-height: 2;
  text-align: justify;
}}
.translation-section p {{ padding-left: 4mm; border-left: .7mm solid #c7aa7a; }}
.labeled {{ margin: 0 0 4mm; padding: 3.2mm 4mm; break-inside: avoid; }}
.labeled-title {{
  margin-bottom: 1.4mm;
  color: #654838;
  font: 700 8.5pt/1.4 'Noto Sans KR', sans-serif;
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
table {{ width: 100%; margin: 4mm 0 6mm; border-collapse: collapse; font: 400 {paper["table_size"]}/1.58 'Noto Sans KR', sans-serif; }}
thead {{ display: table-header-group; }}
tr {{ break-inside: avoid; }}
th {{ color: #fff; background: #73503c; font-weight: 650; }}
th, td {{ padding: 2.2mm 2.5mm; border: .2mm solid #d8d0c4; vertical-align: top; }}
tbody tr:nth-child(even) {{ background: #f8f5ef; }}
.ornament {{ margin: 8mm 0; text-align: center; color: #a87945; break-after: avoid; }}
.subsection {{ break-inside: auto; }}
.book-dhammapada .verse-section {{
  break-inside: avoid-page;
  page-break-inside: avoid;
}}
.book-lotus .passage-section,
.book-vimalakirti .passage-section,
.book-avatamsaka .passage-section {{
  break-inside: avoid-page;
  page-break-inside: avoid;
}}
strong {{ font-weight: 700; }}
@media screen {{
  body {{ width: {paper["width"]}; margin: 10mm auto; box-shadow: 0 2mm 9mm rgba(0,0,0,.15); }}
}}
"""


def cover_html(book: Book, footer: str) -> str:
    """Return the cover markup: mark, hanja eyebrow, title, seal, AI notice."""
    eyebrow = (
        f'\n    <p class="cover-eyebrow">{html.escape(book.cover_hanja)}</p>'
        if book.cover_hanja
        else ""
    )
    mark = (
        f'\n  <span class="cover-mark">{html.escape(book.cover_mark)}</span>'
        if book.cover_mark
        else ""
    )
    return f"""<section class="cover">
  <div class="cover-ground" aria-hidden="true"></div>
  <div class="cover-motif" aria-hidden="true"><span></span></div>
  <div class="cover-top">{mark}
    <span class="cover-kicker">불교 경전 우리말 해설</span>
  </div>
  <div class="cover-main">{eyebrow}
    <h1>{html.escape(book.title)}</h1>
    <div class="cover-rule" aria-hidden="true"></div>
    <p class="subtitle">{html.escape(book.subtitle)}</p>
    <div class="seal">{html.escape(book.cover_text)}</div>
  </div>
  <div class="cover-footer">
    <span class="cover-ai">{html.escape(AI_BADGE)}</span><br>{footer}
  </div>
</section>"""


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
<style>{stylesheet(book)}</style>
</head>
<body class="book-{html.escape(book.composite, quote=True)}">
{cover_html(book, footer)}
{toc}
<p class="ai-notice">{html.escape(AI_NOTICE)}</p>
<main>{body}</main>
</body>
</html>"""


def windows_path(path: Path) -> str:
    """Return the Windows form of a path, converting only when running on WSL."""
    resolved = str(path.resolve())
    if not resolved.startswith("/"):
        return resolved
    result = subprocess.run(
        ["wslpath", "-w", resolved],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def windows_file_uri(path: Path) -> str:
    value = windows_path(path).replace("\\", "/")
    return "file:///" + quote(value, safe="/:~")


def await_rendered_pdf(path: Path, previous_mtime: int | None, timeout: float) -> None:
    """Wait until Edge has finished writing the PDF.

    Under WSL the interop wrapper blocks until Edge exits, but the native
    Windows ``msedge.exe`` is only a launcher: it returns at once and the real
    browser writes the file a moment later.  Wait for a fresh file whose size
    has stopped growing so both environments behave the same way.
    """
    deadline = time.monotonic() + timeout
    stable_size: int | None = None
    while time.monotonic() < deadline:
        if path.exists():
            stat = path.stat()
            is_fresh = previous_mtime is None or stat.st_mtime_ns != previous_mtime
            if is_fresh and stat.st_size >= 10_000:
                if stable_size == stat.st_size:
                    return
                stable_size = stat.st_size
        time.sleep(0.5)
    raise TimeoutError(f"PDF가 제한 시간 안에 생성되지 않았습니다: {path}")


def render_pdf(book: Book, keep_html: bool = False) -> Path:
    edge = find_edge()
    if not book.source.exists():
        raise FileNotFoundError(f"원본 문서를 찾을 수 없습니다: {book.source}")
    if book.composite == "dhammapada":
        dhammapada_chapter_files()
    elif book.composite in CHAPTER_BOOKS:
        chapter_files(*CHAPTER_BOOKS[book.composite])
    elif book.composite == "pureland":
        pureland_sections()
    elif book.composite == "avatamsaka":
        avatamsaka_chapter_files(book.fascicles)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html_path = OUTPUT_DIR / f".{book.output.stem}.html"
    html_path.write_text(book_html(book), encoding="utf-8")
    profile = Path(tempfile.mkdtemp(prefix=".edge-profile-", dir=OUTPUT_DIR))
    command = [
        str(edge),
        "--headless=new",
        "--disable-gpu",
        "--disable-extensions",
        "--no-first-run",
        "--no-pdf-header-footer",
        f"--user-data-dir={windows_path(profile)}",
        f"--print-to-pdf={windows_path(book.output)}",
        windows_file_uri(html_path),
    ]
    previous_mtime = book.output.stat().st_mtime_ns if book.output.exists() else None
    try:
        subprocess.run(
            command, check=True, capture_output=True, timeout=book.render_timeout
        )
        await_rendered_pdf(book.output, previous_mtime, timeout=book.render_timeout)
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
    # 화엄경 is thirteen volumes, so "화엄경" selects the whole set and
    # "화엄경05" a single book; every other scripture answers to its own name.
    names = dict.fromkeys(
        [*(book.selector for book in BOOKS), *(book.key for book in BOOKS)]
    )
    parser.add_argument(
        "--book",
        choices=["all", *names],
        default="all",
        help="특정 경전만 만들려면 경전 이름을, 화엄경의 한 책만 만들려면 "
        "화엄경05처럼 책 번호까지 지정합니다.",
    )
    args = parser.parse_args()
    selected = (
        BOOKS
        if args.book == "all"
        else tuple(book for book in BOOKS if args.book in (book.key, book.selector))
    )
    for book in selected:
        output = render_pdf(book, keep_html=args.keep_html)
        print(
            f"생성: {output.relative_to(ROOT)} "
            f"({book.paper_size}, {output.stat().st_size:,} bytes)"
        )


if __name__ == "__main__":
    main()
