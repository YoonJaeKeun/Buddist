#!/usr/bin/env python3
"""Reconstruct continuous source text from the repository's reading tables."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


TABLE_SEPARATOR = re.compile(r"^\|\s*:?-{3,}")


def extract_source(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    source: list[str] = []
    for index, line in enumerate(lines[:-1]):
        if not line.startswith("|") or not TABLE_SEPARATOR.match(lines[index + 1]):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        source.extend(cell for cell in cells if cell not in {"", "　", "&nbsp;"})
    return "".join(source)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", type=Path, nargs="+")
    args = parser.parse_args()
    for path in args.sources:
        print(extract_source(path))


if __name__ == "__main__":
    main()
