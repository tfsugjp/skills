#!/usr/bin/env python3
"""Check GitHub Wiki Home routes and plan dates before publication."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit


JST = timezone(timedelta(hours=9))
MARKDOWN_LINK = re.compile(r"\[[^]]*\]\(([^)]+)\)")
TABLE_SEPARATOR = re.compile(r"^:?-{3,}:?$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def public_name(path: Path) -> str:
    return re.sub(r"\s+", "-", path.stem.strip()).casefold()


def git_output(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def page_date(root: Path, page: Path) -> str:
    relative = page.relative_to(root).as_posix()
    if git_output(root, "status", "--porcelain", "--untracked-files=all", "--", relative):
        return datetime.now(JST).date().isoformat()
    committed = git_output(root, "log", "-1", "--format=%cI", "--", relative)
    if not committed:
        raise ValueError(f"no Git history for {relative}")
    return datetime.fromisoformat(committed).astimezone(JST).date().isoformat()


def table_cells(line: str) -> list[str]:
    if not line.startswith("|") or not line.endswith("|"):
        return []
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line[1:-1])]


def check_wiki_link(
    target: str, source: Path, owner: str, repo: str, routes: dict[str, Path], errors: list[str]
) -> str | None:
    if target.startswith("#"):
        return None
    parsed = urlsplit(target)
    prefix = f"/{owner}/{repo}/wiki/"
    if parsed.scheme or parsed.netloc:
        if parsed.netloc.casefold() != "github.com":
            return None
        if not parsed.path.startswith(prefix) and not parsed.path.startswith(prefix[:-1]):
            return None
        if parsed.scheme != "https" or not parsed.path.startswith(prefix):
            errors.append(f"{source}: noncanonical wiki link: {target}")
            return None
        name = unquote(parsed.path[len(prefix) :])
    else:
        errors.append(f"{source}: relative wiki link: {target}")
        return None
    if not name or "/" in name or name.endswith(".md") or parsed.query:
        errors.append(f"{source}: noncanonical wiki route: {target}")
        return None
    route = name.casefold()
    if route not in routes:
        errors.append(f"{source}: missing wiki page for {target}")
        return None
    if name != re.sub(r"\s+", "-", routes[route].stem.strip()):
        errors.append(f"{source}: URL does not match the page's public name: {target}")
    return route


def check_links(
    root: Path, page: Path, owner: str, repo: str, routes: dict[str, Path], errors: list[str]
) -> None:
    for target in MARKDOWN_LINK.findall(page.read_text(encoding="utf-8")):
        check_wiki_link(target, page.relative_to(root), owner, repo, routes, errors)


def home_rows(
    root: Path, home: Path, owner: str, repo: str, routes: dict[str, Path], errors: list[str]
) -> dict[str, str]:
    rows: dict[str, str] = {}
    category: str | None = None
    in_plan_table = False
    for number, line in enumerate(home.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("## "):
            category = line[3:].strip()
            in_plan_table = False
        cells = table_cells(line)
        if len(cells) == 4 and cells[1] in {"Date", "日付"}:
            if not category:
                errors.append(f"{home.name}:{number}: plan table has no H2 category")
            in_plan_table = True
            continue
        if not in_plan_table:
            continue
        if not cells:
            in_plan_table = False
            continue
        if all(TABLE_SEPARATOR.fullmatch(cell) for cell in cells):
            continue
        if len(cells) != 4:
            errors.append(f"{home.name}:{number}: plan row must have four columns")
            continue
        match = MARKDOWN_LINK.search(cells[0])
        if not match:
            errors.append(f"{home.name}:{number}: plan row has no page link")
            continue
        route = check_wiki_link(
            match.group(1), Path(f"{home.name}:{number}"), owner, repo, routes, errors
        )
        if route is None:
            continue
        key = route.removesuffix("_ja")
        if key in rows:
            errors.append(f"{home.name}:{number}: duplicate plan row for {key}")
        if not DATE.fullmatch(cells[1]):
            errors.append(f"{home.name}:{number}: invalid Date: {cells[1]}")
        rows[key] = cells[1]
    if not rows:
        errors.append(f"{home.name}: no categorized plan rows")
    return rows


def validate(root: Path, repository: str, changed_pages: list[Path]) -> list[str]:
    errors: list[str] = []
    if "/" not in repository:
        return ["repository must be <owner>/<repo>"]
    owner, repo = repository.split("/", 1)
    routes: dict[str, Path] = {}
    for page in root.rglob("*.md"):
        route = public_name(page)
        if route in routes:
            errors.append(
                f"duplicate public route {route}: {routes[route].relative_to(root)} and {page.relative_to(root)}"
            )
        else:
            routes[route] = page
    homes = [root / "Home.md", root / "Home_ja.md"]
    if any(not home.is_file() for home in homes):
        return errors + ["both Home.md and Home_ja.md are required"]
    for page in homes + changed_pages:
        if not page.is_file() or not page.resolve().is_relative_to(root.resolve()):
            errors.append(f"page not found inside wiki: {page}")
            continue
        check_links(root, page, owner, repo, routes, errors)
    english = home_rows(root, homes[0], owner, repo, routes, errors)
    japanese = home_rows(root, homes[1], owner, repo, routes, errors)
    for key in sorted(english.keys() | japanese.keys()):
        if key not in english or key not in japanese:
            errors.append(f"plan {key} is missing from one Home page")
            continue
        if english[key] != japanese[key]:
            errors.append(f"plan {key} has different Home dates: {english[key]} vs {japanese[key]}")
        pair = [routes[name] for name in (key, f"{key}_ja") if name in routes]
        try:
            expected = max(page_date(root, page) for page in pair)
        except ValueError as error:
            errors.append(str(error))
            continue
        if english[key] != expected or japanese[key] != expected:
            errors.append(f"plan {key} Date must be {expected} (latest plan-page update)")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wiki", type=Path, help="local GitHub Wiki checkout")
    parser.add_argument("repository", help="GitHub owner/repo")
    parser.add_argument("--page", action="append", default=[], help="additional edited wiki page")
    args = parser.parse_args()
    root = args.wiki.resolve()
    if not root.is_dir():
        parser.error(f"wiki checkout does not exist: {root}")
    errors = validate(root, args.repository, [root / name for name in args.page])
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Wiki routes, category tables, and plan dates are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
