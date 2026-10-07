from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

import msi_review  # noqa: E402

SUBSCRIPTION = "00000000-0000-0000-0000-000000000000"
BASE = f"/subscriptions/{SUBSCRIPTION}/resourceGroups"


def wrapped(rows: list[dict]) -> dict:
    return {"totalRecords": len(rows), "count": len(rows), "data": rows}


def run_live(*, identities: list[dict] | None = None, holders: list[dict] | None = None,
             vaults: list[dict] | None = None, settings: dict[str, list[dict]] | None = None,
             roles: dict[str, list[dict]] | None = None, identity: str | None = None) -> tuple[int, dict]:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        index: dict[str, str] = {}

        def save(key: str, filename: str, value: object) -> None:
            (root / filename).write_text(json.dumps(value), encoding="utf-8")
            index[key] = filename

        save("graph:identities#0", "identities.json", wrapped(identities or []))
        save("graph:holders#0", "holders.json", wrapped(holders or []))
        save("graph:vaults#0", "vaults.json", wrapped(vaults or []))
        save("graph:cosmos#0", "cosmos.json", wrapped([]))
        for n, (resource_id, rows) in enumerate((settings or {}).items()):
            save(f"appsettings:{resource_id}", f"settings-{n}.json", rows)
        for n, (principal, rows) in enumerate((roles or {}).items()):
            save(f"roles:{principal}", f"roles-{n}.json", rows)
        (root / "index.json").write_text(json.dumps(index), encoding="utf-8")
        args = ["live", "--subscription", SUBSCRIPTION, "--replay", str(root), "--json"]
        if identity:
            args.extend(["--identity", identity])
        stdout = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
            code = msi_review.main(args)
        return code, json.loads(stdout.getvalue())


def uami(name: str, group: str, principal: str, client: str) -> dict:
    resource_id = f"{BASE}/{group}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/{name}"
    return {"id": resource_id, "name": name, "resourceGroup": group, "principalId": principal, "clientId": client}


def site(name: str, group: str, *, uamis: list[str] | None = None, principal: str | None = None) -> dict:
    identity: dict = {"type": "UserAssigned" if uamis else "SystemAssigned" if principal else "None"}
    if uamis:
        identity["userAssignedIdentities"] = {resource_id: {} for resource_id in uamis}
    if principal:
        identity["principalId"] = principal
    return {"id": f"{BASE}/{group}/providers/Microsoft.Web/sites/{name}", "name": name,
            "resourceGroup": group, "type": "microsoft.web/sites", "identity": identity,
            "kvRef": None, "encryption": None, "identityProfile": None, "registries": None,
            "secrets": None, "containers": None, "acrClientId": None}


class LiveIdentityRegressionTests(unittest.TestCase):
    def test_same_named_identities_do_not_share_grants(self) -> None:
        a = uami("shared", "rg-a", "11111111-1111-1111-1111-111111111111", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        b = uami("shared", "rg-b", "22222222-2222-2222-2222-222222222222", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        holders = [site("app-a", "rg-a", uamis=[a["id"]]), site("app-b", "rg-b", uamis=[b["id"]])]
        settings = {holder["id"]: [
            {"name": "Bus__fullyQualifiedNamespace", "value": "orders.servicebus.windows.net"},
            {"name": "Bus__credential", "value": "managedidentity"},
            {"name": "Bus__clientId", "value": ident["clientId"]},
        ] for holder, ident in zip(holders, (a, b))}
        code, data = run_live(identities=[a, b], holders=holders, settings=settings,
                              roles={a["principalId"]: [{"roleDefinitionName": "Azure Service Bus Data Receiver",
                                     "scope": f"{BASE}/rg-bus/providers/Microsoft.ServiceBus/namespaces/orders"}],
                                     b["principalId"]: []})
        self.assertEqual(code, 1)
        self.assertEqual([(f["rule"], f["identity"], f["resource"]) for f in data["findings"]],
                         [("MIR002", b["id"].lower(), "app-b")])

    def test_same_named_identities_are_distinct_and_full_resource_id_selects_exactly_one(self) -> None:
        a = uami("shared", "rg-a", "11111111-1111-1111-1111-111111111111", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        b = uami("shared", "rg-b", "22222222-2222-2222-2222-222222222222", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        aid = a["id"]
        bid = b["id"]
        holders = [site("app-a", "rg-a", uamis=[aid]), site("app-b", "rg-b", uamis=[bid])]
        code, data = run_live(identities=[a, b], holders=holders, identity=bid.upper())
        self.assertEqual(code, 0)
        user_ids = {row["key"] for row in data["identities"] if row["kind"] == "user"}
        self.assertEqual(user_ids, {bid.lower()})
        resources = {row["key"]: row for row in data["resources"]}
        self.assertEqual(resources["app-b"]["user_identities"], [bid.lower()])
        self.assertEqual(resources["app-a"]["user_identities"], [aid.lower()])

    def test_unfiltered_review_includes_system_assigned_only_resources(self) -> None:
        principal = "33333333-3333-3333-3333-333333333333"
        app_id = f"{BASE}/rg-sys/providers/Microsoft.Web/sites/sys-app"
        code, data = run_live(holders=[site("sys-app", "rg-sys", principal=principal)],
                              settings={app_id: [
                                  {"name": "Bus__credential", "value": "managedidentity"},
                                  {"name": "Bus__fullyQualifiedNamespace", "value": "orders.servicebus.windows.net"},
                              ]}, roles={principal: []})
        self.assertEqual(code, 1)
        self.assertIn("system:sys-app", {row["key"] for row in data["identities"]})
        self.assertTrue(any(t["resource"] == "sys-app" and t["service"] == "servicebus" for t in data["targets"]))
        self.assertTrue(any(f["rule"] == "MIR002" and f["resource"] == "sys-app" for f in data["findings"]))

    def test_duplicate_resource_names_keep_both_system_identities(self) -> None:
        principals = ["44444444-4444-4444-4444-444444444444", "55555555-5555-5555-5555-555555555555"]
        holders = [site("same-app", "rg-a", principal=principals[0]), site("same-app", "rg-b", principal=principals[1])]
        code, data = run_live(holders=holders, roles={p: [] for p in principals})
        self.assertEqual(code, 0)
        system_keys = {row["key"] for row in data["identities"] if row["kind"] == "system"}
        self.assertEqual(system_keys, {f"system:{h['id'].lower()}" for h in holders})
        self.assertEqual({row["resource_id"].lower() for row in data["resources"]}, {h["id"].lower() for h in holders})

    def test_key_vault_access_policy_does_not_cover_rbac_vault(self) -> None:
        ident = uami("kv-client", "rg-app", "66666666-6666-6666-6666-666666666666",
                     "77777777-7777-7777-7777-777777777777")
        holder = site("kv-app", "rg-app", uamis=[ident["id"]])
        app_id = holder["id"]
        vault = {"id": f"{BASE}/rg-data/providers/Microsoft.KeyVault/vaults/kv-test", "name": "kv-test",
                 "resourceGroup": "rg-data", "rbac": True,
                 "accessPolicies": [{"objectId": ident["principalId"]}]}
        settings = {app_id: [
            {"name": "Vault__vaultUri", "value": "https://kv-test.vault.azure.net"},
            {"name": "Vault__clientId", "value": ident["clientId"]},
        ]}
        for rbac in (True, False):
            with self.subTest(rbac=rbac):
                vault["rbac"] = rbac
                code, data = run_live(identities=[ident], holders=[holder], vaults=[vault], settings=settings,
                                      roles={ident["principalId"]: []})
                self.assertEqual(code, 1 if rbac else 0)
                missing = [f for f in data["findings"] if f["rule"] == "MIR002" and f["resource"] == "kv-app"]
                self.assertEqual(len(missing), 1 if rbac else 0)
                self.assertTrue(any(g["plane"] == "kv-access-policy" for g in data["grants"]))


if __name__ == "__main__":
    unittest.main()
