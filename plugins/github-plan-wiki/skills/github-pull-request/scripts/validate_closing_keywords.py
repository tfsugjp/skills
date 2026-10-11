#!/usr/bin/env python3
"""Check explicit PR closure targets against standalone Fixed/Close entries."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


REPOSITORY = r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
REFERENCE = rf"(?:{REPOSITORY})?#[1-9][0-9]*"
ENTRY = re.compile(rf"(?:[-+*] +)?(Fixed|Close) +({REFERENCE})\.?", re.I)
LIST_ITEM = re.compile(r"^( *)(?:[-+*]|[0-9]{1,9}[.)])( +|$)")
CLOSING = re.compile(
    rf"\b(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?)\s*:?[ \t]+({REFERENCE})(?![\w/])",
    re.I,
)


def target(value: str, repository: str) -> str:
    if re.fullmatch(r"#?[1-9][0-9]*", value):
        return repository.lower() + "#" + value.lstrip("#")
    if re.fullmatch(rf"{REPOSITORY}#[1-9][0-9]*", value):
        return value.lower()
    raise ValueError(f"Invalid issue target: {value}")


def prose_lines(body: str):
    """Exclude non-prose contexts; closing entries must be ordinary text lines."""
    body = re.sub(r"<!--[\s\S]*?(?:-->|\Z)", "\n", body)
    body = re.sub(r"<(pre|code|script|style)\b[^>]*>[\s\S]*?(?:</\1\s*>|\Z)", "\n", body, flags=re.I)
    fence = None
    list_content = None  # content column of the innermost open list item
    after_blank = False
    visible = []
    for line in body.splitlines():
        marker = re.match(r"^\s*(?:[-+*] +)?(`{3,}|~{3,})(.*)$", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        expanded = line.expandtabs(4)
        indent = len(expanded) - len(expanded.lstrip(" "))
        if not expanded.strip():
            after_blank = True
            visible.append("")
            continue
        # An indented line is a code block only when it is 4+ columns past the
        # enclosing list item's content column (CommonMark list-item rules).
        base = list_content if list_content is not None else 0
        item = LIST_ITEM.match(expanded)
        if indent >= base + 4 or expanded.lstrip().startswith(">"):
            visible.append("")
            continue
        if item:
            spaces = len(item[2])
            marker_end = item.end() - spaces
            list_content = marker_end + (spaces if 1 <= spaces <= 4 else 1)
        elif indent < base and after_blank:
            list_content = None  # a blank line then dedented text ends the list
        after_blank = False
        visible.append(line)
    text = "\n".join(visible)
    ticks = list(re.finditer(r"`+", text))
    output, cursor, index = [], 0, 0
    while index < len(ticks):
        opening = ticks[index]
        prefix = text[:opening.start()]
        # Escaped delimiters and unmatched ticks are literal Markdown text.
        if (len(prefix) - len(prefix.rstrip("\\"))) % 2:
            index += 1
            continue
        closing_index = next((i for i in range(index + 1, len(ticks)) if ticks[i][0] == opening[0]), None)
        if closing_index is None:
            index += 1
            continue
        closing = ticks[closing_index]
        output.extend((text[cursor:opening.start()], "\n" * text[opening.start():closing.end()].count("\n") + " "))
        cursor, index = closing.end(), closing_index + 1
    output.append(text[cursor:])
    yield from (line.strip() for line in "".join(output).splitlines())


def validate(body: str, repository: str, bugs=(), closes=(), reference_only=False, commit_messages: str = "") -> list[str]:
    if not re.fullmatch(REPOSITORY, repository):
        raise ValueError("--repo must be owner/repository")
    expected = {}
    for keyword, values in (("fixed", bugs), ("close", closes)):
        for value in values:
            issue = target(value, repository)
            if issue in expected and expected[issue] != keyword:
                raise ValueError(f"Issue classified as both bug and other work: {issue}")
            expected[issue] = keyword
    if reference_only == bool(expected):
        raise ValueError("Provide closure targets or --reference-only, exclusively")
    errors = []
    if not body.strip() or body.startswith("\ufeff") or "\x00" in body:
        errors.append("Body must be nonempty UTF-8 without BOM or NUL")
    seen = set()
    for line in prose_lines(body):
        entry = ENTRY.fullmatch(line)
        if entry:
            keyword, reference = entry.groups()
            issue = target(reference, repository)
            if issue not in expected:
                errors.append(f"Unplanned closure: {issue}")
            elif expected[issue] != keyword.lower():
                errors.append(f"Use {expected[issue].title()} for {issue}")
            elif issue in seen:
                errors.append(f"Duplicate closure: {issue}")
            else:
                seen.add(issue)
        elif CLOSING.search(line):
            errors.append(f"Use one standalone Fixed/Close entry per issue: {line}")
    for issue in sorted(expected.keys() - seen):
        errors.append(f"Missing {expected[issue].title()} entry: {issue}")
    errors.extend(commit_errors(commit_messages, repository, set(expected)))
    return errors


def commit_errors(messages: str, repository: str, expected: set[str]) -> list[str]:
    """Flag closing keywords in commit messages that GitHub would act on at merge."""
    errors = []
    for match in CLOSING.finditer(messages):
        issue = target(match[1], repository)
        if issue not in expected:
            errors.append(f"Unplanned closure in commit message: {issue}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("body_file", type=Path)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--bug", action="append", default=[])
    parser.add_argument("--close", action="append", default=[])
    parser.add_argument("--commit-messages", type=Path, help="file with the full messages of the PR's commits")
    parser.add_argument("--reference-only", action="store_true")
    args = parser.parse_args()
    try:
        body = args.body_file.read_text(encoding="utf-8")
        commits = args.commit_messages.read_text(encoding="utf-8") if args.commit_messages else ""
        errors = validate(body, args.repo, args.bug, args.close, args.reference_only, commits)
    except (OSError, UnicodeError, ValueError) as error:
        errors = [str(error)]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("PR closing keywords match the intended issue targets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
