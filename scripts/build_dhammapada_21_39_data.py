#!/usr/bin/env python3
"""Build verse-aligned T210 source and Korean base renderings for chapters 21-39."""

from __future__ import annotations

import difflib
import html
import importlib.util
import pprint
import re
import ssl
import sys
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "buddist-sutra-builder"
XML = CACHE / "8980644a8f36aeec-T04n0210.xml"
GAIJI = CACHE / "262237f7c9196fb3-cbeta_gaiji.json"
OUT = ROOT / "scripts" / "dhammapada_data_21_39.py"
KABC_URL = "https://kabc.dongguk.edu/content/view?dataId=ABC_IT_K1021_T_00{}"

CHAPTER_NAMES = {
    21: "세속품", 22: "술불품", 23: "안녕품", 24: "호희품", 25: "분노품",
    26: "진구품", 27: "봉지품", 28: "도행품", 29: "광연품", 30: "지옥품",
    31: "상유품", 32: "애욕품", 33: "이양품", 34: "사문품", 35: "범지품",
    36: "니원품", 37: "생사품", 38: "도리품", 39: "길상품",
}

CHAPTER_COUNTS = {
    21: 14, 22: 21, 23: 14, 24: 12, 25: 26, 26: 19, 27: 17, 28: 28,
    29: 14, 30: 16, 31: 18, 32: 32, 33: 20, 34: 32, 35: 40, 36: 36,
    37: 18, 38: 19, 39: 19,
}

VERSE_COUNTS = {**CHAPTER_COUNTS, 36: 35}

NUMBER_WORDS = {
    14: "열네", 21: "스물한", 12: "열두", 26: "스물여섯", 19: "열아홉",
    17: "열일곱", 28: "스물여덟", 16: "열여섯", 18: "열여덟", 32: "서른두",
    20: "스무", 40: "마흔", 36: "서른여섯",
}

VARIANTS = str.maketrans(
    "爲衆閒卽㝵迴僞淸眞飮著恆峯羣顏牀旣愼",
    "為眾間即礙回偽清真飲着恒峰群顔床既慎",
)

APPENDIX_TRANSLATIONS = [
    "법구경이다.",
    "상권이다.",
    "법구경이다.",
    "서문이다.",
    (
        "『담발게』는 여러 경전의 핵심 뜻을 모은 것이다. ‘담’은 법이고 ‘발’은 구절이다. "
        "《법구경》에는 900게송본·700게송본·500게송본 등 여러 전승이 있다. 게송은 시와 같이 뜻을 맺는 말이며, "
        "부처님이 여러 상황을 보고 설한 것이어서 한때에 한꺼번에 말씀한 것이 아니고 여러 경전에 흩어져 있다. "
        "일체지이신 부처님은 큰 자비로 세상에 출현하여 도의 뜻을 드러내 사람들을 깨우치셨다. 열두 부류의 경전에서 "
        "그 요점을 모아 여러 부로 나누었다. 부처님이 열반한 뒤 아난이 전한 네 아함은 분량과 관계없이 ‘이와 같이 들었다’고 "
        "시작하여 설법 장소와 내용을 밝힌다. 그 뒤 다섯 부파의 사문들이 여러 경전의 네 구절 또는 여섯 구절 게송을 뽑아 "
        "뜻에 따라 품을 나누었고, 열두 부류의 경전을 두루 참작했으므로 특정 경 이름 대신 ‘법구’라 불렀다. "
        "근세의 갈씨가 전한 700게송은 뜻이 매우 깊었으나 번역 과정에서 다소 흐려졌다. 부처님을 만나고 그 말씀을 듣기 어려우며, "
        "천축과 중국의 언어와 사물 이름이 서로 달라 뜻을 그대로 전하기가 쉽지 않았기 때문이다."
    ),
    (
        "옛날 남조의 안후 세고와 도위 불조가 범어를 중국말로 옮긴 번역은 원문의 체를 잘 얻었으나 계승하기 어려웠다. "
        "뒤의 번역들은 정밀하지 못한 점이 있어도 그 가르침을 귀하게 여겨 대체적인 뜻은 전하였다."
    ),
    (
        "처음 유기난이 천축에서 나와 황무 3년인 224년에 무창에 왔을 때, 지겸은 그에게서 500게송본을 받고 도반 축장염에게 "
        "번역을 부탁하였다. 축장염은 천축 말에는 능했으나 한문에는 충분히 익숙하지 않아 뜻으로 옮기거나 음역했고 문장은 질박했다. "
        "지겸이 문장이 우아하지 않다고 하자 유기난은 부처님의 말씀은 뜻과 법을 취할 뿐 꾸밈과 장엄을 요구하지 않으며, 읽는 사람이 "
        "쉽게 이해하면서 본뜻을 잃지 않는 번역이 좋다고 답했다. 자리의 사람들도 노자와 공자의 말을 들어 아름다운 수사보다 믿을 만한 "
        "뜻이 중요하다고 동의했다. 그래서 번역자의 말을 받아 본뜻에 따라 다듬되 지나치게 꾸미지 않았고, 이해하지 못한 곳은 억지로 "
        "옮기지 않아 빠진 구절도 생겼다. 문장은 질박하고 간결하지만 뜻은 깊고 넓으며 여러 경전과 연결된다. 천축에서는 처음 배우는 "
        "사람이 《법구경》을 배우지 않으면 순서를 건너뛰었다고 했다. 이 경은 초심자에게는 큰 디딤돌이고 깊이 공부하는 이에게는 "
        "오묘한 보고여서, 어리석음과 의혹을 밝히고 스스로 서게 한다."
    ),
    (
        "예전에 이 경을 번역할 때 이해하지 못한 곳이 있었는데 마침 축장염이 다시 오자 자문하여 게송을 보완하고 열세 품을 더 얻었다. "
        "옛 전승과 교정하여 늘리고 바로잡은 뒤 한 부 서른아홉 편, 모두 752장으로 정리하였다. 이 작업이 널리 묻고 배우는 데 보탬이 "
        "되기를 바란다는 뜻으로 서문을 맺는다."
    ),
]


def load_builder():
    path = ROOT / "scripts" / "generate_full_sutra_readings.py"
    spec = importlib.util.spec_from_file_location("sutra_builder", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["sutra_builder"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def clean_dt(body: str) -> str:
    body = re.sub(
        r'<span[^>]*(?:class="para_line"|data-jusok-type)[^>]*>.*?</span>',
        "",
        body,
        flags=re.S,
    )
    body = re.sub(r"<br[^>]*>", " ", body)
    body = re.sub(r"<[^>]+>", "", body)
    body = html.unescape(body).replace("\xa0", " ")
    return re.sub(r"\s+", " ", body).strip()


def fetch_kabc() -> dict[int, dict[str, object]]:
    result: dict[int, dict[str, object]] = {}
    for volume in (1, 2):
        url = KABC_URL.format(volume)
        try:
            response = urllib.request.urlopen(url, timeout=60)
        except urllib.error.URLError:
            # The KABC server chain is not recognized by some WSL CA stores.
            response = urllib.request.urlopen(
                url,
                context=ssl._create_unverified_context(),
                timeout=60,
            )
        with response:
            page = response.read().decode("utf-8")
        rows = []
        for match in re.finditer(
            r'<dt[^>]*data-xsl-paranum="(\d+)([RT])"[^>]*>(.*?)</dt>',
            page,
            re.S,
        ):
            number, kind, body = match.groups()
            rows.append((number, kind, clean_dt(body)))
        paired: dict[str, dict[str, str]] = {}
        for number, kind, body in rows:
            paired.setdefault(number, {})[kind] = body
        sequence = list(paired.values())
        for index, pair in enumerate(sequence):
            title = pair.get("R", "")
            found = re.match(r"(\d+)\.\s.*?\[(\d+)장\]", title)
            if not found:
                continue
            chapter, count = map(int, found.groups())
            if not 21 <= chapter <= 39:
                continue
            verse_count = VERSE_COUNTS[chapter]
            result[chapter] = {
                "intro": sequence[index + 1],
                "verses": sequence[index + 2 : index + 2 + verse_count],
            }
    return result


def canonical_chars(value: str) -> tuple[str, list[int]]:
    chars = []
    positions = []
    normalized = unicodedata.normalize("NFKC", value).translate(VARIANTS)
    for index, char in enumerate(normalized):
        if unicodedata.category(char)[0] in "PZ" or char.isdigit():
            continue
        chars.append(char)
        positions.append(index)
    return "".join(chars), positions


def cbeta_chapters() -> dict[int, list[str]]:
    builder = load_builder()
    gaiji = builder.load_gaiji(GAIJI.read_bytes(), {})
    juans = builder.extract_juan(XML.read_bytes(), gaiji)
    result = {}
    for juan, first_chapter in ((1, 1), (2, 22)):
        blocks = juans[juan]
        starts = []
        for index, block in enumerate(blocks):
            if juan == 1 and index == 4 and block.startswith("無常品"):
                starts.append(index)
            elif "品法句經" in block[:30]:
                starts.append(index)
        starts.append(len(blocks))
        for offset in range(len(starts) - 1):
            result[first_chapter + offset] = blocks[starts[offset] : starts[offset + 1]]
    return result


def map_boundary(position: int, total: int, target_total: int, opcodes) -> int:
    if position >= total:
        return target_total
    for _tag, a1, a2, b1, b2 in opcodes:
        if a1 <= position <= a2 and a2 > a1:
            return round(b1 + (position - a1) * (b2 - b1) / (a2 - a1))
    return round(position * target_total / total)


def group_t210_verses(chapter: int, blocks: list[str], kabc_verses) -> list[str]:
    body_start = 2 if chapter in (36, 37, 38) else 3
    raw = "".join(blocks[body_start:])
    if chapter == 21:
        raw = raw.split("法句經卷上", 1)[0]

    kabc_parts = [canonical_chars(pair["T"])[0] for pair in kabc_verses]
    kabc_all = "".join(kabc_parts)
    cbeta_all, raw_positions = canonical_chars(raw)
    matcher = difflib.SequenceMatcher(None, kabc_all, cbeta_all, autojunk=False)
    opcodes = matcher.get_opcodes()

    canonical_bounds = [0]
    cursor = 0
    for part in kabc_parts:
        cursor += len(part)
        canonical_bounds.append(map_boundary(cursor, len(kabc_all), len(cbeta_all), opcodes))
    raw_bounds = [0]
    for bound in canonical_bounds[1:]:
        raw_bounds.append(raw_positions[bound] if bound < len(raw_positions) else len(raw))
    grouped = [raw[raw_bounds[i] : raw_bounds[i + 1]] for i in range(len(kabc_parts))]
    assert all(canonical_chars(item)[0] for item in grouped), (chapter, "empty verse")
    assert canonical_chars("".join(grouped))[0] == cbeta_all
    return grouped


def modernize_translation(value: str) -> str:
    value = re.sub(r"^【\d+】\s*", "", value)
    replacements = {
        "제 몸": "자신", "제 마음": "자기 마음", "온갖": "모든",
        "나쁜 세계": "악한 세계", "삿된": "그릇된", "이내": "곧",
        "깨우쳐": "깨우쳐서", "못하리라": "못한다", "없으리라": "없다",
        "되리라": "될 것이다",
        "얻으리라": "얻게 된다", "받으리라": "받게 된다",
        "하리라": "할 것이다", "가리라": "가게 된다", "오르리라": "오르게 된다",
        "따르리라": "따르게 된다", "사라지리라": "사라진다",
        "이루어지리라": "이루어진다", "편안하리라": "편안하다",
    }
    for before, after in replacements.items():
        value = value.replace(before, after)
    value = value.replace("ㆍ", "·")
    return re.sub(r"\s+", " ", value).strip()


def main() -> None:
    kabc = fetch_kabc()
    cbeta = cbeta_chapters()
    data: dict[int, list[tuple[str, str]]] = {}

    for chapter in range(21, 40):
        blocks = cbeta[chapter]
        verses = kabc[chapter]["verses"]
        assert len(verses) == VERSE_COUNTS[chapter]
        grouped_sources = group_t210_verses(chapter, blocks, verses)
        extra_entries = []
        if chapter == 38:
            extra_source = "今我上體首，　白生為被盜，已有天使召，　時正宜出家。"
            assert grouped_sources[-1].endswith(extra_source)
            grouped_sources[-1] = grouped_sources[-1][: -len(extra_source)]
            extra_entries.append((
                extra_source,
                "이제 내 머리에 흰머리가 돋아 삶이 도둑맞고 있으며, 이미 하늘의 사자가 부르니 지금이야말로 출가하기에 알맞다.",
            ))
        if chapter == 39:
            extra_source = "法句經卷下"
            assert grouped_sources[-1].endswith(extra_source)
            grouped_sources[-1] = grouped_sources[-1][: -len(extra_source)]
            extra_entries.append((extra_source, "법구경 하권의 끝이다."))
        entries: list[tuple[str, str]] = []

        if chapter in (36, 37, 38):
            entries.append((
                blocks[0],
                f"법구경 제{chapter}품 {CHAPTER_NAMES[chapter]}이며 모두 "
                f"{NUMBER_WORDS[CHAPTER_COUNTS[chapter]]} 장이다.",
            ))
            intro_index = 1
        else:
            entries.extend([
                (blocks[0], f"법구경 제{chapter}품 {CHAPTER_NAMES[chapter]}이다."),
                (
                    blocks[1],
                    f"제{chapter}품은 모두 {NUMBER_WORDS[CHAPTER_COUNTS[chapter]]} 장이다.",
                ),
            ])
            intro_index = 2

        entries.append((blocks[intro_index], modernize_translation(kabc[chapter]["intro"]["R"])))
        entries.extend(
            (source, modernize_translation(pair["R"]))
            for source, pair in zip(grouped_sources, verses)
        )
        entries.extend(extra_entries)

        if chapter == 21:
            appendix_sources = blocks[24:]
            assert len(appendix_sources) == len(APPENDIX_TRANSLATIONS)
            entries.extend(zip(appendix_sources, APPENDIX_TRANSLATIONS))
        data[chapter] = entries

    header = (
        '"""Generated verse-aligned T210 data for chapters 21-39.\n\n'
        "Source text: CBETA T04 No.210. Korean base renderings were checked against\n"
        "KABC K1021 and normalized for this project. Regenerate with\n"
        "python3 scripts/build_dhammapada_21_39_data.py.\n"
        '"""\n\n'
    )
    OUT.write_text(
        header + "DATA = " + pprint.pformat(data, width=120, sort_dicts=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT.relative_to(ROOT)} with {sum(map(len, data.values()))} entries")


if __name__ == "__main__":
    main()
