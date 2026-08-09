from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = Path(__file__).resolve().parents[1]


class ManifestTests(unittest.TestCase):
    def test_plugin_metadata_and_capabilities_are_fixed(self):
        manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual("dependabot-safe-merge", manifest["name"])
        self.assertEqual("0.1.0", manifest["version"])
        self.assertEqual("MIT", manifest["license"])
        self.assertEqual("Team Foundation Users Japan", manifest["author"]["name"])
        self.assertEqual("Developer Tools", manifest["interface"]["category"])
        self.assertEqual(["Interactive", "Write"], manifest["interface"]["capabilities"])

    def test_github_connector_is_required_and_no_mcp_server_exists(self):
        app = json.loads((PLUGIN_ROOT / ".app.json").read_text(encoding="utf-8"))
        github = app["apps"]["github"]
        self.assertRegex(github["id"], r"^connector_[0-9a-f]+$")
        self.assertIs(github["required"], True)
        self.assertFalse((PLUGIN_ROOT / ".mcp.json").exists())
        manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertNotIn("mcpServers", manifest)

    def test_skill_ui_metadata_matches_required_values(self):
        text = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "Dependabot Safe Merge"', text)
        self.assertIn('short_description: "Safely refresh and merge Dependabot PRs"', text)
        self.assertIn('default_prompt: "Use $dependabot-safe-merge to review and safely merge this Dependabot pull request."', text)

    def test_skill_references_resolve_and_documents_contain_no_addresses(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        references = re.findall(r"\[[^]]+\]\((references/[^)]+)\)", skill)
        self.assertTrue(references)
        for reference in references:
            self.assertTrue((SKILL_ROOT / reference).is_file(), reference)
        for document in [SKILL_ROOT / "SKILL.md", *(SKILL_ROOT / "references").glob("*.md")]:
            contents = document.read_text(encoding="utf-8")
            self.assertNotIn("https://", contents)
            self.assertNotIn("http://", contents)


if __name__ == "__main__":
    unittest.main()
