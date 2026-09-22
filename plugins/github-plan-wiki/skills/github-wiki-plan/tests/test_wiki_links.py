from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
from validate_wiki import JST, validate  # noqa: E402


REPO = "example-owner/example-repo"
BASE = f"https://github.com/{REPO}/wiki/"
LINK = re.compile(r"\[[^]]*\]\(([^)]+)\)")


def render(name: str) -> str:
    result = (SKILL_ROOT / "templates" / name).read_text(encoding="utf-8")
    for before, after in {
        "<owner>": "example-owner",
        "<repo>": "example-repo",
        "<slug>": "example-plan",
        "<n>": "40",
        "<yyyy-MM-dd>": "2026-08-27",
    }.items():
        result = result.replace(before, after)
    return result


class WikiTemplateTests(unittest.TestCase):
    def test_templates_use_absolute_flat_wiki_routes(self) -> None:
        expected = {
            "home.md": {BASE + "Home_ja", BASE + "example-plan", BASE + "example-plan_ja"},
            "home_ja.md": {BASE + "Home", BASE + "example-plan", BASE + "example-plan_ja"},
            "plan-page.md": {BASE + "example-plan_ja"},
        }
        for name, targets in expected.items():
            links = LINK.findall(render(name))
            self.assertEqual(targets, {link for link in links if link.startswith(BASE)})
            self.assertTrue(all(link.startswith("https://github.com/") for link in links))


class WikiPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.plan = self.root / "plan" / "2026-08-27"
        self.plan.mkdir(parents=True)
        (self.plan / "example-plan.md").write_text(
            f"# Plan\n\n[日本語]({BASE}example-plan_ja)\n", encoding="utf-8"
        )
        (self.plan / "example-plan_ja.md").write_text(
            f"# 計画\n\n[English]({BASE}example-plan)\n", encoding="utf-8"
        )
        env = os.environ.copy()
        env.update(
            GIT_AUTHOR_DATE="2026-08-26T18:00:00+00:00",
            GIT_COMMITTER_DATE="2026-08-26T18:00:00+00:00",
            GIT_AUTHOR_NAME="Wiki Test",
            GIT_COMMITTER_NAME="Wiki Test",
            GIT_AUTHOR_EMAIL="test@example.invalid",
            GIT_COMMITTER_EMAIL="test@example.invalid",
        )
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True, env=env)
        subprocess.run(
            ["git", "-C", str(self.root), "commit", "-qm", "fixture"], check=True, env=env
        )
        self.english = self.root / "Home.md"
        self.japanese = self.root / "Home_ja.md"
        self.english.write_text(
            f"# Wiki\n\n[日本語]({BASE}Home_ja)\n\n## setup\n\n"
            "| Plan | Date | Tracking | 日本語 |\n|---|---|---|---|\n"
            f"| [Plan]({BASE}example-plan) | 2026-08-27 | "
            f"[Issue](https://github.com/{REPO}/issues/40) | "
            f"[日本語]({BASE}example-plan_ja) |\n",
            encoding="utf-8",
        )
        self.japanese.write_text(
            f"# Wiki\n\n[English]({BASE}Home)\n\n## セットアップ\n\n"
            "| 計画 | 日付 | 追跡 | English |\n|---|---|---|---|\n"
            f"| [計画]({BASE}example-plan_ja) | 2026-08-27 | "
            f"[Issue](https://github.com/{REPO}/issues/40) | "
            f"[English]({BASE}example-plan) |\n",
            encoding="utf-8",
        )

    def errors(self) -> list[str]:
        return validate(self.root, REPO, [self.plan / "example-plan.md"])

    @staticmethod
    def replace(path: Path, old: str, new: str) -> None:
        path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

    def test_nested_files_have_flat_public_routes(self) -> None:
        self.assertEqual([], self.errors())

    def test_nested_url_is_rejected(self) -> None:
        self.replace(self.english, BASE + "example-plan)", BASE + "plan/2026-08-27/example-plan)")
        self.assertTrue(any("noncanonical wiki route" in error for error in self.errors()))

    def test_md_url_is_rejected(self) -> None:
        self.replace(self.english, BASE + "example-plan)", BASE + "example-plan.md)")
        self.assertTrue(any("noncanonical wiki route" in error for error in self.errors()))

    def test_missing_page_is_rejected(self) -> None:
        self.replace(self.english, BASE + "example-plan)", BASE + "missing-plan)")
        self.assertTrue(any("missing wiki page" in error for error in self.errors()))

    def test_relative_link_is_rejected(self) -> None:
        self.replace(self.english, BASE + "example-plan)", "example-plan)")
        self.assertTrue(any("relative wiki link" in error for error in self.errors()))

    def test_duplicate_route_is_rejected(self) -> None:
        other = self.root / "another"
        other.mkdir()
        (other / "example-plan.md").write_text("# Duplicate\n", encoding="utf-8")
        self.assertTrue(any("duplicate public route" in error for error in self.errors()))

    def test_home_dates_must_match(self) -> None:
        self.replace(self.japanese, "2026-08-27", "2026-08-28")
        self.assertTrue(any("different Home dates" in error for error in self.errors()))

    def test_date_follows_latest_plan_update(self) -> None:
        self.replace(self.plan / "example-plan_ja.md", "# 計画", "# 更新した計画")
        today = datetime.now(JST).date().isoformat()
        self.assertTrue(any(f"Date must be {today}" in error for error in self.errors()))
        for home in (self.english, self.japanese):
            self.replace(home, "2026-08-27", today)
        self.assertEqual([], self.errors())

    def test_date_uses_later_committed_translation(self) -> None:
        japanese_plan = self.plan / "example-plan_ja.md"
        self.replace(japanese_plan, "# 計画", "# 更新した計画")
        env = os.environ.copy()
        env.update(
            GIT_AUTHOR_DATE="2026-08-28T18:00:00+00:00",
            GIT_COMMITTER_DATE="2026-08-28T18:00:00+00:00",
            GIT_AUTHOR_NAME="Wiki Test",
            GIT_COMMITTER_NAME="Wiki Test",
            GIT_AUTHOR_EMAIL="test@example.invalid",
            GIT_COMMITTER_EMAIL="test@example.invalid",
        )
        subprocess.run(
            ["git", "-C", str(self.root), "add", "--", str(japanese_plan)], check=True, env=env
        )
        subprocess.run(
            ["git", "-C", str(self.root), "commit", "-qm", "translation update"],
            check=True,
            env=env,
        )
        self.assertTrue(any("Date must be 2026-08-29" in error for error in self.errors()))
        for home in (self.english, self.japanese):
            self.replace(home, "2026-08-27", "2026-08-29")
        self.assertEqual([], self.errors())

    def test_plan_rows_require_category(self) -> None:
        self.replace(self.english, "## setup\n\n", "")
        self.assertTrue(any("no H2 category" in error for error in self.errors()))


if __name__ == "__main__":
    unittest.main()
