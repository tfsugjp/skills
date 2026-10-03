#!/usr/bin/env python3
"""Validate Azure DevOps Wiki work item references in a UTF-8 Markdown file."""

import argparse
from pathlib import Path
import re
import sys
from typing import List, Optional, Tuple


FENCE = re.compile(r"^\s{0,3}(\x60{3,}|~{3,})(.*)$")
INLINE_CODE = re.compile(r"(?<!\x60)(\x60+).*?\1")
GITHUB_STYLE = re.compile(r"\bAB#(?:[0-9]+|<[^>]+>|\{[^}]+\})", re.IGNORECASE)


def prose_lines(markdown: str) -> Tuple[List[Tuple[int, str]], bool]:
    lines = []
    fence: Optional[Tuple[str, int]] = None
    for number, line in enumerate(markdown.splitlines(), 1):
        match = FENCE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = (marker[0], len(marker))
                continue
            if marker[0] == fence[0] and len(marker) >= fence[1] and not match.group(2).strip():
                fence = None
                continue
        if fence is None:
            lines.append((number, INLINE_CODE.sub("", line)))
    return lines, fence is not None


def validate(markdown: str, required_ids: List[str]) -> List[str]:
    lines, unclosed_fence = prose_lines(markdown)
    errors = []
    if unclosed_fence:
        errors.append("Wiki Markdown has an unclosed code fence.")
    prose = "\n".join(line for _, line in lines)
    reference_text = re.sub(r"\]\([^)]*\)", "]", prose)
    for number, line in lines:
        if GITHUB_STYLE.search(line):
            errors.append(
                "Line {} uses AB# for a work item; Azure DevOps Wiki requires # followed by the ID.".format(number)
            )
    for work_item_id in required_ids:
        reference = re.compile(r"(?<![A-Za-z0-9#])#{}(?![0-9])".format(re.escape(work_item_id)))
        if not reference.search(reference_text):
            errors.append("Wiki Markdown is missing the #{} work item reference.".format(work_item_id))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown_file", type=Path)
    parser.add_argument("--require-id", action="append", default=[], metavar="ID")
    args = parser.parse_args()
    if any(not value.isdecimal() or int(value) < 1 for value in args.require_id):
        parser.error("--require-id must be a positive decimal work item ID")
    try:
        raw = args.markdown_file.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise ValueError("Wiki Markdown must be UTF-8 without a BOM.")
        markdown = raw.decode("utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        print("Invalid Wiki Markdown: {}".format(exc), file=sys.stderr)
        return 1
    errors = validate(markdown, args.require_id)
    for error in errors:
        print("Invalid Wiki Markdown: {}".format(error), file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
