#!/usr/bin/env python3
"""Generate complete CBETA base-text editions with Korean readings under each Hanja.

The generated Markdown uses three-row tables.  The first row contains the source
characters, and the third row contains the corresponding Korean reading.  The
source text is split by juan (卷) so even the 80-volume Avatamsaka remains usable.

Only the CBETA base reading is rendered.  Critical-apparatus notes, alternate
readings, page/line markers, and editorial pronunciation notes are intentionally
excluded; they remain available through the linked CBETA XML source.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import shutil
import sys
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


CBETA_RAW = "https://raw.githubusercontent.com/cbeta-git/xml-p5a/master/"
HANJA_CSV_URL = (
    "https://raw.githubusercontent.com/masoris/hanja_hangul/main/src/hanja.csv"
)
HANJA_LICENSE_URL = "https://github.com/masoris/hanja_hangul/blob/main/LICENSE"
DUEUM_CSV_URL = (
    "https://raw.githubusercontent.com/masoris/hanja_hangul/main/src/dueum.csv"
)
SEGMENT_DICT_URL = (
    "https://raw.githubusercontent.com/ldkrsi/jieba-zh_TW/master/jieba/dict.txt"
)
SEGMENT_LICENSE_URL = "https://github.com/ldkrsi/jieba-zh_TW/blob/master/LICENSE"
GAIJI_JSON_URL = (
    "https://raw.githubusercontent.com/cbeta-org/cbeta_gaiji/master/cbeta_gaiji.json"
)


@dataclass(frozen=True)
class Sutra:
    slug: str
    title_ko: str
    title_zh: str
    taisho: str
    translator: str
    xml_path: str
    expected_juan: int


SUTRAS = (
    Sutra(
        "금강경",
        "금강반야바라밀경",
        "金剛般若波羅蜜經",
        "T0235",
        "요진 구마라집",
        "T/T08/T08n0235.xml",
        1,
    ),
    Sutra(
        "반야심경",
        "반야바라밀다심경",
        "般若波羅蜜多心經",
        "T0251",
        "당 현장",
        "T/T08/T08n0251.xml",
        1,
    ),
    Sutra(
        "유마경",
        "유마힐소설경",
        "維摩詰所說經",
        "T0475",
        "요진 구마라집",
        "T/T14/T14n0475.xml",
        3,
    ),
    Sutra(
        "무량수경",
        "불설무량수경",
        "佛說無量壽經",
        "T0360",
        "조위 강승개",
        "T/T12/T12n0360.xml",
        2,
    ),
    Sutra(
        "관무량수경",
        "불설관무량수불경",
        "佛說觀無量壽佛經",
        "T0365",
        "송 강량야사",
        "T/T12/T12n0365.xml",
        1,
    ),
    Sutra(
        "아미타경",
        "불설아미타경",
        "佛說阿彌陀經",
        "T0366",
        "요진 구마라집",
        "T/T12/T12n0366.xml",
        1,
    ),
    Sutra(
        "법화경",
        "묘법연화경",
        "妙法蓮華經",
        "T0262",
        "요진 구마라집",
        "T/T09/T09n0262.xml",
        7,
    ),
    Sutra(
        "화엄경",
        "대방광불화엄경",
        "大方廣佛華嚴經",
        "T0279",
        "당 실차난타",
        "T/T10/T10n0279.xml",
        80,
    ),
)


# Conventional Korean Buddhist readings that cannot be derived reliably from a
# character-by-character general Hanja dictionary.  Each Hangul string must have
# exactly one syllable for each source character.
PHRASE_READINGS = {
    "阿耨多羅三藐三菩提": "아뇩다라삼먁삼보리",
    "祇樹給孤獨園": "기수급고독원",
    "耆闍崛山": "기사굴산",
    "摩訶目犍連": "마하목건련",
    "摩訶迦葉": "마하가섭",
    "摩訶般若": "마하반야",
    "波羅僧揭帝": "바라승아제",
    "般羅僧揭帝": "바라승아제",
    "波羅揭帝": "바라아제",
    "般羅揭帝": "바라아제",
    "三藐三菩提": "삼먁삼보리",
    "摩訶菩提薩埵": "마하보리살타",
    "菩提薩埵": "보리살타",
    "般若波羅蜜多": "반야바라밀다",
    "般若波羅蜜": "반야바라밀",
    "波羅蜜多": "바라밀다",
    "波羅蜜": "바라밀",
    "須菩提": "수보리",
    "摩訶薩": "마하살",
    "菩提": "보리",
    "般若": "반야",
    "涅槃": "열반",
    "南無": "나무",
    "菩薩": "보살",
    "比丘尼": "비구니",
    "比丘": "비구",
    "優婆塞": "우바새",
    "優婆夷": "우바이",
    "阿羅漢": "아라한",
    "辟支佛": "벽지불",
    "舍利弗": "사리불",
    "目犍連": "목건련",
    "迦葉": "가섭",
    "阿難陀": "아난타",
    "阿難": "아난",
    "羅睺羅": "라후라",
    "耶輸陀羅": "야수다라",
    "釋迦牟尼": "석가모니",
    "鳩摩羅什": "구마라집",
    "舍衛國": "사위국",
    "王舍城": "왕사성",
    "文殊師利": "문수사리",
    "觀世音": "관세음",
    "阿彌陀": "아미타",
    "彌勒": "미륵",
    "阿修羅": "아수라",
    "乾闥婆": "건달바",
    "迦樓羅": "가루라",
    "緊那羅": "긴나라",
    "摩睺羅伽": "마후라가",
    "陀羅尼": "다라니",
    "三昧": "삼매",
    "娑婆": "사바",
    "莎婆訶": "사바하",
    "娑婆訶": "사바하",
    "揭帝": "아제",
    "一切": "일체",
    "願樂欲聞": "원요욕문",
    "阿僧祇": "아승기",
    "那由他": "나유타",
}


# Rare CBETA base glyphs not covered by the CC0 table.  Readings come from the
# CBETA apparatus or the character's fanqie/normalized variant.  These entries
# are deliberately explicit so an audit never silently guesses a missing sound.
EXTRA_READINGS = {
    "𢄋": "영",  # fanqie 於營; variant 榮
    "𮜒": "조",  # CBETA apparatus: 躁
    "𦾨": "얼",  # 妖𦾨; corresponding form 孽/蘖
    "𣩠": "사",  # CBETA apparatus: 賜/儩
    "𢤱": "농",  # fanqie/modern reading lǒng; word-initial Korean sound
    "𥯤": "위",  # phonetic 韋 in 竹𥯤
    "𪙁": "사",  # CBETA apparatus: 摣
    "𩑔": "고",  # 形𩑔瘦; Hanyu reading kū, 'withered/emaciated'
    "𧂐": "적",  # composition 艹/積; a pile of sandalwood
    "𡎰": "지",  # fanqie 直尼; dharani transcription
    "𨷲": "약",  # fanqie 以灼
}


BLOCK_TAGS = {
    "byline",
    "head",
    "jhead",
    "l",
    "lg",
    "p",
    "title",
    "trailer",
}
EXCLUDED_TAGS = {
    "anchor",
    "docNumber",
    "mulu",
    "note",
    "pb",
    "rdg",
    "yin",
}


def fetch(url: str, cache_dir: Path) -> bytes:
    """Download a source with a persistent cache and bounded retries."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    basename = url.rsplit("/", 1)[-1] or "source"
    cache_file = cache_dir / f"{sha256(url.encode('utf-8'))[:16]}-{basename}"
    if cache_file.is_file() and cache_file.stat().st_size:
        return cache_file.read_bytes()

    request = urllib.request.Request(url, headers={"User-Agent": "Buddist-sutra-builder/1"})
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                data = response.read()
            if not data:
                raise OSError(f"empty response from {url}")
            temporary = cache_file.with_suffix(cache_file.suffix + ".part")
            temporary.write_bytes(data)
            temporary.replace(cache_file)
            return data
        except (OSError, TimeoutError) as error:
            last_error = error
            if attempt < 3:
                time.sleep(2**attempt)
    raise RuntimeError(f"download failed after 4 attempts: {url}") from last_error


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def attr_by_local_name(elem: ET.Element, wanted: str) -> str | None:
    for key, value in elem.attrib.items():
        if local_name(key) == wanted:
            return value
    return None


def normalize_block(text: str) -> str:
    text = text.replace("\r", "").replace("\t", "")
    text = re.sub(r"[ \u00a0]+", "", text)
    text = re.sub(r"\n+", "", text)
    return text.strip()


def load_hanja_readings(data: bytes) -> dict[str, str]:
    decoded = data.decode("utf-8-sig")
    rows = csv.reader(io.StringIO(decoded))
    next(rows, None)
    readings: dict[str, str] = {}
    for row in rows:
        if len(row) >= 2 and len(row[0]) == 1 and row[1]:
            readings[row[0]] = row[1]
    return readings


def load_dueum(data: bytes) -> dict[str, str]:
    decoded = data.decode("utf-8-sig")
    rows = csv.reader(io.StringIO(decoded))
    next(rows, None)
    return {row[0]: row[1] for row in rows if len(row) >= 2 and row[0] and row[1]}


def load_segment_dictionary(data: bytes) -> tuple[dict[str, int], int, int]:
    frequencies: dict[str, int] = {}
    total = 0
    max_length = 1
    for line in data.decode("utf-8").splitlines():
        parts = line.rsplit(" ", 2)
        if len(parts) < 2:
            continue
        word = parts[0]
        try:
            frequency = int(parts[1])
        except ValueError:
            continue
        if word and all(is_hanja(char) for char in word):
            frequencies[word] = max(frequencies.get(word, 0), frequency)
            total += frequency
            max_length = max(max_length, len(word))
    for phrase in PHRASE_READINGS:
        frequencies[phrase] = max(frequencies.get(phrase, 0), 10_000_000)
        max_length = max(max_length, len(phrase))
    return frequencies, max(total, 1), min(max_length, 24)


def load_gaiji(data: bytes, readings: dict[str, str]) -> dict[str, str]:
    raw = json.loads(data.decode("utf-8"))
    result: dict[str, str] = {}
    for key, value in raw.items():
        candidates = [
            value.get("uni_char"),
            value.get("norm_uni_char"),
            value.get("norm_big5_char"),
        ]
        rendered = next((item for item in candidates if item), None)
        if rendered is None:
            rendered = value.get("composition") or f"[{key}]"
        if len(rendered) == 1 and rendered not in readings:
            for candidate in candidates[1:]:
                if candidate and len(candidate) == 1 and candidate in readings:
                    readings[rendered] = readings[candidate]
                    break
        result[key] = rendered
    return result


def is_hanja(char: str) -> bool:
    if len(char) != 1:
        return False
    name = unicodedata.name(char, "")
    return name.startswith("CJK UNIFIED IDEOGRAPH") or name.startswith(
        "CJK COMPATIBILITY IDEOGRAPH"
    )


def apply_initial_sound(
    reading: str, at_word_start: bool, dueum: dict[str, str]
) -> str:
    if not at_word_start or len(reading) != 1:
        return reading
    return dueum.get(reading, reading)


def segment_hanja(
    sequence: str,
    frequencies: dict[str, int],
    total: int,
    max_length: int,
) -> list[str]:
    """Segment a Traditional Chinese run using a frequency-weighted DAG."""
    length = len(sequence)
    log_total = math.log(total)
    route: list[tuple[float, int]] = [(-float("inf"), length)] * (length + 1)
    route[length] = (0.0, length)
    for start in range(length - 1, -1, -1):
        best = (-float("inf"), start + 1)
        limit = min(length, start + max_length)
        for end in range(start + 1, limit + 1):
            word = sequence[start:end]
            frequency = frequencies.get(word)
            if frequency is None and end != start + 1:
                continue
            score = math.log(frequency or 1) - log_total + route[end][0]
            if score > best[0]:
                best = (score, end)
        route[start] = best
    words: list[str] = []
    index = 0
    while index < length:
        end = route[index][1]
        words.append(sequence[index:end])
        index = end
    return words


def word_starts(
    text: str,
    frequencies: dict[str, int],
    total: int,
    max_length: int,
) -> set[int]:
    starts: set[int] = set()
    index = 0
    while index < len(text):
        if not is_hanja(text[index]):
            index += 1
            continue
        end = index + 1
        while end < len(text) and is_hanja(text[end]):
            end += 1
        offset = index
        for word in segment_hanja(text[index:end], frequencies, total, max_length):
            starts.add(offset)
            offset += len(word)
        index = end
    return starts


def phrase_readings(text: str) -> dict[int, str]:
    assigned: dict[int, str] = {}
    phrases = sorted(PHRASE_READINGS.items(), key=lambda item: len(item[0]), reverse=True)
    index = 0
    while index < len(text):
        matched = False
        for phrase, hangul in phrases:
            if text.startswith(phrase, index):
                syllables = list(hangul)
                if len(syllables) != len(phrase):
                    raise ValueError(f"Reading length mismatch: {phrase} -> {hangul}")
                for offset, syllable in enumerate(syllables):
                    assigned[index + offset] = syllable
                index += len(phrase)
                matched = True
                break
        if not matched:
            index += 1
    return assigned


def readings_for_text(
    text: str,
    readings: dict[str, str],
    dueum: dict[str, str],
    frequencies: dict[str, int],
    frequency_total: int,
    max_word_length: int,
    unknown: dict[str, int],
) -> list[str]:
    overrides = phrase_readings(text)
    starts = word_starts(text, frequencies, frequency_total, max_word_length)
    result: list[str] = []
    previous_reading = ""
    for index, char in enumerate(text):
        at_word_start = index in starts
        if index in overrides:
            reading = overrides[index]
        elif is_hanja(char):
            reading = readings.get(char, "")
            if reading:
                reading = apply_initial_sound(reading, at_word_start, dueum)
                if reading == "렬" and previous_reading:
                    jong = (ord(previous_reading) - 0xAC00) % 28
                    if jong in (0, 4):
                        reading = "열"
                elif reading == "률" and previous_reading:
                    jong = (ord(previous_reading) - 0xAC00) % 28
                    if jong in (0, 4):
                        reading = "율"
            else:
                unknown[char] = unknown.get(char, 0) + 1
                reading = "미상"
        else:
            reading = ""
        result.append(reading)
        if is_hanja(char):
            if reading and reading != "미상":
                previous_reading = reading
        else:
            previous_reading = ""
    return result


def resolve_gaiji(elem: ET.Element, gaiji: dict[str, str]) -> str:
    ref = elem.attrib.get("ref", "").lstrip("#")
    return gaiji.get(ref, f"[{ref or 'GAIJI'}]")


def extract_juan(xml_data: bytes, gaiji: dict[str, str]) -> dict[int, list[str]]:
    root = ET.fromstring(xml_data)
    body = next((elem for elem in root.iter() if local_name(elem.tag) == "body"), None)
    if body is None:
        raise ValueError("CBETA XML contains no body element")

    juan_blocks: dict[int, list[str]] = {}
    state = {"juan": None, "buffer": []}

    def flush() -> None:
        juan = state["juan"]
        if juan is None:
            state["buffer"].clear()
            return
        block = normalize_block("".join(state["buffer"]))
        state["buffer"].clear()
        if block:
            blocks = juan_blocks.setdefault(int(juan), [])
            blocks.append(block)

    def walk(elem: ET.Element) -> None:
        name = local_name(elem.tag)

        if name == "milestone" and elem.attrib.get("unit") == "juan":
            flush()
            state["juan"] = int(elem.attrib.get("n", "1"))
            juan_blocks.setdefault(int(state["juan"]), [])
            return

        if name in EXCLUDED_TAGS:
            return
        if name == "foreign" and (
            attr_by_local_name(elem, "place") == "foot"
            or attr_by_local_name(elem, "lang") not in (None, "zh", "zh-Hant")
        ):
            return
        if name == "t" and (
            attr_by_local_name(elem, "place") == "foot"
            or attr_by_local_name(elem, "lang") not in (None, "zh", "zh-Hant")
        ):
            return
        if name == "space":
            quantity = int(elem.attrib.get("quantity", "1") or "1")
            if quantity > 0:
                state["buffer"].append("　" * quantity)
            return
        if name == "g":
            state["buffer"].append(resolve_gaiji(elem, gaiji))
            return
        if name == "caesura":
            state["buffer"].append("　")
            return

        if elem.text:
            state["buffer"].append(elem.text)
        for child in elem:
            walk(child)
            if child.tail:
                state["buffer"].append(child.tail)
        if name in BLOCK_TAGS:
            flush()

    walk(body)
    flush()
    return juan_blocks


def markdown_cell(value: str) -> str:
    return value.replace("|", "&#124;").replace("\n", " ") or "&nbsp;"


def render_block(
    text: str,
    readings: dict[str, str],
    dueum: dict[str, str],
    frequencies: dict[str, int],
    frequency_total: int,
    max_word_length: int,
    unknown: dict[str, int],
    width: int,
) -> str:
    hangul = readings_for_text(
        text,
        readings,
        dueum,
        frequencies,
        frequency_total,
        max_word_length,
        unknown,
    )
    output: list[str] = []
    for start in range(0, len(text), width):
        chars = list(text[start : start + width])
        sounds = hangul[start : start + width]
        output.append("| " + " | ".join(markdown_cell(char) for char in chars) + " |")
        output.append("| " + " | ".join(":---:" for _ in chars) + " |")
        output.append("| " + " | ".join(markdown_cell(sound) for sound in sounds) + " |")
        output.append("")
    return "\n".join(output)


def render_juan(
    sutra: Sutra,
    juan: int,
    blocks: list[str],
    readings: dict[str, str],
    dueum: dict[str, str],
    frequencies: dict[str, int],
    frequency_total: int,
    max_word_length: int,
    unknown: dict[str, int],
    width: int,
) -> tuple[str, str, int]:
    plain = "\n".join(blocks)
    content = [
        f"# {sutra.title_ko} — 제{juan}권 전문 한자음",
        "",
        f"> 저본: CBETA 대정신수대장경 {sutra.taisho} 《{sutra.title_zh}》<br>",
        f"> 번역: {sutra.translator}<br>",
        f"> 원문 XML: [{sutra.xml_path}]({CBETA_RAW}{sutra.xml_path})",
        "",
        "각 표의 첫째 줄은 원문, 둘째 줄은 정렬선, 셋째 줄은 한글 독음이다. "
        "문장부호 아래의 빈칸은 정상이다.",
        "",
        "---",
        "",
    ]
    for block in blocks:
        content.append(
            render_block(
                block,
                readings,
                dueum,
                frequencies,
                frequency_total,
                max_word_length,
                unknown,
                width,
            )
        )
    return "\n".join(content).rstrip() + "\n", plain, sum(
        1 for char in plain if is_hanja(char)
    )


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_index(
    output_root: Path, manifest: list[dict[str, object]], unknown: dict[str, int]
) -> None:
    lines = [
        "# 경전 전문 한자음 대조본",
        "",
        "CBETA 대정신수대장경의 기본 본문 전체를 권별로 나누고, 각 한자 바로 "
        "아래에 한국 한자음을 배치한 대조본이다.",
        "",
        "## 읽는 방법",
        "",
        "각 표의 첫째 줄은 원문이고 셋째 줄은 같은 열의 한자를 읽는 한글 음이다. "
        "문장부호에는 독음이 없으므로 아래 칸이 비어 있다.",
        "",
        "## 수록 범위",
        "",
        "| 경전 | 대장경 번호 | 권수 | 한자 수 | 바로가기 |",
        "|---|---:|---:|---:|---|",
    ]
    for item in manifest:
        lines.append(
            f"| {item['title_ko']} | {item['taisho']} | {item['juan_count']} | "
            f"{item['hanja_count']:,} | [{item['slug']}](./{item['slug']}/README.md) |"
        )
    lines.extend(
        [
            "",
            "## 본문 범위 원칙",
            "",
            "- 경전 본문, 권 제목, 번역자 표시, 품 제목, 게송, 다라니를 포함한다.",
            "- CBETA 기본 본문에서 채택한 글자(교감 장치의 `lem`)를 사용한다.",
            "- 교감 각주, 다른 판본의 이문, 대정장 페이지·행 번호, 편집자 발음 주는 "
            "본문이 아니므로 대조표에서 제외한다.",
            "- 희귀 글자는 CBETA 외자 데이터베이스의 유니코드 글자 또는 통용자로 "
            "복원한다.",
            "- 한자음은 CC0 한자음 데이터에 불교 관용 독음 보정표를 적용했다. "
            "다라니·음역어·고유명사는 전통과 판본에 따라 다르게 읽을 수 있다.",
            "",
            "## 출처와 재생성",
            "",
            f"- [CBETA XML P5a](https://github.com/cbeta-git/xml-p5a)",
            f"- [CBETA 외자 데이터](https://github.com/cbeta-org/cbeta_gaiji)",
            f"- [한자-한글 데이터(CC0)](https://github.com/masoris/hanja_hangul) · "
            f"[라이선스]({HANJA_LICENSE_URL})",
            f"- [번체자 단어 분리 사전](https://github.com/ldkrsi/jieba-zh_TW) · "
            f"[MIT 라이선스]({SEGMENT_LICENSE_URL})",
            "- 생성 명령: `python3 scripts/generate_full_sutra_readings.py`",
            "- 원문 및 추출 결과의 SHA-256과 문자 수는 "
            "[`manifest.json`](./manifest.json)에 기록한다.",
        ]
    )
    if unknown:
        lines.extend(
            [
                "",
                "## 미확인 독음",
                "",
                "다음 글자는 자동 한자음 자료에서 확인되지 않아 `미상`으로 표시됐다.",
                "",
                ", ".join(f"`{char}`({count})" for char, count in sorted(unknown.items())),
            ]
        )
    (output_root / "README.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def generate(repo_root: Path, width: int, audit_only: bool) -> int:
    output_root = repo_root / "불교_경전" / "전문_한자음"
    scripture_root = repo_root / "불교_경전"
    cache_dir = repo_root / ".cache" / "buddist-sutra-builder"
    build_root = output_root.with_name(".전문_한자음.build")
    backup_root = output_root.with_name(".전문_한자음.backup")
    combined_build_root = scripture_root / ".전문_단일파일.build"
    readings = load_hanja_readings(fetch(HANJA_CSV_URL, cache_dir))
    readings.update(EXTRA_READINGS)
    gaiji = load_gaiji(fetch(GAIJI_JSON_URL, cache_dir), readings)
    dueum = load_dueum(fetch(DUEUM_CSV_URL, cache_dir))
    frequencies, frequency_total, max_word_length = load_segment_dictionary(
        fetch(SEGMENT_DICT_URL, cache_dir)
    )
    unknown: dict[str, int] = {}
    manifest: list[dict[str, object]] = []

    if not audit_only:
        if build_root.exists():
            shutil.rmtree(build_root)
        build_root.mkdir(parents=True)
        if combined_build_root.exists():
            shutil.rmtree(combined_build_root)
        combined_build_root.mkdir(parents=True)

    for sutra in SUTRAS:
        xml_data = fetch(CBETA_RAW + sutra.xml_path, cache_dir)
        juan_blocks = extract_juan(xml_data, gaiji)
        if len(juan_blocks) != sutra.expected_juan:
            raise ValueError(
                f"{sutra.slug}: expected {sutra.expected_juan} juan, "
                f"found {len(juan_blocks)}"
            )

        sutra_dir = build_root / sutra.slug
        if not audit_only:
            sutra_dir.mkdir(parents=True)
        guide_name = (
            "정토삼부경.md"
            if sutra.slug in {"무량수경", "관무량수경", "아미타경"}
            else f"{sutra.slug}.md"
        )
        sutra_index = [
            f"# {sutra.title_ko} 전문 한자음",
            "",
            f"- 원전: {sutra.title_zh}",
            f"- 대장경 번호: {sutra.taisho}",
            f"- 번역: {sutra.translator}",
            f"- 권수: {sutra.expected_juan}권",
            f"- [품별 우리말 풀이·해설](../../{guide_name})",
            "",
            "## 권별 파일",
            "",
        ]
        extracted_parts: list[str] = []
        combined_parts = [
            f"# {sutra.title_ko} — 전문 한자음",
            "",
            f"> 저본: CBETA 대정신수대장경 {sutra.taisho} 《{sutra.title_zh}》<br>",
            f"> 번역: {sutra.translator}<br>",
            f"> 원문 XML: [{sutra.xml_path}]({CBETA_RAW}{sutra.xml_path})",
            f"> 품별 우리말 풀이·해설: [{guide_name}]({guide_name})",
            "",
            "경전의 CBETA 기본 본문 전체를 한 파일에 모았다. 각 표의 첫째 줄은 "
            "원문이고 셋째 줄은 같은 열의 한자를 읽는 한글 음이다. 문장부호 "
            "아래의 빈칸은 정상이다.",
            "",
            "---",
            "",
        ]
        hanja_count = 0
        per_juan: list[dict[str, object]] = []
        for juan in sorted(juan_blocks):
            rendered, plain, count = render_juan(
                sutra,
                juan,
                juan_blocks[juan],
                readings,
                dueum,
                frequencies,
                frequency_total,
                max_word_length,
                unknown,
                width,
            )
            filename = f"{juan:03d}.md"
            if not audit_only:
                (sutra_dir / filename).write_text(rendered, encoding="utf-8")
                _, separator, body = rendered.partition("\n---\n\n")
                if not separator:
                    raise ValueError(f"{sutra.slug} 제{juan}권 본문 구분선을 찾지 못함")
                combined_parts.extend([f"## 제{juan}권", "", body.rstrip(), ""])
            sutra_index.append(f"- [제{juan}권]({filename})")
            extracted_parts.append(plain)
            hanja_count += count
            per_juan.append(
                {
                    "juan": juan,
                    "file": f"{sutra.slug}/{filename}",
                    "blocks": len(juan_blocks[juan]),
                    "characters": len(plain),
                    "hanja": count,
                    "text_sha256": sha256(plain.encode("utf-8")),
                }
            )

        if not audit_only:
            (sutra_dir / "README.md").write_text(
                "\n".join(sutra_index).rstrip() + "\n", encoding="utf-8"
            )
            (combined_build_root / f"{sutra.slug}_전문_한자음.md").write_text(
                "\n".join(combined_parts).rstrip() + "\n", encoding="utf-8"
            )
        extracted = "\n\n".join(extracted_parts)
        manifest.append(
            {
                "slug": sutra.slug,
                "title_ko": sutra.title_ko,
                "title_zh": sutra.title_zh,
                "taisho": sutra.taisho,
                "translator": sutra.translator,
                "source_url": CBETA_RAW + sutra.xml_path,
                "source_xml_sha256": sha256(xml_data),
                "juan_count": len(juan_blocks),
                "characters": len(extracted),
                "hanja_count": hanja_count,
                "extracted_text_sha256": sha256(extracted.encode("utf-8")),
                "juan": per_juan,
            }
        )

    summary = {
        "format_version": 1,
        "source_policy": "CBETA base text; notes and variant apparatus excluded",
        "reading_source": HANJA_CSV_URL,
        "reading_license": HANJA_LICENSE_URL,
        "dueum_source": DUEUM_CSV_URL,
        "segmentation_source": SEGMENT_DICT_URL,
        "segmentation_license": SEGMENT_LICENSE_URL,
        "gaiji_source": GAIJI_JSON_URL,
        "sutras": manifest,
        "unknown_readings": unknown,
    }
    if not audit_only:
        write_index(build_root, manifest, unknown)
        (build_root / "manifest.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if backup_root.exists():
            shutil.rmtree(backup_root)
        if output_root.exists():
            output_root.rename(backup_root)
        build_root.rename(output_root)
        if backup_root.exists():
            shutil.rmtree(backup_root)
        for combined_file in combined_build_root.glob("*_전문_한자음.md"):
            combined_file.replace(scripture_root / combined_file.name)
        combined_build_root.rmdir()

    print(
        json.dumps(
            {
                "sutras": len(manifest),
                "juan": sum(int(item["juan_count"]) for item in manifest),
                "hanja": sum(int(item["hanja_count"]) for item in manifest),
                "unknown_unique": len(unknown),
                "unknown_total": sum(unknown.values()),
                "unknown": unknown,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not unknown else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=16, help="characters per table row")
    parser.add_argument(
        "--audit-only", action="store_true", help="extract and audit without writing files"
    )
    args = parser.parse_args()
    if args.width < 4 or args.width > 24:
        parser.error("--width must be between 4 and 24")
    repo_root = Path(__file__).resolve().parents[1]
    return generate(repo_root, args.width, args.audit_only)


if __name__ == "__main__":
    sys.exit(main())
