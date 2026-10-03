from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from validate_work_item_links import normalize_page_path, validate  # noqa: E402


ORG_PROJECT = "https://dev.azure.com/example-org/example-project"
PLAN = f"""# Example plan

| Item | Details |
| --- | --- |
| Work Item | #1234 |
| PR | [!322]({ORG_PROJECT}/_git/example-repo/pullrequest/322) |
"""
INDEX = f"""# example-repo: Plans

| Work Item | Page | PR | Status | Summary |
| --- | --- | --- | --- | --- |
| #1234 | [Example plan](/example-repo/plan/1234-example-plan) | [!322]({ORG_PROJECT}/_git/example-repo/pullrequest/322) | Done | Summary |
| #1300 | [Japanese title](/example-repo/plan/1300-%E8%A8%88%E7%94%BB) | Not yet created | Planned | Summary |
"""


def render(name: str) -> str:
    result = (SKILL_ROOT / "templates" / name).read_text(encoding="utf-8")
    for before, after in {
        "<repo>": "example-repo",
        "<org>": "example-org",
        "<project>": "example-project",
        "<plan|bug>": "plan",
        "<id>": "1234",
        "<feature-id>": "1200",
        "<child-id>": "1235",
        "<pr>": "322",
        "<slug>": "example-plan",
    }.items():
        result = result.replace(before, after)
    return result


class ValidateTests(unittest.TestCase):
    def test_accepts_work_item_and_pull_request_link(self) -> None:
        self.assertEqual(validate(PLAN, ["1234"], ["322"]), [])

    def test_rejects_ab_reference_in_prose_but_not_in_code(self) -> None:
        errors = validate("Work Item: AB#1234\n\n`AB#1`\n", [])
        self.assertEqual(len(errors), 1)
        self.assertIn("Line 1", errors[0])

    def test_rejects_missing_pull_request_link(self) -> None:
        errors = validate("Work Item: #1234\nPR: #322\n", ["1234"], ["322"])
        self.assertEqual(errors, ["Wiki Markdown is missing a link to pull request 322."])

    def test_pull_request_id_must_match_exactly(self) -> None:
        markdown = f"[!3221]({ORG_PROJECT}/_git/example-repo/pullrequest/3221)\n"
        self.assertEqual(len(validate(markdown, [], ["322"])), 1)

    def test_accepts_github_pull_request_link(self) -> None:
        markdown = "[example/repo#45](https://github.com/example/repo/pull/45)\n"
        self.assertEqual(validate(markdown, [], ["45"]), [])

    def test_pull_request_link_inside_code_does_not_count(self) -> None:
        markdown = f"`[!322]({ORG_PROJECT}/_git/example-repo/pullrequest/322)`\n"
        self.assertEqual(len(validate(markdown, [], ["322"])), 1)

    def test_index_lists_every_child_page(self) -> None:
        children = ["/example-repo/plan/1234-example-plan", "/example-repo/plan/1300-計画"]
        self.assertEqual(validate(INDEX, ["1234", "1300"], ["322"], children), [])

    def test_index_missing_child_page_fails(self) -> None:
        errors = validate(INDEX, [], [], ["/example-repo/plan/1400-missing"])
        self.assertEqual(errors, ["Wiki Markdown is missing a link to the /example-repo/plan/1400-missing page."])

    def test_wiki_link_syntax_is_not_a_page_link(self) -> None:
        errors = validate("- [[/example-repo/plan]]\n", [], [], ["/example-repo/plan"])
        self.assertEqual(len(errors), 1)

    def test_pull_request_path_is_case_insensitive(self) -> None:
        markdown = f"[!322]({ORG_PROJECT}/_git/example-repo/PullRequest/322)\n"
        self.assertEqual(validate(markdown, [], ["322"]), [])

    def test_angle_bracket_link_target_with_space(self) -> None:
        self.assertEqual(validate("[P](</repo/plan/My Page>)\n", [], [], ["/repo/plan/My-Page"]), [])

    def test_image_is_not_a_page_link(self) -> None:
        self.assertEqual(len(validate("![diagram](/repo/plan)\n", [], [], ["/repo/plan"])), 1)

    def test_normalize_page_path(self) -> None:
        self.assertEqual(normalize_page_path("/repo/plan/My%20Page.md#top"), "/repo/plan/My-Page")
        self.assertEqual(normalize_page_path("/repo/plan/"), "/repo/plan")


class TemplateTests(unittest.TestCase):
    def test_plan_and_bug_templates_contain_required_references(self) -> None:
        for name in ("plan-page.md", "bug-page.md"):
            with self.subTest(name=name):
                self.assertEqual(validate(render(name), ["1234"], ["322"]), [])

    def test_index_template_links_child_and_pull_request(self) -> None:
        markdown = render("index-page.md")
        self.assertEqual(validate(markdown, ["1234"], ["322"], ["/example-repo/plan/1234-example-plan"]), [])

    def test_root_template_links_plan_and_bug_indexes(self) -> None:
        markdown = render("root-page.md")
        self.assertEqual(validate(markdown, [], [], ["/example-repo/plan", "/example-repo/bug"]), [])


@unittest.skipIf(shutil.which("pwsh") is None, "PowerShell 7 is not installed")
class PowerShellParityTests(unittest.TestCase):
    def run_script(self, markdown: str, **arguments: list[str]) -> subprocess.CompletedProcess[str]:
        def quote(value: str) -> str:
            return "'" + value.replace("'", "''") + "'"

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "page.md"
            path.write_bytes(markdown.encode("utf-8"))
            command = "& {} -MarkdownPath {}".format(quote(str(SCRIPTS / "Assert-WikiWorkItemLinks.ps1")), quote(str(path)))
            for name, values in arguments.items():
                command += " -{} @({})".format(name, ",".join(quote(value) for value in values))
            return subprocess.run(
                ["pwsh", "-NoProfile", "-NonInteractive", "-Command",
                 "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); " + command],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )

    def test_index_passes(self) -> None:
        result = self.run_script(
            INDEX, RequireId=["1234"], RequirePr=["322"],
            RequirePageLink=["/example-repo/plan/1234-example-plan", "/example-repo/plan/1300-計画"],
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_pull_request_fails(self) -> None:
        result = self.run_script("Work Item: #1234\nPR: #322\n", RequirePr=["322"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pull request 322", result.stderr + result.stdout)

    def test_matches_python_link_edge_cases(self) -> None:
        markdown = f"[!322]({ORG_PROJECT}/_git/r/PullRequest/322)\n[P](</repo/plan/My Page>)\n"
        result = self.run_script(markdown, RequirePr=["322"], RequirePageLink=["/repo/plan/My-Page"])
        self.assertEqual(result.returncode, 0, result.stderr)
        image = self.run_script("![diagram](/repo/plan)\n", RequirePageLink=["/repo/plan"])
        self.assertNotEqual(image.returncode, 0)

    def test_missing_child_page_fails(self) -> None:
        result = self.run_script(INDEX, RequirePageLink=["/example-repo/plan/1400-missing"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("/example-repo/plan/1400-missing", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
