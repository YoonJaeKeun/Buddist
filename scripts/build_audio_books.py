#!/usr/bin/env python3
"""Build MP3 listening albums from each scripture's 우리말 풀이 and 해설.

The albums are made for phones.  Every track carries ID3 tags and each album
gets an M3U playlist, so Apple Music, the Files app or VLC show a scripture as
one book with numbered chapters.  Two albums are written per scripture:

``풀이+해설``  큰목차와 소목차를 안내한 뒤 단락마다 우리말 풀이와 해설을 잇는다.
``풀이만``     같은 트랙 구분에서 해설만 빼고 읽는다.

Both albums share track numbers and titles, so switching albums while
listening lands on the same passage — that is how 해설을 듣거나 빼는 선택이
재생 도중에도 가능해진다.

Three voices keep the layers apart without spoken labels: 안내는 현수, 풀이는
선히, 해설은 인준.  한자 인용은 ``전문_한자음`` 대조표의 독음으로 바꾸어 읽는다.

Speech comes from ``edge-tts`` (``pip install edge-tts``) — the one dependency
outside the standard library — so the build needs a network connection.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_scripture_pdfs import AI_NOTICE, BOOKS, Book, book_markdown  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
AUDIO_DIR = ROOT / "불교_경전" / "오디오"
CACHE_DIR = ROOT / ".cache" / "audio"
READING_TABLES = ROOT / "불교_경전" / "전문_한자음"

VOICE_TITLE = "ko-KR-HyunsuMultilingualNeural"
VOICE_READING = "ko-KR-SunHiNeural"
VOICE_COMMENTARY = "ko-KR-InJoonNeural"

# edge-tts always answers with MPEG-2 Layer III, 24kHz, 48kbps, mono: every
# frame is 144 bytes and lasts 24ms.  A frame whose side info is zeroed decodes
# to silence, which is how the pauses between segments are made.
FRAME_BYTES = 144
FRAME_MS = 24
SILENT_FRAME = bytes.fromhex("fff364c4") + bytes(FRAME_BYTES - 4)

# 트랙을 나눌 때 쓰는 셈 단위.  값을 바꾸면 트랙 경계가 움직여 이미 만든 음성을
# 통째로 다시 구워야 하므로 그대로 둔다.
CHARS_PER_MINUTE = 300.0
# 실제로 만든 2,252트랙에서 잰 낭독 속도.  분량을 어림하는 데만 쓴다.
SPOKEN_CHARS_PER_MINUTE = 420.0
BYTES_PER_MINUTE = 48_000 / 8 * 60  # 48kbps

FLAVORS = {
    "full": ("풀이+해설", True),
    "plain": ("풀이만", False),
}


# --------------------------------------------------------------------------
# 한자 독음
# --------------------------------------------------------------------------

# ``전문_한자음`` 대조표에 없는 이체자들.  표는 저본의 글자를 그대로 싣기 때문에
# 풀이·해설이 쓰는 통용자가 빠지는 자리가 남는다.
EXTRA_READINGS = {
    "爲": "위", "眞": "진", "淸": "청", "卽": "즉", "敎": "교", "衆": "중",
    "廻": "회", "着": "착", "刹": "찰", "隊": "대", "約": "약", "鑑": "감",
    "喙": "훼", "熒": "형", "逞": "령", "澹": "담", "酩": "명", "篤": "독",
    "尅": "극", "儈": "쾌", "泆": "일", "史": "사", "譚": "담", "疏": "소",
    "苔": "태", "渝": "투", "駏": "거", "驉": "허", "㺃": "구", "䨍": "몽",
}

TABLE_SEPARATOR = re.compile(r"^\|\s*:?-{3,}")
ONE_HANJA = re.compile(r"^[㐀-䶿一-鿿豈-﫿]$")
ONE_HANGUL = re.compile(r"^[가-힣]$")
HANJA_RUN = re.compile(r"[㐀-䶿一-鿿豈-﫿]+")


def build_hanja_readings() -> dict[str, str]:
    """Collect 한자 → 한글 독음 from the repository's reading tables.

    The tables print a source line and its per-character reading one above the
    other, so the two rows around a separator line give the pairs.  A character
    read differently in different places keeps its commonest reading, which is
    the best a per-character table can offer.
    """
    counts: dict[str, dict[str, int]] = {}
    for path in sorted(READING_TABLES.rglob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index in range(len(lines) - 2):
            if not lines[index].startswith("|") or not TABLE_SEPARATOR.match(lines[index + 1]):
                continue
            if not lines[index + 2].startswith("|"):
                continue
            source = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
            reading = [cell.strip() for cell in lines[index + 2].strip().strip("|").split("|")]
            if len(source) != len(reading):
                continue
            for glyph, sound in zip(source, reading):
                if ONE_HANJA.match(glyph) and ONE_HANGUL.match(sound):
                    counts.setdefault(glyph, {})
                    counts[glyph][sound] = counts[glyph].get(sound, 0) + 1
    readings = {
        glyph: max(sounds.items(), key=lambda item: item[1])[0]
        for glyph, sounds in counts.items()
    }
    for glyph, sound in EXTRA_READINGS.items():
        readings.setdefault(glyph, sound)
    return readings


def hanja_readings() -> dict[str, str]:
    """Return the reading map, rebuilding the cache when the tables change."""
    cache = CACHE_DIR / "hanja_readings.json"
    newest = max(
        (path.stat().st_mtime_ns for path in READING_TABLES.rglob("*.md")),
        default=0,
    )
    if cache.exists() and cache.stat().st_mtime_ns >= newest:
        return json.loads(cache.read_text(encoding="utf-8"))
    readings = build_hanja_readings()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(readings, ensure_ascii=False), encoding="utf-8")
    return readings


# --------------------------------------------------------------------------
# 문서 읽기
# --------------------------------------------------------------------------

SECTION_LABELS = {"원문": "source", "우리말 풀이": "reading", "해설": "commentary"}
INLINE_LABEL = re.compile(r"^\*\*(원문|우리말 풀이|해설)\*\*:?\s*(.*)$")
PARAGRAPH_HEADING = re.compile(r"^(?:\d+|제\d+게송|제\d+절|품 해제|해제)$")


@dataclass
class Unit:
    """One 단락: its 우리말 풀이 and, when there is one, its 해설."""

    chapter: str
    reading: str
    commentary: str

    def chars(self, with_commentary: bool) -> int:
        return len(self.reading) + (len(self.commentary) if with_commentary else 0)


def parse_units(markdown: str, fallback_chapter: str) -> list[Unit]:
    """Pull every 우리말 풀이 · 해설 pair out of one assembled book.

    Only text under those two labels is kept, so 원문, 얼개 표, 편집 주석은
    낭독에서 빠진다.  소목차는 단락 번호가 아닌 가장 가까운 제목으로 잡는다.
    """
    units: list[Unit] = []
    section = fallback_chapter
    chapter = fallback_chapter
    label: str | None = None
    buckets: dict[str, list[str]] = {"reading": [], "commentary": []}

    def flush() -> None:
        nonlocal label
        reading = "\n".join(buckets["reading"]).strip()
        commentary = "\n".join(buckets["commentary"]).strip()
        if reading or commentary:
            units.append(Unit(chapter, reading, commentary))
        buckets["reading"] = []
        buckets["commentary"] = []
        label = None

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            flush()
            section = chapter = stripped[3:].strip()
            continue
        if stripped.startswith("### "):
            title = stripped[4:].strip()
            if title in SECTION_LABELS:
                label = SECTION_LABELS[title]
                continue
            flush()
            # 단락 번호는 소목차를 그 앞의 큰 제목으로 되돌린다.  「이 구간의
            # 구조」처럼 풀이·해설이 없는 안내 절이 사이에 끼어도 단락이 엉뚱한
            # 이름 아래로 묶이지 않는다.
            chapter = section if PARAGRAPH_HEADING.match(title) else title
            continue
        if stripped.startswith("#"):
            flush()
            continue

        match = INLINE_LABEL.match(stripped)
        if match:
            name, rest = match.group(1), match.group(2).strip()
            if name == "원문" or (name == "우리말 풀이" and buckets["reading"]):
                flush()
            label = SECTION_LABELS[name]
            if rest and label != "source":
                buckets[label].append(rest)
            continue

        if label in (None, "source"):
            continue
        if not stripped or stripped.startswith(("|", ">", "---")):
            continue
        buckets[label].append(stripped)

    flush()
    return units


# --------------------------------------------------------------------------
# 낭독용 문장 다듬기
# --------------------------------------------------------------------------

MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
MARKUP = re.compile(r"[*`_]+")
LIST_MARKER = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s+)")
HANJA_PARENTHESIS = re.compile(
    r"[（(][㐀-䶿一-鿿豈-﫿\s·,，、;；:：/]+[)）]"
)
ROMAN_GLOSS = re.compile(
    r"(?<![가-힣])[A-Za-zÀ-ɏḀ-ỿ]"
    r"[A-Za-zÀ-ɏḀ-ỿ̀-ͯ\s\-’'·.]*"
    r"[（(]([가-힣][^)）]*)[)）]"
)
SPACES = re.compile(r"[ \t]+")
SENTENCE_END = re.compile(r"""[.!?。！？…"'”’」』)\]]$""")


def speak_hanja(text: str, readings: dict[str, str]) -> str:
    """Replace hanja with the Korean reading the source tables give them."""

    def convert(match: re.Match[str]) -> str:
        return "".join(readings.get(glyph, "") for glyph in match.group())

    return HANJA_RUN.sub(convert, text)


def to_speech(text: str, readings: dict[str, str]) -> str:
    """Turn one 풀이·해설 block into plain prose a voice can read.

    Markdown 표기, 표, 링크는 걷어내고 한자는 독음으로 바꾼다.  괄호 속 한자와,
    한글 음이 뒤따르는 로마자 표기는 같은 말을 두 번 읽게 하므로 한쪽만 남긴다.
    """
    lines: list[str] = []
    for raw in text.splitlines():
        line = MARKDOWN_LINK.sub(r"\1", raw.strip())
        line = LIST_MARKER.sub("", line)
        line = MARKUP.sub("", line)
        line = ROMAN_GLOSS.sub(r"\1", line)
        line = HANJA_PARENTHESIS.sub("", line)
        line = speak_hanja(line, readings)
        line = line.replace("—", ", ").replace("–", ", ").replace("·", ", ")
        for bracket in "《》〈〉「」『』":
            line = line.replace(bracket, "")
        line = SPACES.sub(" ", line)
        line = re.sub(r"\s+([,.])", r"\1", line)
        line = re.sub(r"(?:,\s*){2,}", ", ", line).strip(" ,")
        if not line:
            continue
        if not SENTENCE_END.search(line):
            line += "."
        lines.append(line)
    return " ".join(lines)


def speakable_title(title: str, readings: dict[str, str]) -> str:
    """Say a heading the way it is meant to be heard, without its 한자 병기."""
    spoken = HANJA_PARENTHESIS.sub("", title)
    spoken = MARKUP.sub("", spoken)
    spoken = speak_hanja(spoken, readings)
    spoken = spoken.replace("—", ",").replace("·", ",")
    spoken = SPACES.sub(" ", spoken)
    spoken = re.sub(r"\s+,", ",", spoken).strip(" ,.")
    return spoken + "." if spoken else ""


# --------------------------------------------------------------------------
# 트랙 구성
# --------------------------------------------------------------------------


@dataclass
class Track:
    number: int
    title: str
    units: list[Unit] = field(default_factory=list)

    def chars(self, with_commentary: bool) -> int:
        return sum(unit.chars(with_commentary) for unit in self.units)


def chapter_groups(units: list[Unit]) -> list[tuple[str, list[Unit]]]:
    groups: list[tuple[str, list[Unit]]] = []
    for unit in units:
        if groups and groups[-1][0] == unit.chapter:
            groups[-1][1].append(unit)
        else:
            groups.append((unit.chapter, [unit]))
    return groups


def split_units(units: list[Unit], budget: int) -> list[list[Unit]]:
    """Cut one long 품 into parts at 단락 boundaries, near the char budget."""
    total = sum(unit.chars(True) for unit in units)
    parts = max(1, round(total / budget)) if budget else 1
    parts = min(parts, len(units))
    target = total / parts
    chunks: list[list[Unit]] = [[]]
    running = 0
    for index, unit in enumerate(units):
        remaining = len(units) - index
        if (
            chunks[-1]
            and len(chunks) < parts
            and running >= target * len(chunks)
            and remaining >= parts - len(chunks)
        ):
            chunks.append([])
        chunks[-1].append(unit)
        running += unit.chars(True)
    return [chunk for chunk in chunks if chunk]


def build_tracks(units: list[Unit], minutes: float) -> list[Track]:
    """Group 단락 into tracks of about ``minutes``, never cutting one in half.

    Track boundaries come from the 풀이+해설 length so both albums keep the same
    numbering; the 풀이만 tracks simply run shorter.
    """
    budget = int(minutes * CHARS_PER_MINUTE)
    tracks: list[Track] = []
    pending: list[tuple[str, list[Unit]]] = []

    def flush() -> None:
        if not pending:
            return
        title = pending[0][0]
        if len(pending) > 1:
            title = f"{title} 외 {len(pending) - 1}편"
        merged = [unit for _, group in pending for unit in group]
        tracks.append(Track(len(tracks) + 1, title, merged))
        pending.clear()

    for chapter, group in chapter_groups(units):
        size = sum(unit.chars(True) for unit in group)
        if size > budget:
            flush()
            parts = split_units(group, budget)
            for index, part in enumerate(parts, 1):
                title = chapter if len(parts) == 1 else f"{chapter} ({index}/{len(parts)})"
                tracks.append(Track(len(tracks) + 1, title, part))
            continue
        carried = sum(unit.chars(True) for _, group_ in pending for unit in group_)
        if pending and carried + size > budget:
            flush()
        pending.append((chapter, group))
    flush()
    return tracks


def track_script(
    book: Book,
    track: Track,
    with_commentary: bool,
    readings: dict[str, str],
    notice: bool,
) -> list[tuple[str, str]]:
    """The spoken segments of one track: 큰목차, 소목차, 풀이, 해설 순서.

    소목차는 바뀔 때만 다시 부른다.  같은 품이 이어지면 풀이와 해설로 곧장
    넘어간다.
    """
    segments: list[tuple[str, str]] = []
    if notice:
        segments.append((VOICE_TITLE, AI_NOTICE))
    heading = speakable_title(book.running_title, readings)
    announced: str | None = None
    for unit in track.units:
        if unit.chapter != announced:
            chapter = speakable_title(unit.chapter, readings)
            spoken = f"{heading} {chapter}".strip()
            if spoken:
                segments.append((VOICE_TITLE, spoken))
            heading = ""
            announced = unit.chapter
        reading = to_speech(unit.reading, readings)
        if reading:
            segments.append((VOICE_READING, reading))
        if with_commentary:
            commentary = to_speech(unit.commentary, readings)
            if commentary:
                segments.append((VOICE_COMMENTARY, commentary))
    return segments


# --------------------------------------------------------------------------
# MP3 쓰기
# --------------------------------------------------------------------------


def silence(milliseconds: int) -> bytes:
    return SILENT_FRAME * max(0, round(milliseconds / FRAME_MS))


def duration_ms(audio: bytes) -> int:
    return len(audio) // FRAME_BYTES * FRAME_MS


def text_frame(name: str, value: str) -> bytes:
    body = b"\x01" + value.encode("utf-16")
    return name.encode("ascii") + len(body).to_bytes(4, "big") + b"\x00\x00" + body


def comment_frame(value: str) -> bytes:
    body = b"\x01kor" + "﻿".encode("utf-16-le") + b"\x00\x00" + value.encode("utf-16")
    return b"COMM" + len(body).to_bytes(4, "big") + b"\x00\x00" + body


def id3_tag(fields: dict[str, str], comment: str) -> bytes:
    """An ID3v2.3 tag, UTF-16 encoded so Korean titles survive every player."""
    frames = b"".join(text_frame(name, value) for name, value in fields.items() if value)
    frames += comment_frame(comment)
    size = len(frames)
    syncsafe = bytes(((size >> shift) & 0x7F) for shift in (21, 14, 7, 0))
    return b"ID3\x03\x00\x00" + syncsafe + frames


def tagged_mp3(audio: bytes, album: str, title: str, number: int, total: int) -> bytes:
    fields = {
        "TIT2": title,
        "TALB": album,
        "TPE1": "AI 낭독",
        "TPE2": "불교 경전 낭독",
        "TRCK": f"{number}/{total}",
        "TCON": "Speech",
        "TLEN": str(duration_ms(audio)),
    }
    return id3_tag(fields, AI_NOTICE) + audio


# --------------------------------------------------------------------------
# 음성 합성
# --------------------------------------------------------------------------


async def read_once(text: str, voice: str, rate: str) -> bytes:
    import edge_tts

    chunks: list[bytes] = []
    async for chunk in edge_tts.Communicate(text, voice, rate=rate).stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    audio = b"".join(chunks)
    if not audio:
        raise RuntimeError("돌아온 음성이 비어 있습니다")
    return audio


async def synthesize(text: str, voice: str, rate: str, retries: int = 6) -> bytes:
    """Read one segment aloud, retrying refusals and stalls alike.

    The service sometimes accepts a connection and then simply stops sending,
    which no amount of error handling catches — the await never returns.  A
    deadline generous enough for a slow answer but far short of a hung socket
    turns that silence into one more retry.
    """
    limit = max(90.0, len(text) * 0.08)
    for attempt in range(retries):
        try:
            return await asyncio.wait_for(read_once(text, voice, rate), limit)
        except Exception as error:  # noqa: BLE001 - 서비스 오류는 모두 재시도한다
            if attempt == retries - 1:
                raise RuntimeError(f"음성 합성에 실패했습니다: {error!r}") from error
            await asyncio.sleep(min(30, 2**attempt))
    raise RuntimeError("음성 합성에 실패했습니다")


async def render_track(
    segments: list[tuple[str, str]],
    rate: str,
    gate: asyncio.Semaphore,
) -> bytes:
    """Synthesize a track's segments in parallel and join them with pauses."""

    async def one(voice: str, text: str) -> bytes:
        async with gate:
            return await synthesize(text, voice, rate)

    pieces = await asyncio.gather(*(one(voice, text) for voice, text in segments))
    joined: list[bytes] = []
    previous: str | None = None
    for (voice, _), audio in zip(segments, pieces):
        if joined:
            title_edge = voice == VOICE_TITLE or previous == VOICE_TITLE
            joined.append(silence(700 if title_edge else 400))
        joined.append(audio)
        previous = voice
    return b"".join(joined)


# --------------------------------------------------------------------------
# 앨범 만들기
# --------------------------------------------------------------------------

UNSAFE_NAME = re.compile(r'[\\/:*?"<>|]+')


def safe(name: str) -> str:
    """A file name Windows accepts, keeping ``(1/4)` readable as ``(1-4)``."""
    return UNSAFE_NAME.sub("", name.replace("/", "-")).strip().rstrip(".")


def album_name(book: Book, flavor: str) -> str:
    return f"{book.title} ({FLAVORS[flavor][0]})"


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def write_playlist(directory: Path, album: str, entries: list[dict]) -> None:
    lines = ["#EXTM3U", f"#PLAYLIST:{album}"]
    for entry in entries:
        lines.append(f"#EXTINF:{entry.get('seconds', 0)},{entry.get('title', '')}")
        lines.append(entry["file"])
    (directory / "재생목록.m3u8").write_text("\n".join(lines) + "\n", encoding="utf-8")


class Deadline(Exception):
    """Raised when ``--until`` arrives, to stop between tracks rather than mid-track."""


async def build_album(
    book: Book,
    flavor: str,
    tracks: list[Track],
    readings: dict[str, str],
    args: argparse.Namespace,
) -> None:
    """Render one album, skipping tracks whose script has not changed."""
    with_commentary = FLAVORS[flavor][1]
    album = album_name(book, flavor)
    directory = AUDIO_DIR / safe(book.output.stem) / safe(FLAVORS[flavor][0])
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "트랙목록.json"
    manifest: dict[str, dict] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    gate = asyncio.Semaphore(args.concurrency)
    entries: list[dict] = []
    for track in tracks:
        segments = track_script(
            book, track, with_commentary, readings, notice=track.number == 1
        )
        if not segments:
            continue
        script = "\n".join(f"{voice}\t{text}" for voice, text in segments)
        name = f"{track.number:03d}. {safe(track.title)}.mp3"
        path = directory / name
        known = manifest.get(name, {})
        if path.exists() and known.get("script") == hash_text(script) and not args.force:
            entries.append({**known, "file": name})
            continue
        if args.until and time.time() >= args.until:
            write_playlist(directory, album, entries)
            raise Deadline(f"{time.strftime('%H:%M')} — 정한 시각이 되어 멈춥니다")
        started = time.monotonic()
        audio = await render_track(segments, args.rate, gate)
        path.write_bytes(tagged_mp3(audio, album, track.title, track.number, len(tracks)))
        entry = {
            "file": name,
            "title": track.title,
            "seconds": round(duration_ms(audio) / 1000),
            "chars": len(script),
            "script": hash_text(script),
        }
        entries.append(entry)
        manifest[name] = entry
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(
            f"  {name}  {entry['seconds'] / 60:5.1f}분"
            f"  ({time.monotonic() - started:.0f}초 걸림)",
            flush=True,
        )
    if not args.sample:
        # 트랙을 다시 나누면 옛 이름의 파일이 남아 재생 목록을 어지럽힌다.
        planned = {entry["file"] for entry in entries}
        for stale in sorted(set(directory.glob("*.mp3")) - {directory / f for f in planned}):
            stale.unlink()
            manifest.pop(stale.name, None)
            print(f"  낡은 트랙을 지웠습니다: {stale.name}", flush=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    write_playlist(directory, album, entries)


# --------------------------------------------------------------------------
# 집 안에서 듣기
# --------------------------------------------------------------------------

PLAYER_HTML = """<!doctype html>
<html lang="ko">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>불교 경전 낭독</title>
<style>
 :root { color-scheme: light dark; --line: #8883; }
 body { margin: 0; font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", sans-serif; }
 header { position: sticky; top: 0; padding: 12px 16px 10px; backdrop-filter: blur(12px);
          background: color-mix(in srgb, Canvas 82%, transparent); border-bottom: 1px solid var(--line); }
 h1 { margin: 0 0 8px; font-size: 17px; font-weight: 600; }
 select, button { font: inherit; padding: 7px 10px; border-radius: 9px;
                  border: 1px solid var(--line); background: Canvas; color: CanvasText; }
 .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
 audio { width: 100%; margin-top: 10px; }
 ol { list-style: none; margin: 0; padding: 0 0 40vh; }
 li { padding: 12px 16px; border-bottom: 1px solid var(--line); display: flex; gap: 10px; }
 li[aria-current="true"] { background: color-mix(in srgb, Highlight 18%, transparent); font-weight: 600; }
 .no { opacity: .5; font-variant-numeric: tabular-nums; }
 .len { margin-left: auto; opacity: .5; font-variant-numeric: tabular-nums; }
 button[aria-pressed="true"] { background: CanvasText; color: Canvas; }
 .save { margin-top: 8px; font-size: 14px; opacity: .75; }
 .save a { color: inherit; }
</style>
<header>
 <h1 id="now">불교 경전 낭독</h1>
 <div class="row">
  <select id="book"></select>
  <button id="commentary" aria-pressed="true">해설 포함</button>
  <button id="speed">1.0배</button>
 </div>
 <audio id="audio" controls preload="metadata"></audio>
 <div class="save">내려받기 · <a id="one" download>이 트랙</a> · <a id="whole">이 앨범 전체(zip)</a></div>
</header>
<ol id="list"></ol>
<script>
const DATA = __DATA__;
const $ = (id) => document.getElementById(id);
const state = Object.assign({book: Object.keys(DATA)[0], commentary: true, index: 0, speed: 1},
  JSON.parse(localStorage.getItem("낭독") || "{}"));
const flavor = () => state.commentary && DATA[state.book]["풀이+해설"] ? "풀이+해설" : "풀이만";
const tracks = () => DATA[state.book][flavor()] || [];
const save = () => localStorage.setItem("낭독", JSON.stringify(
  {book: state.book, commentary: state.commentary, index: state.index, speed: state.speed, time: $("audio").currentTime}));

for (const name of Object.keys(DATA)) $("book").add(new Option(name, name));
$("book").value = state.book;

function paint() {
  const list = tracks();
  $("list").innerHTML = list.map((t, i) => `<li aria-current="${i === state.index}" data-i="${i}">` +
    `<span class="no">${String(i + 1).padStart(2, "0")}</span><span>${t.title}</span>` +
    `<span class="len">${Math.round(t.seconds / 60)}분</span></li>`).join("");
  $("now").textContent = (list[state.index]?.title || "") + " — " + state.book;
  $("commentary").setAttribute("aria-pressed", state.commentary);
  $("commentary").textContent = state.commentary ? "해설 포함" : "풀이만";
  $("speed").textContent = state.speed.toFixed(1) + "배";
  document.querySelector('li[aria-current="true"]')?.scrollIntoView({block: "nearest"});
}

function load(index, play, at = 0) {
  const list = tracks();
  state.index = Math.max(0, Math.min(index, list.length - 1));
  const track = list[state.index];
  if (!track) return;
  const source = [state.book, flavor(), track.file].map(encodeURIComponent).join("/");
  $("audio").src = source;
  $("one").href = source;
  $("whole").href = "zip/" + [state.book, flavor()].map(encodeURIComponent).join("/") + ".zip";
  $("audio").playbackRate = state.speed;
  if (at) $("audio").currentTime = at;
  if (play) $("audio").play();
  if ("mediaSession" in navigator)
    navigator.mediaSession.metadata = new MediaMetadata({title: track.title, album: state.book, artist: "AI 낭독"});
  paint(); save();
}

$("book").onchange = () => { state.book = $("book").value; load(0, true); };
$("commentary").onclick = () => { state.commentary = !state.commentary; load(state.index, !$("audio").paused); };
$("speed").onclick = () => {
  const steps = [1, 1.2, 1.5, 1.8, 0.8];
  state.speed = steps[(steps.indexOf(state.speed) + 1) % steps.length];
  $("audio").playbackRate = state.speed; paint(); save();
};
$("list").onclick = (event) => {
  const item = event.target.closest("li");
  if (item) load(Number(item.dataset.i), true);
};
$("audio").onended = () => load(state.index + 1, true);
$("audio").ontimeupdate = () => { if (!($("audio").currentTime % 5 | 0)) save(); };
// 파일로 직접 연 경우엔 서버가 만들어 주는 내려받기 줄을 감춘다.
if (location.protocol === "file:") document.querySelector(".save").hidden = true;
load(state.index, false, state.time || 0);
</script>
</html>
"""


def album_index() -> dict[str, dict[str, list[dict]]]:
    """Read the manifests already on disk, newest album order first."""
    albums: dict[str, dict[str, list[dict]]] = {}
    for manifest_path in sorted(AUDIO_DIR.glob("*/*/트랙목록.json")):
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))
        tracks = sorted(entries.values(), key=lambda entry: entry["file"])
        albums.setdefault(manifest_path.parts[-3], {})[manifest_path.parts[-2]] = tracks
    return albums


def write_player() -> dict[str, dict[str, list[dict]]]:
    """Write the listening page next to the albums it plays."""
    albums = album_index()
    if not albums:
        raise SystemExit(f"들려줄 음성이 없습니다: {AUDIO_DIR}")
    page = PLAYER_HTML.replace("__DATA__", json.dumps(albums, ensure_ascii=False))
    (AUDIO_DIR / "index.html").write_text(page, encoding="utf-8")
    return albums


GUIDE = """{title} 낭독

{subtitle}

■ 듣는 법
  ㆍ아이폰·아이패드·안드로이드 — MP3 파일을 그대로 옮겨 재생기에 넣으세요.
    VLC(무료)에 폴더째 넣으면 이어듣기, 배속, 잠금화면 재생이 됩니다.
  ㆍ컴퓨터 — 이 폴더의 「듣기.html」을 브라우저로 열면 목차와 재생기가 나옵니다.

■ 두 벌이 들어 있습니다
  ㆍ풀이+해설 — 경전 이름과 품 이름을 알린 뒤 단락마다 우리말 풀이와 해설을 잇습니다.
  ㆍ풀이만   — 같은 트랙 번호로 해설만 뺀 것입니다.
  트랙 번호와 제목이 같으므로, 듣던 번호 그대로 다른 쪽을 열면 같은 대목이 이어집니다.
  「듣기.html」에서는 '해설 포함' 단추로 그 자리에서 바꿀 수 있습니다.

■ 목소리
  안내는 현수, 우리말 풀이는 선히, 해설은 인준이 읽습니다. 목소리가 바뀌는 것으로
  층이 구분되므로 따로 알리는 말을 넣지 않았습니다.

■ 밝혀 둘 것
  {notice}
  기계가 읽은 음성이며, 사람이 녹음한 것이 아닙니다.
"""


def package(books: list[Book]) -> list[Path]:
    """Pack finished albums into one zip per scripture, ready to hand over.

    받는 사람이 아무것도 설치하지 않고 열 수 있도록 재생기와 안내문을 함께
    넣는다.  「듣기.html」은 웹서버 없이 파일을 직접 열어도 도는 페이지다.
    """
    import zipfile

    outbox = AUDIO_DIR / "배포"
    outbox.mkdir(parents=True, exist_ok=True)
    made: list[Path] = []
    library = album_index()
    for book in books:
        name = safe(book.output.stem)
        albums = library.get(name)
        if not albums:
            print(f"  건너뜀 — 아직 만들지 않았습니다: {book.title}")
            continue
        page = PLAYER_HTML.replace("__DATA__", json.dumps({name: albums}, ensure_ascii=False))
        guide = GUIDE.format(
            title=book.title, subtitle=book.subtitle, notice=AI_NOTICE
        )
        archive_path = outbox / f"{name}_낭독.zip"
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_STORED) as archive:
            archive.writestr("듣기.html", page)
            archive.writestr("읽어 주세요.txt", guide)
            for flavor, tracks in albums.items():
                for track in tracks:
                    source = AUDIO_DIR / name / flavor / track["file"]
                    archive.write(source, f"{name}/{flavor}/{track['file']}")
                playlist = AUDIO_DIR / name / flavor / "재생목록.m3u8"
                if playlist.exists():
                    archive.write(playlist, f"{name}/{flavor}/재생목록.m3u8")
        hours = sum(t["seconds"] for f in albums.values() for t in f) / 3600
        print(
            f"  {archive_path.name}  {archive_path.stat().st_size / 1e6:,.0f}MB · {hours:.1f}시간"
        )
        made.append(archive_path)
    return made


def album_zip_handler(base: type):
    """Add a ``/zip/<경전>/<앨범>.zip`` route that packs an album on request.

    The MP3s are already compressed, so the archive is stored, not deflated,
    and streams straight to the phone — no temporary copy on disk.  That is
    what turns "듣고 있다"를 "가지고 다닌다"로 바꾸는 한 번의 눌림이다.
    """
    import zipfile
    from urllib.parse import quote, unquote

    class Library(base):  # type: ignore[misc, valid-type]
        def do_GET(self) -> None:  # noqa: N802 - http.server의 이름 규칙
            path = unquote(self.path.split("?")[0])
            if not (path.startswith("/zip/") and path.endswith(".zip")):
                super().do_GET()
                return
            folder = (AUDIO_DIR / path[len("/zip/") : -len(".zip")]).resolve()
            if not folder.is_dir() or AUDIO_DIR.resolve() not in folder.parents:
                # 상태 줄은 latin-1만 담을 수 있어 한국어는 본문 쪽에 둔다.
                self.send_error(404, "Not Found", "앨범을 찾을 수 없습니다")
                return
            name = f"{folder.parent.name}_{folder.name}.zip"
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header(
                "Content-Disposition",
                f"attachment; filename=\"album.zip\"; filename*=UTF-8''{quote(name)}",
            )
            self.end_headers()
            with zipfile.ZipFile(self.wfile, "w", zipfile.ZIP_STORED) as archive:
                for item in sorted(folder.iterdir()):
                    if item.suffix in {".mp3", ".m3u8"}:
                        archive.write(item, item.name)

    return Library


def serve(port: int) -> None:
    """Play the finished albums from a phone on the same network.

    iOS keeps Safari's audio going with the screen off and shows the track on
    the lock screen, so this is the shortest path from a finished build to a
    pair of headphones — no cable, no app, no copying gigabytes.  트랙과 앨범을
    파일로 내려받는 길도 같은 페이지에 함께 둔다.
    """
    import socket
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    albums = write_player()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect(("8.8.8.8", 53))
        address = probe.getsockname()[0]
    handler = partial(album_zip_handler(SimpleHTTPRequestHandler), directory=str(AUDIO_DIR))
    server = ThreadingHTTPServer(("0.0.0.0", port), handler)
    print(f"아이폰 사파리에서 여세요:  http://{address}:{port}/")
    print(f"경전 {len(albums)}종 · 트랙과 앨범을 파일로 내려받을 수 있습니다 · 멈추려면 Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 닫았습니다.")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def selected_books(names: list[str]) -> list[Book]:
    if not names or "전체" in names or "all" in names:
        return list(BOOKS)
    chosen: list[Book] = []
    for name in names:
        found = [book for book in BOOKS if name in (book.key, book.selector)]
        if not found:
            keys = ", ".join(dict.fromkeys(book.selector for book in BOOKS))
            raise SystemExit(f"알 수 없는 경전입니다: {name} (가능한 이름: {keys})")
        chosen.extend(book for book in found if book not in chosen)
    return chosen


def plan(book: Book, minutes: float) -> list[Track]:
    units = parse_units(book_markdown(book), book.title)
    if not units:
        raise SystemExit(f"우리말 풀이·해설을 찾지 못했습니다: {book.key}")
    return build_tracks(units, minutes)


def parse_until(text: str) -> float:
    """Read ``17:10`` as a moment today — tomorrow if that hour has passed."""
    try:
        hour, minute = (int(part) for part in text.split(":"))
    except ValueError as error:
        raise SystemExit(f"시각은 HH:MM으로 적어 주세요: {text}") from error
    now = time.localtime()
    stamp = time.mktime(
        (now.tm_year, now.tm_mon, now.tm_mday, hour, minute, 0, 0, 0, -1)
    )
    return stamp + 24 * 3600 if stamp <= time.time() else stamp


def status(books: list[Book], minutes: float) -> None:
    """Show how much of each scripture is already on disk."""
    print(f"{'경전':10s} {'풀이+해설':>13s} {'풀이만':>13s}   {'만든 분량':>9s}")
    done = todo = 0.0
    for book in books:
        tracks = plan(book, minutes)
        columns = []
        for label, commentary in FLAVORS.values():
            folder = AUDIO_DIR / safe(book.output.stem) / label
            made = len(list(folder.glob("*.mp3"))) if folder.is_dir() else 0
            hours = (
                sum(track.chars(commentary) for track in tracks)
                / SPOKEN_CHARS_PER_MINUTE
                / 60
            )
            share = made / len(tracks) if tracks else 0.0
            done += hours * share
            todo += hours * (1 - share)
            columns.append(f"{made:4d}/{len(tracks):<4d}{share * 100:3.0f}%")
        print(f"{book.key:10s} {columns[0]:>13s} {columns[1]:>13s}")
    print(f"\n끝난 분량 {done:,.0f}시간 · 남은 분량 {todo:,.0f}시간")


def rate_factor(rate: str) -> float:
    match = re.fullmatch(r"([+-]\d+)%", rate)
    return 1 + int(match.group(1)) / 100 if match else 1.0


def report(tracks: list[Track], factor: float) -> None:
    for label, with_commentary in FLAVORS.values():
        chars = sum(track.chars(with_commentary) for track in tracks)
        minutes = chars / (SPOKEN_CHARS_PER_MINUTE * factor)
        print(
            f"  {label:6s} 트랙 {len(tracks):4d}개 · {chars:>9,d}자 · "
            f"{minutes / 60:6.1f}시간 · 약 {minutes * BYTES_PER_MINUTE / 1e6:6.0f}MB"
        )


async def run(args: argparse.Namespace) -> None:
    readings = hanja_readings()
    factor = rate_factor(args.rate)
    for book in selected_books(args.book):
        tracks = plan(book, args.minutes)
        if args.sample:
            tracks = tracks[: args.sample]
        print(f"[{book.key}] {book.title} — {book.running_title}")
        report(tracks, factor)
        if args.dry_run:
            for track in tracks[: args.preview]:
                print(f"    {track.number:3d}. {track.title}")
            for voice, text in track_script(book, tracks[0], True, readings, True)[: args.script]:
                tag = {VOICE_TITLE: "안내", VOICE_READING: "풀이"}.get(voice, "해설")
                print(f"    [{tag}] {text[:400]}")
            continue
        for flavor in args.flavor:
            print(f"  ▸ {album_name(book, flavor)}")
            try:
                await build_album(book, flavor, tracks, readings, args)
            except Deadline as stop:
                print(f"\n{stop}  다시 실행하면 이 자리에서 이어 갑니다.")
                return
    if not args.dry_run:
        print(f"\n완성된 음성은 {AUDIO_DIR} 아래에 있습니다.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("book", nargs="*", help="경전 이름 (생략하면 전체)")
    parser.add_argument("--flavor", nargs="+", choices=list(FLAVORS), default=list(FLAVORS))
    parser.add_argument("--minutes", type=float, default=15.0, help="트랙 목표 길이 (기본 15분)")
    parser.add_argument("--rate", default="+0%", help="낭독 속도, 예: +20%%")
    parser.add_argument("--concurrency", type=int, default=6, help="동시에 합성할 토막 수")
    parser.add_argument("--sample", type=int, default=0, help="앞의 N개 트랙만 만든다")
    parser.add_argument("--force", action="store_true", help="이미 만든 트랙도 다시 만든다")
    parser.add_argument("--dry-run", action="store_true", help="만들지 않고 분량만 계산한다")
    parser.add_argument("--preview", type=int, default=0, help="트랙 제목을 N개까지 보여 준다")
    parser.add_argument("--script", type=int, default=0, help="첫 트랙 대본을 N토막까지 보여 준다")
    parser.add_argument("--list", action="store_true", help="만들 수 있는 경전을 보여 준다")
    parser.add_argument(
        "--serve",
        nargs="?",
        type=int,
        const=8000,
        help="만들어 둔 음성을 집 안 다른 기기에서 듣도록 웹으로 연다",
    )
    parser.add_argument(
        "--package",
        action="store_true",
        help="만들어 둔 음성을 남에게 건넬 zip으로 묶는다 (재생기·안내문 포함)",
    )
    parser.add_argument("--status", action="store_true", help="어디까지 만들었는지 보여 준다")
    parser.add_argument("--until", help="정한 시각에 멈춘다, 예: 17:10 (지난 시각이면 내일)")
    args = parser.parse_args()
    args.until = parse_until(args.until) if args.until else None

    if args.status:
        status(selected_books(args.book), args.minutes)
        return
    if args.serve:
        serve(args.serve)
        return
    if args.package:
        made = package(selected_books(args.book))
        if made:
            print(f"\n건넬 파일은 {made[0].parent} 안에 있습니다.")
        return
    if args.list:
        for book in BOOKS:
            print(f"{book.key:10s} {book.title} — {book.subtitle}")
        return
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
