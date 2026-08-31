#!/usr/bin/env python3
"""Check that a 문장별 풀이·해설 manuscript covers its source text without gaps.

The manuscripts in this repository pair every 원문 block with a 우리말 풀이 and a
해설.  This script rebuilds the continuous source text from the repository's
reading tables (see ``extract_pronunciation_text.py``), concatenates the 원문
blocks of a manuscript, and walks both in order.  It reports:

* the character span of the source that the manuscript covers,
* any source text skipped between two consecutive 원문 blocks,
* any 원문 block that cannot be found in the source at all.

A manuscript is complete when it reports ``누락 구간 0건`` and its end position
reaches the end of the intended range.

Usage::

    python scripts/check_passage_coverage.py 불교_경전/아미타경_전문_한자음.md \\
        불교_경전/아미타경_문장별_풀이_해설.md

Several manuscripts may share one source (for example the two volumes of the
무량수경); pass the source once followed by every manuscript to check.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from extract_pronunciation_text import extract_source


PASSAGE = re.compile(r"^\*\*원문\*\*(.*)$", re.MULTILINE)
NOISE = re.compile(r"\*\*|`|\s")


def normalise(text: str) -> str:
    """Strip the markup and whitespace that never appears in the source text."""
    return NOISE.sub("", text)


def check(source: str, manuscript: Path) -> bool:
    passages = PASSAGE.findall(manuscript.read_text(encoding="utf-8"))
    if not passages:
        print(f"{manuscript.name}: 원문 블록을 찾지 못했습니다.")
        return False

    joined = normalise("".join(passages))
    start = source.find(normalise(passages[0]))
    print(f"--- {manuscript.name} ---")
    print(f"단락 수: {len(passages)}, 원문 글자수: {len(joined)}")
    if start < 0:
        print("첫 원문 블록을 저본에서 찾지 못했습니다.")
        return False
    print(f"저본 내 시작 위치: {start}")

    position = start
    gaps: list[tuple[int, str]] = []
    missing: list[tuple[int, str]] = []
    for number, passage in enumerate(passages, 1):
        cleaned = normalise(passage)
        found = source.find(cleaned, position)
        if found < 0:
            missing.append((number, cleaned[:40]))
            continue
        if found > position:
            gaps.append((number, source[position:found]))
        position = found + len(cleaned)

    print(f"저본 내 끝 위치: {position} / {len(source)}")
    for number, head in missing:
        print(f"  !! 단락 {number}: 저본에서 찾지 못함 -> {head}")
    print(f"누락 구간 {len(gaps)}건")
    for number, gap in gaps:
        print(f"  단락 {number} 앞 누락({len(gap)}자): {gap[:120]}")
    if position < len(source):
        print(f"끝난 뒤 저본에 남은 {len(source) - position}자: {source[position:position + 120]}")
    return not gaps and not missing


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="전문 한자음 표 파일")
    parser.add_argument("manuscripts", type=Path, nargs="+", help="문장별 풀이·해설 원고")
    args = parser.parse_args()

    source = normalise(extract_source(args.source))
    clean = all(check(source, manuscript) for manuscript in args.manuscripts)
    sys.exit(0 if clean else 1)


if __name__ == "__main__":
    main()
