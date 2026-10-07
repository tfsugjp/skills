from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
LINT = SKILL / "scripts" / "Test-NativeCommand.ps1"
HELPER = SKILL / "scripts" / "Invoke-NativeJson.ps1"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
PWSH = shutil.which("pwsh")


def run_pwsh(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PWSH, "-NoProfile", "-NonInteractive", *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


def lint_file(path: Path) -> tuple[int, list[dict]]:
    result = run_pwsh("-File", str(LINT), "-Path", str(path), "-AsJson")
    findings = json.loads(result.stdout) if result.stdout.strip() else []
    return result.returncode, findings


@unittest.skipUnless(PWSH, "pwsh is required")
class LintFixtureTests(unittest.TestCase):
    def test_unsafe_fixtures_report_their_rule(self) -> None:
        fixtures = sorted((FIXTURES / "unsafe").glob("*.txt"))
        self.assertTrue(fixtures)
        for fixture in fixtures:
            expected = fixture.name.split("-", 1)[0]
            with self.subTest(fixture=fixture.name):
                code, findings = lint_file(fixture)
                self.assertEqual(code, 1)
                self.assertIn(expected, {f["RuleId"] for f in findings})
                for finding in findings:
                    self.assertTrue(finding["Why"])
                    self.assertTrue(finding["Fix"])

    def test_every_rule_has_an_unsafe_fixture(self) -> None:
        covered = {p.name.split("-", 1)[0] for p in (FIXTURES / "unsafe").glob("*.txt")}
        self.assertEqual(covered, {f"WSS{n:03d}" for n in range(1, 10)})

    def test_safe_fixtures_are_clean(self) -> None:
        fixtures = sorted((FIXTURES / "safe").glob("*.txt"))
        self.assertTrue(fixtures)
        for fixture in fixtures:
            with self.subTest(fixture=fixture.name):
                code, findings = lint_file(fixture)
                self.assertEqual(findings, [])
                self.assertEqual(code, 0)


@unittest.skipUnless(PWSH, "pwsh is required")
class LintInputTests(unittest.TestCase):
    def test_command_argument(self) -> None:
        result = run_pwsh("-File", str(LINT), "-Command", 'az version --query "keys(@)|[0]"')
        self.assertEqual(result.returncode, 1)
        self.assertIn("WSS003", result.stdout)
        self.assertIn("fix:", result.stdout)

    def test_pipeline_input(self) -> None:
        script = f"'cmd /c dir', 'Get-Date' | & '{LINT}' -AsJson; exit $LASTEXITCODE"
        result = run_pwsh("-Command", script)
        self.assertEqual(result.returncode, 1)
        self.assertEqual([f["RuleId"] for f in json.loads(result.stdout)], ["WSS001"])

    def test_clean_command_exit_zero(self) -> None:
        result = run_pwsh("-File", str(LINT), "-Command", "az account show -o json")
        self.assertEqual(result.returncode, 0)
        self.assertIn("OK", result.stdout)

    def test_missing_path_exit_two(self) -> None:
        result = run_pwsh("-File", str(LINT), "-Path", str(FIXTURES / "missing.txt"))
        self.assertEqual(result.returncode, 2)


@unittest.skipUnless(PWSH, "pwsh is required")
class HelperTests(unittest.TestCase):
    def run_helper(self, body: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "case.ps1"
            script.write_text(f". '{HELPER}'\n{body}\n", encoding="utf-8")
            return run_pwsh("-File", str(script))

    def test_body_round_trips_through_utf8_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            echo = Path(directory) / "echo.ps1"
            echo.write_text("param($File) Get-Content -Raw -Encoding utf8 -LiteralPath $File", encoding="utf-8")
            result = self.run_helper(
                f"$r = Invoke-NativeJson -FilePath pwsh -Arguments '-NoProfile', '-File', '{echo}' "
                "-Body @{ name = 'テスト'; q = 'a|b\"c&d' } -BodyParameter '' -BodyValueFormat '{0}'\n"
                "$r | ConvertTo-Json -Compress"
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"name": "テスト", "q": 'a|b"c&d'})

    def test_batch_target_refuses_cmd_metacharacters(self) -> None:
        result = self.run_helper(
            "try { Invoke-NativeJson -FilePath pwsh -Arguments '-c', 'a|b' -AssumeBatch; 'ran' }\n"
            "catch { 'refused: ' + $_.Exception.Message }"
        )
        self.assertIn("refused: Argument 'a|b'", result.stdout)

    def test_non_zero_exit_throws_with_stderr(self) -> None:
        result = self.run_helper(
            "try { Invoke-NativeJson -FilePath pwsh -Arguments '-NoProfile', '-c', "
            "'[Console]::Error.WriteLine(\"boom\"); exit 3' }\n"
            "catch { $_.Exception.Message }"
        )
        self.assertIn("exited with 3", result.stdout)
        self.assertIn("boom", result.stdout)

    def test_show_native_args_prints_received_argv(self) -> None:
        result = self.run_helper("Show-NativeArgs 'x y' 'plain'")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["[x", "y]", "[plain]"])


if __name__ == "__main__":
    unittest.main()
