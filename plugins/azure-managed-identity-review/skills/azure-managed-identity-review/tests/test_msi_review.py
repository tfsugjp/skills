from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SKILL / "scripts"))

import msi_review  # noqa: E402

SUBSCRIPTION = "00000000-0000-0000-0000-000000000000"
HAS_BICEP = bool(shutil.which("bicep"))


def review(*args: str) -> tuple[int, dict]:
    stdout = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
        code = msi_review.main([*args, "--json"])
    return code, json.loads(stdout.getvalue())


def rules(data: dict, severity: str | None = None) -> set[str]:
    return {f["rule"] for f in data["findings"] if severity is None or f["severity"] == severity}


def findings(data: dict, rule: str) -> list[dict]:
    return [f for f in data["findings"] if f["rule"] == rule]


class CanonicalScenarioTests(unittest.TestCase):
    """Storage CMK identity reused by a Function App for Service Bus and trusted by GitHub Actions."""

    def assert_canonical(self, data: dict) -> None:
        self.assertTrue({"MIR001", "MIR002", "MIR003", "MIR004"} <= rules(data))
        missing = findings(data, "MIR002")
        self.assertEqual(len(missing), 1)
        self.assertEqual((missing[0]["resource"], missing[0]["severity"]), ("func-orders", "error"))
        self.assertIn("Service Bus sb-orders", missing[0]["message"])
        shared = findings(data, "MIR001")[0]["message"]
        self.assertIn("func-orders", shared)
        self.assertIn("stshared001", shared)
        self.assertIn("github-main", findings(data, "MIR004")[0]["message"])

    def test_compiled_arm(self) -> None:
        code, data = review("static", str(FIXTURES / "arm-canonical"))
        self.assertEqual(code, 1)
        self.assert_canonical(data)
        grants = {(g["role"], g["scope_name"]) for g in data["grants"]}
        self.assertIn(("Key Vault Crypto Service Encryption User", "kv-shared-001"), grants)
        self.assertIn(("Storage Blob Data Owner", "stshared001"), grants)

    def test_terraform(self) -> None:
        code, data = review("static", str(FIXTURES / "terraform-canonical"))
        self.assertEqual(code, 1)
        self.assert_canonical(data)
        broad = [f for f in findings(data, "MIR003") if "resourceGroup rg-orders" in f["message"]]
        self.assertEqual(len(broad), 1)

    @unittest.skipUnless(HAS_BICEP, "the standalone Bicep CLI is required")
    def test_bicep_with_code(self) -> None:
        code, data = review("static", str(FIXTURES / "canonical"))
        self.assertEqual(code, 1)
        self.assert_canonical(data)
        self.assertIn("MIR007", rules(data))
        # DefaultAzureCredential in the Function App has no AZURE_CLIENT_ID and no system-assigned identity.
        selection = findings(data, "MIR005")
        self.assertTrue(any(f["resource"] == "func-orders" and "OrderPublisher.cs" in f["message"] for f in selection))

    def test_resource_filter_includes_other_consumers(self) -> None:
        _, data = review("static", str(FIXTURES / "terraform-canonical"), "--resource", "stshared001")
        self.assertEqual({i["key"] for i in data["identities"] if i["kind"] == "user"}, {"id-shared"})
        self.assertTrue(any(f["resource"] == "func-orders" for f in findings(data, "MIR002")))


class RuleTests(unittest.TestCase):
    def test_identity_selection_and_non_rbac(self) -> None:
        code, data = review("static", str(FIXTURES / "terraform-identity-selection"))
        self.assertEqual(code, 1)
        errors = {(f["resource"], f["severity"]) for f in findings(data, "MIR005")}
        self.assertIn(("app-api", "error"), errors)
        self.assertIn(("func-batch", "warning"), errors)
        self.assertTrue(any("Key Vault reference" in f["message"] for f in findings(data, "MIR005")))
        non_rbac = findings(data, "MIR006")
        self.assertTrue(any(f["resource"] == "func-batch" and "Azure SQL sql-batch" in f["message"] for f in non_rbac))
        # Cosmos DB data-plane role assignment covers func-batch's Cosmos endpoint.
        self.assertFalse(any("Cosmos" in f["message"] and f["resource"] == "func-batch" for f in non_rbac + findings(data, "MIR002")))
        self.assertTrue(any("api://partner-exchange" in f["message"] for f in findings(data, "MIR004")))
        # A custom setting holding the attached identity's client ID selects that identity.
        self.assertFalse([f for f in data["findings"] if f["resource"] == "app-custom-client"])
        custom = [t for t in data["targets"] if t["resource"] == "app-custom-client"]
        self.assertEqual([(t["identity"], t["target_name"]) for t in custom], [("id-app", "streports001")])
        self.assertIn("REPORTS_MANAGED_IDENTITY_CLIENT_ID", custom[0]["via"])

    def test_clean_configuration(self) -> None:
        code, data = review("static", str(FIXTURES / "clean"))
        self.assertEqual(code, 0)
        self.assertEqual(data["findings"], [])
        self.assertEqual({t["resource"] for t in data["targets"]}, {"stclean001", "func-clean", "app-clean"})

    def test_unresolved_reference_is_a_note(self) -> None:
        code, data = review("static", str(FIXTURES / "terraform-unresolved"))
        self.assertEqual(code, 0)
        self.assertEqual(rules(data), {"MIR000"})
        self.assertIn("var.identity_id", data["findings"][0]["message"])

    def test_terraform_plan_json(self) -> None:
        _, data = review("static", str(FIXTURES / "terraform-unresolved"), "--tf-plan-json", str(FIXTURES / "terraform-plan" / "plan.json"))
        self.assertTrue(any(f["resource"] == "func-orders" and "Service Bus" in f["message"] for f in findings(data, "MIR002")))
        self.assertTrue(any("Reader at subscription" in f["message"] for f in findings(data, "MIR003")))

    def test_drift_and_live_replay(self) -> None:
        code, data = review("live", "--subscription", SUBSCRIPTION, "--replay", str(FIXTURES / "live-replay"),
                            "--static", str(FIXTURES / "arm-canonical"))
        self.assertEqual(code, 1)
        drift = [f["message"] for f in findings(data, "MIR008")]
        self.assertTrue(any("ca-reports holds id-shared in Azure but not in IaC" in m for m in drift))
        self.assertTrue(any("contributor on rg-orders" in m for m in drift))
        self.assertEqual(len(drift), 2)
        self.assertTrue(any(f["resource"] == "func-orders" and f["severity"] == "error" for f in findings(data, "MIR002")))
        self.assertTrue(any(f["resource"] == "ca-reports" and f["severity"] == "warning" for f in findings(data, "MIR002")))

    def test_subscription_scope_template_and_literal_ids(self) -> None:
        code, data = review("static", str(FIXTURES / "arm-subscription"))
        self.assertEqual(code, 1)
        self.assertIn("app-one", findings(data, "MIR001")[0]["message"])
        self.assertIn("app-two", findings(data, "MIR001")[0]["message"])  # literal resource ID key
        self.assertTrue(any("Contributor at subscription" in f["message"] for f in findings(data, "MIR003")))
        self.assertTrue(any(f["resource"] == "app-two" and f["severity"] == "warning" and "cannot be matched" in f["message"]
                            for f in findings(data, "MIR005")))

    def test_grants_on_the_wrong_resource(self) -> None:
        code, data = review("static", str(FIXTURES / "terraform-regressions"))
        self.assertEqual(code, 1)
        errors = {(f["resource"], f["message"].split(" with ")[0]) for f in findings(data, "MIR002") if f["severity"] == "error"}
        self.assertIn(("web-a", "web-a reaches Key Vault secrets kv-web"), errors)
        self.assertIn(("ca-api", "ca-api reaches Container Registry acrone"), errors)
        self.assertIn(("func-events", "func-events reaches Event Hubs eh-ns"), errors)
        child = [f for f in findings(data, "MIR002") if f["severity"] == "warning" and f["resource"] == "func-events"]
        self.assertTrue(child and "stdata001/reports" in child[0]["message"])
        self.assertTrue(any("merge(" in f["message"] for f in findings(data, "MIR000")))
        # The same container grant counts when the endpoint points into that container.
        self.assertFalse([f for f in findings(data, "MIR002") if f["resource"] == "app-reports"])

    def test_resource_filter_with_system_assigned_only(self) -> None:
        _, data = review("static", str(FIXTURES / "terraform-regressions"), "--resource", "func-sys")
        self.assertEqual([(f["rule"], f["resource"]) for f in data["findings"]], [("MIR002", "func-sys")])

    def test_identity_by_resource_id(self) -> None:
        resource_id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-orders/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-shared"
        code, data = review("static", str(FIXTURES / "terraform-canonical"), "--identity", resource_id)
        self.assertEqual(code, 1)
        self.assertEqual({i["key"] for i in data["identities"] if i["kind"] == "user"}, {"id-shared"})

    def test_invalid_map_is_an_input_error(self) -> None:
        for value in ("src/OrdersFunc", "src/OrdersFunc=nope"):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = msi_review.main(["static", str(FIXTURES / "arm-canonical"), "--map", value])
            self.assertEqual(code, 2, value)

    def test_review_scoping_and_key_vault_purposes(self) -> None:
        _, data = review("static", str(FIXTURES / "terraform-review"))
        users = {i["key"] for i in data["identities"] if i["kind"] == "user"}
        self.assertTrue({"rg-a/id-dup", "rg-b/id-dup", "id-lit"} <= users)  # same names in different groups stay apart
        missing = {(f["resource"], f["identity"]) for f in findings(data, "MIR002")}
        self.assertIn(("func-b", "rg-b/id-dup"), missing)  # rg-a's grant does not cover rg-b's identity
        self.assertIn(("stcmk001", "id-kv"), missing)  # Secrets User does not wrap keys
        self.assertIn(("app-lit", "id-lit"), missing)  # literal ID attached; grants in other groups do not cover
        messages = " ".join(f["message"] for f in findings(data, "MIR002") if f["resource"] == "app-lit")
        self.assertIn("Queue Storage stb001", messages)  # resource-group grant on rg-other
        self.assertIn("Table Storage stsame001", messages)  # same name in rg-x
        self.assertTrue(any(f["resource"] == "app-lit" for f in findings(data, "MIR005")))  # client ID of an unattached identity
        self.assertTrue(any("var.scope" in f["message"] for f in findings(data, "MIR000")))

    def test_client_id_chosen_in_code(self) -> None:
        _, data = review("static", str(FIXTURES / "code-client-id"), "--map", "src/app=app-code")
        queue = [t for t in data["targets"] if t["service"] == "storage-queue"]
        self.assertEqual([t["identity"] for t in queue], ["id-orders"])
        self.assertFalse(findings(data, "MIR002"))
        self.assertTrue(any("AUDIT_CLIENT_ID" in f["message"] for f in findings(data, "MIR005")))

    def test_all_flag(self) -> None:
        code, data = review("static", str(FIXTURES / "terraform-canonical"), "--all")
        self.assertEqual(code, 1)
        self.assertTrue(findings(data, "MIR001"))
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(msi_review.main(["static", str(FIXTURES / "terraform-canonical"), "--all", "--resource", "func-orders"]), 2)

    def test_drift_compares_child_scopes(self) -> None:
        static = msi_review.Model(origin="static")
        live = msi_review.Model(origin="live")
        for model in (static, live):
            model.add_identity(msi_review.Identity(key="id-x", kind="user", name="id-x", source="t"))
        static.grants.append(msi_review.Grant("id-x", "Storage Blob Data Contributor", "resource", "stdata", "t", scope_path="stdata/reports"))
        live.grants.append(msi_review.Grant("id-x", "Storage Blob Data Contributor", "resource", "stdata", "t", scope_path="stdata/invoices"))
        messages = [f.message for f in msi_review.drift(static, live)]
        self.assertTrue(any("stdata/invoices" in m for m in messages), messages)

    def test_every_service_role_has_a_verified_id(self) -> None:
        names = set(msi_review.ROLE_IDS.values())
        missing = sorted({r for _, roles, _ in msi_review.SERVICES.values() for r in roles if r != "*" and r not in names})
        self.assertEqual(missing, [])

    def test_every_rule_has_a_positive_fixture(self) -> None:
        seen: set[str] = set()
        for args in (["static", str(FIXTURES / "arm-canonical")], ["static", str(FIXTURES / "terraform-identity-selection")],
                     ["static", str(FIXTURES / "terraform-unresolved")],
                     ["live", "--subscription", SUBSCRIPTION, "--replay", str(FIXTURES / "live-replay"), "--static", str(FIXTURES / "arm-canonical")]):
            seen |= rules(review(*args)[1])
        if HAS_BICEP:
            seen |= rules(review("static", str(FIXTURES / "canonical"))[1])
        expected = {f"MIR00{i}" for i in range(0, 9)} - (set() if HAS_BICEP else {"MIR007"})
        self.assertTrue(expected <= seen, expected - seen)


class ParserTests(unittest.TestCase):
    def ctx(self) -> msi_review.ArmContext:
        return msi_review.ArmContext({"name": "id-x", "free": msi_review.Unknown("param:free")}, {"v": "[parameters('name')]"}, {}, "t")

    def test_arm_expressions(self) -> None:
        ctx = self.ctx()
        ref = ctx.value("[format('{0}', resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', variables('v')))]")
        self.assertTrue(msi_review.is_uami(ref))
        self.assertEqual(ref.name, "id-x")
        prop = ctx.value("[reference(resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', parameters('name')), '2023-01-31').principalId]")
        self.assertEqual((prop.ref.name, prop.path), ("id-x", ["principalId"]))
        partial = ctx.value("[format('https://{0}.blob.{1}', parameters('free'), environment().suffixes.storage)]")
        self.assertIsInstance(partial, msi_review.Partial)
        self.assertEqual(msi_review.service_from_text(partial), "storage-blob")
        self.assertEqual(ctx.value("[[literal]"), "[literal]")

    def test_hcl_parser(self) -> None:
        text = '''
        # comment { not a block
        resource "azurerm_linux_web_app" "a" {
          name = "app-a" // trailing
          app_settings = {
            "K1" = "v1"
            K2   = azurerm_user_assigned_identity.x.client_id
          }
          note = <<-EOT
            { unbalanced
          EOT
          identity {
            identity_ids = [azurerm_user_assigned_identity.x.id, var.other]
          }
        }
        '''
        _, blocks = msi_review.HclParser(text).parse_body()
        self.assertEqual(len(blocks), 1)
        block = blocks[0]
        self.assertEqual(block.labels, ["azurerm_linux_web_app", "a"])
        self.assertEqual(msi_review.hcl_map(block.attrs["app_settings"]), {"K1": '"v1"', "K2": "azurerm_user_assigned_identity.x.client_id"})
        self.assertEqual(msi_review.hcl_list(block.blocks[0].attrs["identity_ids"]), ["azurerm_user_assigned_identity.x.id", "var.other"])

    def test_masking(self) -> None:
        mask = msi_review.mask_value
        self.assertEqual(mask("PartnerApiKey", "abc123"), "***")
        self.assertEqual(mask("Storage", "DefaultEndpointsProtocol=https;AccountName=x;AccountKey=secret"), "***")
        self.assertEqual(mask("Bus__fullyQualifiedNamespace", "sb.servicebus.windows.net"), "sb.servicebus.windows.net")
        self.assertEqual(mask("Bus__clientId", "22222222-2222-2222-2222-222222222222"), "22222222-2222-2222-2222-222222222222")
        self.assertEqual(mask("Blob", "https://st.blob.core.windows.net/c/file?sv=1&sig=abc"), "***")
        self.assertEqual(mask("Blob", "https://st.blob.core.windows.net/c/file?comp=list"), "https://st.blob.core.windows.net/c/file")
        self.assertEqual(mask("Db", "@Microsoft.KeyVault(VaultName=kv1;SecretName=db)"), "@Microsoft.KeyVault(VaultName=kv1)")
        rows = msi_review.mask_graph({"data": [{"containers": [{"env": [{"name": "TOKEN", "value": "x"}, {"name": "S", "secretRef": "s"}]}]}]})
        self.assertEqual(rows["data"][0]["containers"][0]["env"], [{"name": "TOKEN", "value": "***"}, {"name": "S", "secretRef": "s", "value": None}])


class CliTests(unittest.TestCase):
    def test_markdown_and_exit_codes(self) -> None:
        script = SKILL / "scripts" / "msi_review.py"
        result = subprocess.run([sys.executable, str(script), "static", str(FIXTURES / "terraform-canonical")],
                                capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(result.returncode, 1)
        self.assertIn("## Identity `id-shared`", result.stdout)
        self.assertIn("| Grant | Scope | Needed by |", result.stdout)
        missing = subprocess.run([sys.executable, str(script), "static", str(FIXTURES / "does-not-exist")],
                                 capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()
