#!/usr/bin/env python3
"""Build a chapter-by-chapter Dhammapada edition with source, reading, and guide.

The source blocks come directly from the same CBETA T210 extraction used by the
volume edition.  The Korean explanation is taken from the 39품 section in
불교_경전/법구경.md, so each chapter has one consistent translation note and
commentary next to its complete source blocks.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "scripts" / "generate_full_sutra_readings.py"
spec = importlib.util.spec_from_file_location("sutra_builder", GENERATOR_PATH)
builder = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)


CHAPTERS = [
    ("무상품", "無常品"), ("교학품", "教學品"), ("다문품", "多聞品"),
    ("독신품", "篤信品"), ("계신품", "戒慎品"), ("유념품", "惟念品"),
    ("자인품", "慈仁品"), ("언어품", "言語品"), ("쌍요품", "雙要品"),
    ("방일품", "放逸品"), ("심의품", "心意品"), ("화향품", "華香品"),
    ("우암품", "愚闇品"), ("명철품", "明哲品"), ("나한품", "羅漢品"),
    ("술천품", "述千品"), ("악행품", "惡行品"), ("도장품", "刀杖品"),
    ("노모품", "老耗品"), ("애신품", "愛身品"), ("세속품", "世俗品"),
    ("술불품", "述佛品"), ("안녕품", "安寧品"), ("호희품", "好喜品"),
    ("분노품", "忿怒品"), ("진구품", "塵垢品"), ("봉지품", "奉持品"),
    ("도행품", "道行品"), ("광연품", "廣衍品"), ("지옥품", "地獄品"),
    ("상유품", "象喻品"), ("애욕품", "愛欲品"), ("이양품", "利養品"),
    ("사문품", "沙門品"), ("범지품", "梵志品"), ("니원품", "泥洹品"),
    ("생사품", "生死品"), ("도리품", "道利品"), ("길상품", "吉祥品"),
]


def load_builder_data():
    cache = ROOT / ".cache" / "buddist-sutra-builder"
    readings = builder.load_hanja_readings(builder.fetch(builder.HANJA_CSV_URL, cache))
    readings.update(builder.EXTRA_READINGS)
    gaiji = builder.load_gaiji(builder.fetch(builder.GAIJI_JSON_URL, cache), readings)
    dueum = builder.load_dueum(builder.fetch(builder.DUEUM_CSV_URL, cache))
    frequencies, total, max_length = builder.load_segment_dictionary(
        builder.fetch(builder.SEGMENT_DICT_URL, cache)
    )
    return cache, readings, gaiji, dueum, frequencies, total, max_length


def chapter_ranges(blocks: list[str]) -> list[tuple[int, str, int, int]]:
    starts: list[tuple[int, str]] = []
    for index, block in enumerate(blocks):
        for korean, chinese in CHAPTERS:
            if block.startswith(chinese) and (
                "品法句經" in block or re.match(r"^無常品第一", block)
            ):
                starts.append((index, korean))
                break
    if len(starts) != len(CHAPTERS):
        raise ValueError(f"expected 39 chapter headings, found {len(starts)}")
    ranges = []
    for position, (start, korean) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(blocks)
        ranges.append((position + 1, korean, start, end))
    return ranges


def guide_sections() -> dict[int, tuple[str, str]]:
    guide = (ROOT / "불교_경전" / "법구경.md").read_text(encoding="utf-8")
    pattern = re.compile(
        r"^### (\d+)\. ([^\n]+)\n\*\*우리말 풀이:\*\* (.*?)\n\*\*해설:\*\* (.*?)(?=\n### |\n## )",
        re.M | re.S,
    )
    result = {}
    for match in pattern.finditer(guide):
        result[int(match.group(1))] = (match.group(3).strip(), match.group(4).strip())
    if len(result) != 39:
        raise ValueError(f"expected 39 Korean guide sections, found {len(result)}")
    return result


def main() -> int:
    cache, readings, gaiji, dueum, frequencies, total, max_length = load_builder_data()
    source = builder.fetch(builder.CBETA_RAW + "T/T04/T04n0210.xml", cache)
    juan_blocks = builder.extract_juan(source, gaiji)
    blocks = juan_blocks[1] + juan_blocks[2]
    ranges = chapter_ranges(blocks)
    guides = guide_sections()
    unknown: dict[str, int] = {}
    output_parts = [
        "# 법구경 39품별 원문·한글 발음·우리말 풀이·해설",
        "",
        "> 저본: CBETA 대정신수대장경 T04 No. 210 《法句經》<br>",
        "> 번역: 오나라 유기난 등<br>",
        "> 원문은 T210의 두 권에서 품 경계를 따라 재배열했으며, 각 표의 첫째 줄은 한자 원문, 셋째 줄은 같은 열의 한글 발음이다.",
        "",
        "원문 전체와 품별 풀이·해설을 한 파일에 함께 배치했다. 교감 각주와 판본별 이문은 [권별 전문 대조본](전문_한자음/README.md)에서 범위 원칙을 확인할 수 있다.",
        "",
        "---",
        "",
    ]
    for number, korean, start, end in ranges:
        _, chinese = CHAPTERS[number - 1]
        output_parts.extend([f"## 제{number}품 {korean}({chinese})", ""])
        output_parts.extend(["### 원문과 한글 발음", ""])
        # Keep the T210 title/translator blocks with the first chapter of each
        # volume so the 품별 file does not silently drop any source characters.
        prefix: list[str] = []
        chapter_end = end
        if number == 21:
            # The four title/translator blocks for 卷下 belong to 품 22.
            chapter_end = len(juan_blocks[1])
        chapter_blocks = blocks[start:chapter_end]
        if number == 1:
            prefix = blocks[:start]
        elif number == 22:
            second_volume_start = len(juan_blocks[1])
            prefix = blocks[second_volume_start:start]
        for block in prefix + chapter_blocks:
            output_parts.append(
                builder.render_block(
                    block, readings, dueum, frequencies, total, max_length, unknown, 16
                ).rstrip()
            )
        풀이, 해설 = guides[number]
        output_parts.extend([
            "",
            "### 우리말 풀이",
            "",
            풀이,
            "",
            "### 해설",
            "",
            해설,
            "",
            "---",
            "",
        ])
    if unknown:
        raise ValueError(f"unknown readings: {unknown}")
    target = ROOT / "불교_경전" / "법구경_품별_원문_풀이_해설.md"
    target.write_text("\n".join(output_parts).rstrip() + "\n", encoding="utf-8")
    print(f"wrote {target} ({target.stat().st_size:,} bytes, 39품)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
