#!/usr/bin/env python3
"""Reconstruct continuous source text from the repository's reading tables.

The reading tables live in ``불교_경전/전문_한자음/<경전>/`` as one Markdown file
per volume (``001.md``, ``002.md``, …).  Pass either that directory to read a
whole scripture in volume order, or a single file to read one volume.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


TABLE_SEPARATOR = re.compile(r"^\|\s*:?-{3,}")
VOLUME_FILE = re.compile(r"^\d+\.md$")


def volume_files(directory: Path) -> list[Path]:
    """Return the numbered volume files of one scripture, in reading order."""
    files = sorted(p for p in directory.iterdir() if VOLUME_FILE.match(p.name))
    if not files:
        raise RuntimeError(f"권별 한자음 파일을 찾지 못했습니다: {directory}")
    return files


def extract_file(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    source: list[str] = []
    for index, line in enumerate(lines[:-1]):
        if not line.startswith("|") or not TABLE_SEPARATOR.match(lines[index + 1]):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        source.extend(cell for cell in cells if cell not in {"", "　", "&nbsp;"})
    return "".join(source)


def extract_source(path: Path) -> str:
    """Read one volume file, or every volume of a scripture directory in order."""
    if path.is_dir():
        return "".join(extract_file(volume) for volume in volume_files(path))
    return extract_file(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "sources",
        type=Path,
        nargs="+",
        help="경전 한자음 디렉터리 또는 권별 파일",
    )
    args = parser.parse_args()
    for path in args.sources:
        print(extract_source(path))


if __name__ == "__main__":
    main()
