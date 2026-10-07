from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from test_msi_review import findings, msi_review, review


class StaticRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def write(self, name: str, text: str) -> None:
        (self.root / name).write_text(text, encoding="utf-8")

    def test_inline_settings_preserve_all_connection_properties(self) -> None:
        config = '''resource "azurerm_user_assigned_identity" "app" {
  name = "id-app"
}
resource "azurerm_linux_function_app" "app" {
  name = "app-test"
  identity {
    type = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }
  app_settings = { Bus__credential = "managedidentity", Bus__fullyQualifiedNamespace = "missing.servicebus.windows.net", Bus__clientId = azurerm_user_assigned_identity.app.client_id }
}
'''
        self.write("main.tf", config)
        inline_code, inline = review("static", str(self.root))
        self.write("main.tf", config.replace(", Bus__", "\nBus__"))
        multiline_code, multiline = review("static", str(self.root))
        self.assertEqual((inline_code, multiline_code), (1, 1))
        self.assertEqual(inline["targets"], multiline["targets"])
        self.assertEqual(inline["findings"], multiline["findings"])
        self.assertEqual([(f["rule"], f["identity"], f["severity"]) for f in inline["findings"]],
                         [("MIR002", "id-app", "error")])

    def test_conditional_identity_uses_false_branch(self) -> None:
        identity = "resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', '{name}')"
        a, b = (identity.format(name=name) for name in ("id-a", "id-b"))
        selected = f"[if(parameters('useA'), {a}, {b})]"
        client = f"[if(parameters('useA'), reference({a}, '2023-01-31').clientId, reference({b}, '2023-01-31').clientId)]"
        template = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "parameters": {"useA": {"type": "bool", "defaultValue": False}},
            "resources": [
                {"type": "Microsoft.ManagedIdentity/userAssignedIdentities", "name": "id-a"},
                {"type": "Microsoft.ManagedIdentity/userAssignedIdentities", "name": "id-b"},
                {"type": "Microsoft.Web/sites", "name": "app-test",
                 "identity": {"type": "UserAssigned", "userAssignedIdentities": {selected: {}}},
                 "properties": {"siteConfig": {"appSettings": [
                     {"name": "Bus__fullyQualifiedNamespace", "value": "busone.servicebus.windows.net"},
                     {"name": "Bus__credential", "value": "managedidentity"},
                     {"name": "Bus__clientId", "value": client}]}}},
                {"type": "Microsoft.Authorization/roleAssignments", "name": "grant-a",
                 "scope": "/subscriptions/s/resourceGroups/rg/providers/Microsoft.ServiceBus/namespaces/busone",
                 "properties": {"principalId": f"[reference({a}, '2023-01-31').principalId]",
                                "roleDefinitionId": "4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0"}},
            ],
        }
        self.write("main.json", json.dumps(template))
        code, data = review("static", str(self.root))
        self.assertEqual(code, 1)
        self.assertEqual(data["targets"][0]["identity"], "id-b")
        self.assertEqual(findings(data, "MIR002")[0]["identity"], "id-b")
        template["parameters"]["useA"]["defaultValue"] = True
        self.write("main.json", json.dumps(template))
        code, data = review("static", str(self.root))
        self.assertEqual(code, 0)
        self.assertEqual(data["targets"][0]["identity"], "id-a")
        self.assertEqual(data["findings"], [])

    def test_connections_without_any_identity_report_selection_error(self) -> None:
        for settings in (
            'Bus__fullyQualifiedNamespace = "missing.servicebus.windows.net"\nBus__credential = "managedidentity"',
            'ApiKey = "@Microsoft.KeyVault(VaultName=kv-app;SecretName=api)"',
        ):
            with self.subTest(settings=settings):
                self.write("main.tf", 'resource "azurerm_linux_function_app" "app" {\n'
                           'name = "app-test"\napp_settings = {\n' + settings + '\n}\n}')
                code, data = review("static", str(self.root))
                self.assertEqual(code, 1)
                self.assertEqual([(f["rule"], f["severity"], f["resource"]) for f in data["findings"]],
                                 [("MIR005", "error", "app-test")])
                self.assertIn("Enable the system-assigned identity", data["findings"][0]["fix"])

    def code_config(self, scope: str) -> None:
        self.write("main.tf", '''resource "azurerm_linux_web_app" "app" {
  name = "app-test"
  identity {
    type = "SystemAssigned"
  }
}
resource "azurerm_role_assignment" "blob" {
  role_definition_name = "Storage Blob Data Reader"
  principal_id = azurerm_linux_web_app.app.identity[0].principal_id
  scope = "''' + scope + '''"
}
''')

    def test_plain_url_does_not_require_an_identity(self) -> None:
        self.write("main.tf", '''resource "azurerm_linux_web_app" "app" {
  name = "app-test"
  app_settings = {
    BLOB_ENDPOINT = "https://store.blob.core.windows.net"
  }
}
''')
        code, data = review("static", str(self.root))
        self.assertEqual(code, 0)
        self.assertEqual(data["findings"], [])

    def test_code_credential_without_identity_reports_selection_error(self) -> None:
        self.write("main.tf", '''resource "azurerm_linux_web_app" "app" {
  name = "app-test"
  app_settings = {
    APP_MODE = "test"
  }
}
''')
        self.write("source.cs", 'var client = new BlobServiceClient("https://store.blob.core.windows.net", new ManagedIdentityCredential());')
        code, data = review("static", str(self.root), "--map", "source.cs=app-test")
        self.assertEqual(code, 1)
        self.assertEqual([(f["rule"], f["severity"]) for f in data["findings"]], [("MIR005", "error")])

    def test_every_distinct_code_endpoint_is_checked(self) -> None:
        self.code_config("/subscriptions/s/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/grantedstore")
        self.write("source.cs", '''var first = new BlobServiceClient("https://grantedstore.blob.core.windows.net", new ManagedIdentityCredential());
var second = new BlobServiceClient("https://missingstore.blob.core.windows.net", new ManagedIdentityCredential());
var third = new BlobServiceClient("https://missingstore.blob.core.windows.net", new ManagedIdentityCredential());
''')
        code, data = review("static", str(self.root), "--map", "source.cs=app-test")
        self.assertEqual(code, 1)
        self.assertEqual({t["target_name"] for t in data["targets"]}, {"grantedstore", "missingstore"})
        self.assertEqual(len(data["targets"]), 2)
        missing = findings(data, "MIR002")
        self.assertEqual(len(missing), 1)
        self.assertIn("missingstore", missing[0]["message"])

    def test_code_endpoints_keep_distinct_child_paths(self) -> None:
        self.code_config("/subscriptions/s/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/grantedstore/blobServices/default/containers/reports")
        self.write("source.cs", '''var first = new BlobContainerClient("https://grantedstore.blob.core.windows.net/reports", new ManagedIdentityCredential());
var second = new BlobContainerClient("https://grantedstore.blob.core.windows.net/invoices", new ManagedIdentityCredential());
''')
        code, data = review("static", str(self.root), "--map", "source.cs=app-test")
        self.assertEqual(code, 1)
        self.assertEqual(len(data["targets"]), 2)
        missing = findings(data, "MIR002")
        self.assertEqual(len(missing), 1)
        self.assertIn("source.cs:2", missing[0]["message"])


class ExpressionRegressionTests(unittest.TestCase):
    def test_if_does_not_guess_when_condition_is_unknown(self) -> None:
        context = msi_review.ArmContext({}, {}, {}, "test")
        value = context.value("[if(parameters('unset'), 'id-a', 'id-b')]")
        self.assertIsInstance(value, msi_review.Unknown)

    def test_if_evaluates_only_selected_branch(self) -> None:
        context = msi_review.ArmContext({}, {}, {}, "test")
        # The unused branch would raise IndexError if evaluated.
        self.assertEqual(context.value("[if(false(), parameters(), 'id-b')]"), "id-b")
        self.assertEqual(context.value("[if(true(), 'id-a', parameters())]"), "id-a")
        self.assertEqual(context.value("[if(false, 'id-a', 'id-b')]"), "id-b")
        self.assertEqual(context.value("[if(bool('false'), 'id-a', 'id-b')]"), "id-b")

    def test_map_commas_inside_nested_expressions_are_preserved(self) -> None:
        values = msi_review.hcl_map('{ A = "a,b", B = concat(["x", "y"], ["z"]), C = { nested = "one,two" } }')
        self.assertEqual(values, {"A": '"a,b"', "B": 'concat(["x", "y"], ["z"])', "C": '{ nested = "one,two" }'})


if __name__ == "__main__":
    unittest.main()
