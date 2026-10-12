#!/usr/bin/env python3
"""Behavioral checks for PR closing-target validation."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/validate_closing_keywords.py"
spec = importlib.util.spec_from_file_location("closing_keywords", SCRIPT)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class ClosingKeywordsTests(unittest.TestCase):
    def check(self, body, bugs=(), closes=(), reference_only=False):
        return validator.validate(body, "team/repo", bugs, closes, reference_only)

    def test_multiple_bugs_and_other_work(self):
        body = "## Related issues\nFixed #10\n- Fixed #11\nClose #20\nRefs #30\n"
        self.assertEqual([], self.check(body, bugs=["10", "11"], closes=["20"]))

    def test_cross_repository_identity_and_case(self):
        body = "Fixed OTHER/Repo#10\nClose #10\n"
        self.assertEqual([], self.check(body, bugs=["other/repo#10"], closes=["10"]))
        self.assertTrue(self.check("Fixed #10", bugs=["other/repo#10"]))

    def test_grouped_references_fail_even_with_repeated_keyword(self):
        for body in ("Fixed #10, #11", "Close #10, #11", "Close #10, Close #11"):
            with self.subTest(body=body):
                self.assertTrue(self.check(body, closes=["10", "11"]))

    def test_reference_is_not_closure(self):
        for body in ("Refs #10", "Related: #10", "Fixed #11"):
            with self.subTest(body=body):
                self.assertTrue(self.check(body, bugs=["10"]))

    def test_wrong_work_type_fails(self):
        self.assertTrue(self.check("Close #10", bugs=["10"]))
        self.assertTrue(self.check("Fixed #10", closes=["10"]))
        self.assertTrue(self.check("Fixes #10", bugs=["10"]))

    def test_unfinished_parent_cannot_be_closed(self):
        self.assertEqual([], self.check("Fixed #10\nRefs #9", bugs=["10"]))
        self.assertTrue(self.check("Fixed #10\nClose #9", bugs=["10"]))
        self.assertTrue(self.check("Fixed #10\nAlso resolves #9", bugs=["10"]))

    def test_hidden_entries_do_not_count(self):
        for body in (
            "<!-- Fixed #10 -->", "<!--\nFixed #10\n-->",
            "```text\nFixed #10\n```", "~~~\nFixed #10\n~~~",
            "`Fixed #10`", "``Fixed #10``", "`example\nFixed #10\nend`",
            "> Fixed #10", "    Fixed #10", "\tFixed #10",
            "- ```\n  Fixed #10\n  ```", "<pre>\nFixed #10\n</pre>",
        ):
            with self.subTest(body=body):
                self.assertTrue(self.check(body, bugs=["10"]))

    def test_template_examples_do_not_close_unplanned_issues(self):
        body = "<!-- Fixed #90 -->\n```\nClose #91\n```\n`Close #92`\nFixed #10"
        self.assertEqual([], self.check(body, bugs=["10"]))

    def test_escaped_or_unmatched_ticks_do_not_hide_entries(self):
        for body in ("\\`\n\nFixed #10\n`", "Unmatched `tick\n\nFixed #10"):
            self.assertEqual([], self.check(body, bugs=["10"]))

    def test_indented_text_inside_list_item_is_visible(self):
        self.assertEqual([], self.check("- Related:\n    Close #10", closes=["10"]))
        self.assertEqual([], self.check("1. Related:\n   Close #10", closes=["10"]))
        self.assertTrue(self.check("- Related:\n    Close #10", closes=["11"]))
        self.assertTrue(self.check("- Related:\n    Close #10", reference_only=True))

    def test_code_block_inside_list_item_stays_hidden(self):
        self.assertTrue(self.check("- Related:\n\n      Close #10", closes=["10"]))
        self.assertTrue(self.check("Text\n\n    Close #10", closes=["10"]))
        self.assertTrue(self.check("- item\n\ntext\n\n    Close #10", closes=["10"]))

    def test_commit_message_closing_keywords_are_checked(self):
        body = "Fixed #10\nRefs #30\n"
        ok = "feat: x\n\nFixes #10\nRefs #30"
        self.assertEqual([], validator.validate(body, "team/repo", ["10"], (), False, ok))
        for message in ("Fixes #30", "closes: team/repo#30", "Resolved #30"):
            with self.subTest(message=message):
                self.assertTrue(validator.validate(body, "team/repo", ["10"], (), False, message))
        self.assertTrue(validator.validate("Refs #30", "team/repo", (), (), True, "Fixes #30"))

    def test_duplicate_closure_is_rejected(self):
        self.assertTrue(self.check("Fixed #10\nFixed TEAM/REPO#10", bugs=["10"]))

    def test_reference_only_requires_no_closing_entries(self):
        self.assertEqual([], self.check("Refs #10", reference_only=True))
        for body in ("Fixed #10", "Close #10", "Closes: #10"):
            self.assertTrue(self.check(body, reference_only=True))

    def test_explicit_scope_required(self):
        for kwargs in ({}, {"bugs": ["10"], "reference_only": True}, {"bugs": ["10"], "closes": ["10"]}):
            with self.assertRaises(ValueError):
                self.check("Fixed #10", **kwargs)

    def test_invalid_inputs(self):
        for issue in ("0", "-10", "10,11", "#10suffix", "owner/repo#0"):
            with self.assertRaises(ValueError):
                self.check("Fixed #10", bugs=[issue])
        for body in ("", "\ufeffFixed #10", "Fixed #10\x00"):
            self.assertTrue(self.check(body, bugs=["10"]))

    def test_actual_cli_exit_status(self):
        with tempfile.TemporaryDirectory() as temp:
            body_file = Path(temp) / "pr.md"
            command = [sys.executable, str(SCRIPT), str(body_file), "--repo", "team/repo", "--bug", "10", "--bug", "11"]
            for body, expected in (("Fixed #10\nFixed #11\n", 0), ("Fixed #10, #11\n", 1)):
                body_file.write_text(body, encoding="utf-8")
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(expected, result.returncode, result.stderr)
            body_file.write_bytes(b"\xff")
            self.assertNotEqual(0, subprocess.run(command, capture_output=True).returncode)


if __name__ == "__main__":
    unittest.main()
