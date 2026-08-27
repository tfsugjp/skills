from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import urlparse


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "templates"
MARKDOWN_LINK = re.compile(r"\[[^]]*\]\(([^)]+)\)")


def render_template(name: str) -> str:
    replacements = {
        "<yyyy-MM-dd>": "2026-08-27",
        "<slug>": "example-plan",
        "<n>": "40",
        "<owner>": "example-owner",
        "<repo>": "example-repo",
    }
    content = (TEMPLATE_ROOT / name).read_text(encoding="utf-8")
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def internal_targets(name: str) -> set[str]:
    targets: set[str] = set()
    for target in MARKDOWN_LINK.findall(render_template(name)):
        parsed = urlparse(target)
        if not parsed.scheme and not target.startswith("#"):
            targets.add(target.split("#", 1)[0])
    return targets


class WikiLinkTests(unittest.TestCase):
    def setUp(self) -> None:
        source_pages = {
            Path("Home.md"),
            Path("Home_ja.md"),
            Path("plan/2026-08-27/example-plan.md"),
            Path("plan/2026-08-27/example-plan_ja.md"),
        }
        self.public_routes = {path.stem for path in source_pages}

    def assert_resolves_to_public_route(self, targets: set[str]) -> None:
        for target in targets:
            with self.subTest(target=target):
                self.assertNotIn("/", target)
                self.assertFalse(target.endswith(".md"))
                self.assertIn(target, self.public_routes)

    def test_home_templates_use_flattened_public_routes(self) -> None:
        english_targets = internal_targets("home.md")
        japanese_targets = internal_targets("home_ja.md")
        self.assertEqual({"Home_ja", "example-plan", "example-plan_ja"}, english_targets)
        self.assertEqual({"Home", "example-plan", "example-plan_ja"}, japanese_targets)
        self.assert_resolves_to_public_route(english_targets)
        self.assert_resolves_to_public_route(japanese_targets)

    def test_plan_template_language_link_uses_flattened_public_route(self) -> None:
        targets = internal_targets("plan-page.md")
        self.assertEqual({"example-plan_ja"}, targets)
        self.assert_resolves_to_public_route(targets)

    def test_nested_git_path_is_not_a_public_route(self) -> None:
        self.assertNotIn("plan/2026-08-27/example-plan", self.public_routes)

    def test_reusing_a_basename_creates_a_public_route_collision(self) -> None:
        source_pages = {
            Path("plan/2026-08-27/example-plan.md"),
            Path("plan/2026-08-28/example-plan.md"),
        }
        routes = [path.stem for path in source_pages]
        self.assertNotEqual(len(routes), len(set(routes)))


if __name__ == "__main__":
    unittest.main()
