#!/usr/bin/env python3
"""Validate a UTF-8 GitHub issue body before --body-file submission."""

import argparse
from pathlib import Path
import re
import sys
from typing import List


FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(?:[^`~]*)$")
ESCAPED_NEWLINE = re.compile(r"(?<!\\)\\r\\n|(?<!\\)\\n(?=$|[\s\\#>*+|<-]|\d+[.)]\s)|(?<=[.!?。！？])\\n")
INLINE_CODE = re.compile(r"(?<!\x60)(\x60+).*?\1")


def validate(body: str) -> List[str]:
    errors = []
    if not body.strip():
        return ["Issue body is empty."]

    opening = None
    outside_lines = []
    for number, line in enumerate(body.splitlines(), 1):
        fence = FENCE.match(line)
        if fence:
            marker = fence.group(1)
            if opening is None:
                opening = (marker[0], len(marker))
            elif marker[0] == opening[0] and len(marker) >= opening[1]:
                opening = None
            continue
        if opening is None:
            outside_lines.append(line)
            prose = INLINE_CODE.sub("", line)
            if ESCAPED_NEWLINE.search(prose):
                errors.append(f"Line {number} contains a literal escaped newline outside a code fence.")

    if opening is not None:
        errors.append("Issue body has an unclosed code fence.")
    if not any(line.strip() for line in outside_lines):
        errors.append("Issue body contains only a code fence; add actual issue prose.")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("body_file", type=Path)
    args = parser.parse_args()
    try:
        raw = args.body_file.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise ValueError("Issue body must be UTF-8 without a BOM.")
        body = raw.decode("utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Invalid issue body: {exc}", file=sys.stderr)
        return 1

    errors = validate(body)
    for error in errors:
        print(f"Invalid issue body: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
