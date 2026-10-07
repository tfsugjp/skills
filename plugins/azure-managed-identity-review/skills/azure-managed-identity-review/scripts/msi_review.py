#!/usr/bin/env python3
"""Review who else uses a managed identity, and what each user needs.

`static` reads Bicep (compiled to ARM), ARM JSON, Terraform, app settings,
and source code. `live` reads the subscription with read-only `az` calls.
Both build the same model: identities, the resources that hold them, the
targets each resource reaches with them, the grants they hold, and their
federated identity credentials. Rules MIR000-MIR008 run over that model.

Exit codes: 0 no warnings or errors, 1 warnings or errors, 2 input error.
Python 3.9+, standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

UAMI_ARM_TYPE = "microsoft.managedidentity/userassignedidentities"
FIC_AUDIENCES = {
    "api://azureadtokenexchange",
    "api://azureadtokenexchangeusgov",
    "api://azureadtokenexchangechina",
}
SKIP_DIRS = {".git", "node_modules", "bin", "obj", ".terraform", "dist", "build", ".venv", "venv", "__pycache__", ".idea", ".vs"}
CODE_EXTS = {".cs", ".py", ".js", ".mjs", ".cjs", ".ts", ".java", ".go", ".ps1", ".kt", ".rs"}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2, "note": 3}

# --------------------------------------------------------------------------
# Services, audiences, and the grants that satisfy them
# --------------------------------------------------------------------------

# service -> (description, RBAC roles that grant data access, needs non-RBAC grant)
SERVICES: Dict[str, Tuple[str, Tuple[str, ...], Optional[str]]] = {
    "storage": ("Azure Storage (any data service)", (
        "Storage Blob Data Owner", "Storage Blob Data Contributor", "Storage Blob Data Reader",
        "Storage Queue Data Contributor", "Storage Queue Data Reader", "Storage Queue Data Message Sender",
        "Storage Queue Data Message Processor", "Storage Table Data Contributor", "Storage Table Data Reader",
        "Storage File Data Privileged Contributor", "Storage File Data Privileged Reader",
        "Storage File Data SMB Share Contributor", "Storage File Data SMB Share Reader"), None),
    "storage-blob": ("Blob Storage", ("Storage Blob Data Owner", "Storage Blob Data Contributor", "Storage Blob Data Reader"), None),
    "storage-queue": ("Queue Storage", ("Storage Queue Data Contributor", "Storage Queue Data Reader",
                                        "Storage Queue Data Message Sender", "Storage Queue Data Message Processor"), None),
    "storage-table": ("Table Storage", ("Storage Table Data Contributor", "Storage Table Data Reader"), None),
    "storage-file": ("Azure Files", ("Storage File Data Privileged Contributor", "Storage File Data Privileged Reader",
                                     "Storage File Data SMB Share Contributor", "Storage File Data SMB Share Reader"), None),
    "keyvault": ("Key Vault", ("Key Vault Administrator", "Key Vault Secrets User", "Key Vault Secrets Officer",
                               "Key Vault Crypto User", "Key Vault Crypto Officer", "Key Vault Crypto Service Encryption User",
                               "Key Vault Certificate User", "Key Vault Certificates Officer"), None),
    "servicebus": ("Service Bus", ("Azure Service Bus Data Owner", "Azure Service Bus Data Sender", "Azure Service Bus Data Receiver"), None),
    "eventhubs": ("Event Hubs", ("Azure Event Hubs Data Owner", "Azure Event Hubs Data Sender", "Azure Event Hubs Data Receiver"), None),
    "appconfig": ("App Configuration", ("App Configuration Data Owner", "App Configuration Data Reader"), None),
    # Roles whose dataActions include Microsoft.CognitiveServices data actions for OpenAI, AI services, or agents.
    "cognitive": ("Azure OpenAI / AI services", ("Cognitive Services OpenAI User", "Cognitive Services OpenAI Contributor",
                                                 "Cognitive Services User", "Cognitive Services Data Contributor (Preview)",
                                                 "Azure AI Developer", "Foundry User", "Foundry Owner", "Foundry Project Manager",
                                                 "Foundry Agent Consumer", "Foundry Project Runtime User"), None),
    "acr": ("Container Registry", ("AcrPull", "AcrPush", "Container Registry Repository Reader",
                                   "Container Registry Repository Writer"), None),
    "search": ("Azure AI Search", ("Search Index Data Reader", "Search Index Data Contributor"), None),
    "signalr": ("SignalR", ("SignalR App Server", "SignalR Service Owner"), None),
    "eventgrid": ("Event Grid", ("EventGrid Data Sender",), None),
    "cosmos": ("Cosmos DB data plane", (), "Cosmos DB SQL role assignment (data plane, not Azure RBAC)"),
    "sql": ("Azure SQL", (), "contained database user (CREATE USER [<identity>] FROM EXTERNAL PROVIDER) and database roles"),
    "graph": ("Microsoft Graph", (), "app role assignment on the Microsoft Graph service principal"),
    "custom-api": ("Custom Entra ID API", (), "app role assignment on the API's service principal"),
    "arm": ("Azure Resource Manager", ("*",), None),
}

PRIVILEGED_ROLES = {"owner", "contributor", "user access administrator", "role based access control administrator",
                    "key vault administrator"}

# Built-in role definition IDs commonly found in templates (verified with `az role definition list`).
ROLE_IDS = {
    "8e3af657-a8ff-443c-a75c-2fe8c4bcb635": "Owner",
    "b24988ac-6180-42a0-ab88-20f7382dd24c": "Contributor",
    "acdd72a7-3385-48ef-bd42-f606fba81ae7": "Reader",
    "18d7d88d-d35e-4fb5-a5c3-7773c20a72d9": "User Access Administrator",
    "f58310d9-a9f6-439a-9e8d-f62e7b41a168": "Role Based Access Control Administrator",
    "b7e6dc6d-f1e8-4753-8033-0f276bb0955b": "Storage Blob Data Owner",
    "ba92f5b4-2d11-453d-a403-e96b0029c9fe": "Storage Blob Data Contributor",
    "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1": "Storage Blob Data Reader",
    "974c5e8b-45b9-4653-ba55-5f855dd0fb88": "Storage Queue Data Contributor",
    "19e7f393-937e-4f77-808e-94535e297925": "Storage Queue Data Reader",
    "c6a89b2d-59bc-44d0-9896-0f6e12d7b80a": "Storage Queue Data Message Sender",
    "8a0f0c08-91a1-4084-bc3d-661d67233fed": "Storage Queue Data Message Processor",
    "0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3": "Storage Table Data Contributor",
    "76199698-9eea-4c19-bc75-cec21354c6b6": "Storage Table Data Reader",
    "17d1049b-9a84-46fb-8f53-869881c3d3ab": "Storage Account Contributor",
    "00482a5a-887f-4fb3-b363-3b7fe8e74483": "Key Vault Administrator",
    "4633458b-17de-408a-b874-0445c86b69e6": "Key Vault Secrets User",
    "b86a8fe4-44ce-4948-aee5-eccb2c155cd7": "Key Vault Secrets Officer",
    "12338af0-0e69-4776-bea7-57ae8d297424": "Key Vault Crypto User",
    "14b46e9e-c2b7-41b4-b07b-48a6ebf60603": "Key Vault Crypto Officer",
    "e147488a-f6f5-4113-8e2d-b22465e65bf6": "Key Vault Crypto Service Encryption User",
    "db79e9a7-68ee-4b58-9aeb-b90e7c24fcba": "Key Vault Certificate User",
    "a4417e6f-fecd-4de8-b567-7b0420556985": "Key Vault Certificates Officer",
    "21090545-7ca7-4776-b22c-e363652d74d2": "Key Vault Reader",
    "090c5cfd-751d-490a-894a-3ce6f1109419": "Azure Service Bus Data Owner",
    "69a216fc-b8fb-44d8-bc22-1f3c2cd27a39": "Azure Service Bus Data Sender",
    "4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0": "Azure Service Bus Data Receiver",
    "f526a384-b230-433a-b45c-95f59c4a2dec": "Azure Event Hubs Data Owner",
    "2b629674-e913-4c01-ae53-ef4638d8f975": "Azure Event Hubs Data Sender",
    "a638d3c7-ab3a-418d-83e6-5f17a39d4fde": "Azure Event Hubs Data Receiver",
    "5ae67dd6-50cb-40e7-96ff-dc2bfa4b606b": "App Configuration Data Owner",
    "516239f1-63e1-4d78-a4de-a74fb236a071": "App Configuration Data Reader",
    "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd": "Cognitive Services OpenAI User",
    "a001fd3d-188f-4b5d-821b-7da978bf7442": "Cognitive Services OpenAI Contributor",
    "a97b65f3-24c7-4388-baec-2e87135dc908": "Cognitive Services User",
    "7f951dda-4ed3-4680-a7ca-43fe172d538d": "AcrPull",
    "8311e382-0749-4cb8-b61a-304f252e45ec": "AcrPush",
    "1407120a-92aa-4202-b7e9-c0e197c71c8f": "Search Index Data Reader",
    "8ebe5a00-799e-43f5-93ac-243d3dce84a7": "Search Index Data Contributor",
    "420fcaa2-552c-430f-98ca-3264be4806c7": "SignalR App Server",
    "d5a91429-5739-47e2-a06b-3470a27159e7": "EventGrid Data Sender",
}
COSMOS_DATA_ROLES = {
    "00000000-0000-0000-0000-000000000001": "Cosmos DB Built-in Data Reader",
    "00000000-0000-0000-0000-000000000002": "Cosmos DB Built-in Data Contributor",
}

# ARM / Terraform resource type -> service reached when an app setting points at it.
TYPE_SERVICE = {
    "microsoft.storage/storageaccounts": "storage", "azurerm_storage_account": "storage",
    "microsoft.keyvault/vaults": "keyvault", "azurerm_key_vault": "keyvault",
    "microsoft.servicebus/namespaces": "servicebus", "azurerm_servicebus_namespace": "servicebus",
    "microsoft.eventhub/namespaces": "eventhubs", "azurerm_eventhub_namespace": "eventhubs",
    "microsoft.appconfiguration/configurationstores": "appconfig", "azurerm_app_configuration": "appconfig",
    "microsoft.cognitiveservices/accounts": "cognitive", "azurerm_cognitive_account": "cognitive",
    "microsoft.containerregistry/registries": "acr", "azurerm_container_registry": "acr",
    "microsoft.search/searchservices": "search", "azurerm_search_service": "search",
    "microsoft.signalrservice/signalr": "signalr", "azurerm_signalr_service": "signalr",
    "microsoft.documentdb/databaseaccounts": "cosmos", "azurerm_cosmosdb_account": "cosmos",
    "microsoft.sql/servers": "sql", "azurerm_mssql_server": "sql", "azurerm_mssql_database": "sql",
    "microsoft.eventgrid/topics": "eventgrid", "azurerm_eventgrid_topic": "eventgrid",
}

# Host fragments and token scopes -> service.
HOST_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\.blob\.", re.I), "storage-blob"),
    (re.compile(r"\.queue\.", re.I), "storage-queue"),
    (re.compile(r"\.table\.(core|cosmos)", re.I), "storage-table"),
    (re.compile(r"\.dfs\.", re.I), "storage-blob"),
    (re.compile(r"\.file\.core\.", re.I), "storage-file"),
    (re.compile(r"\.vault\.(azure|usgovcloudapi|azure\.cn)", re.I), "keyvault"),
    (re.compile(r"\.servicebus\.(windows|usgovcloudapi|chinacloudapi)", re.I), "servicebus"),
    (re.compile(r"\.documents\.azure\.", re.I), "cosmos"),
    (re.compile(r"\.database\.(windows|usgovcloudapi|chinacloudapi)\.", re.I), "sql"),
    (re.compile(r"\.azconfig\.io", re.I), "appconfig"),
    (re.compile(r"\.(openai|cognitiveservices)\.azure\.", re.I), "cognitive"),
    (re.compile(r"\.services\.ai\.azure\.", re.I), "cognitive"),
    (re.compile(r"\.azurecr\.io", re.I), "acr"),
    (re.compile(r"\.search\.windows\.net", re.I), "search"),
    (re.compile(r"\.service\.signalr\.net", re.I), "signalr"),
    (re.compile(r"\.eventgrid\.azure\.net", re.I), "eventgrid"),
]
SCOPE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"^https://storage\.azure\.com", re.I), "storage"),
    (re.compile(r"^https://vault\.azure\.net", re.I), "keyvault"),
    (re.compile(r"^https://servicebus\.azure\.net", re.I), "servicebus"),
    (re.compile(r"^https://eventhubs\.azure\.net", re.I), "eventhubs"),
    (re.compile(r"^https://database\.windows\.net", re.I), "sql"),
    (re.compile(r"^https://cosmos\.azure\.com", re.I), "cosmos"),
    (re.compile(r"^https://azconfig\.io", re.I), "appconfig"),
    (re.compile(r"^https://cognitiveservices\.azure\.com", re.I), "cognitive"),
    (re.compile(r"^https://ai\.azure\.com", re.I), "cognitive"),
    (re.compile(r"^https://search\.azure\.com", re.I), "search"),
    (re.compile(r"^https://eventgrid\.azure\.net", re.I), "eventgrid"),
    (re.compile(r"^https://graph\.microsoft\.com", re.I), "graph"),
    (re.compile(r"^https://management\.(azure\.com|core\.windows\.net)", re.I), "arm"),
    (re.compile(r"^api://", re.I), "custom-api"),
]
# Functions identity-based connection property -> service.
CONNECTION_PROPS = {
    "blobserviceuri": "storage-blob", "queueserviceuri": "storage-queue", "tableserviceuri": "storage-table",
    "accountname": "storage", "accountendpoint": "cosmos", "vaulturi": "keyvault",
    "fullyqualifiednamespace": "servicebus", "endpoint": None, "serviceuri": None, "topicendpointuri": "eventgrid",
}


def service_from_text(text: str) -> Optional[str]:
    for pattern, service in SCOPE_PATTERNS:
        if pattern.search(text):
            return service
    for pattern, service in HOST_PATTERNS:
        if pattern.search(text):
            return service
    return None


def target_name_from_endpoint(text: str) -> Optional[str]:
    vault = re.search(r"VaultName=([A-Za-z0-9\-]+)", text, re.I)
    if vault:
        return vault.group(1)
    match = re.search(r"(?:https?://)?([A-Za-z0-9{}:\-_*]+)\.(?:blob|queue|table|dfs|file|vault|servicebus|documents|database|azconfig|openai|cognitiveservices|azurecr|search|service|services)\b", text)
    if not match:
        return None
    name = match.group(1)
    return None if "*" in name else name


def role_covers(role: str, service: str) -> bool:
    roles = SERVICES[service][1]
    return roles == ("*",) or role in roles


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------

@dataclass
class Identity:
    key: str
    kind: str  # user | system
    name: str
    source: str
    client_id: Optional[str] = None
    principal_id: Optional[str] = None
    resource_id: Optional[str] = None
    resource_group: Optional[str] = None
    resolved: bool = True


@dataclass
class Setting:
    name: str
    value: Optional[str]
    identity_ref: Optional[str] = None  # identity key referenced by the value (client ID / resource ID)
    service: Optional[str] = None
    target_name: Optional[str] = None


@dataclass
class Resource:
    key: str
    type: str
    source: str
    user_identities: List[str] = field(default_factory=list)
    system_assigned: bool = False
    settings: Dict[str, Setting] = field(default_factory=dict)
    slots: List[Tuple[str, str]] = field(default_factory=list)  # (property path, identity key)
    resource_id: Optional[str] = None
    slot_targets: Dict[str, str] = field(default_factory=dict)  # slot path -> target resource name


@dataclass
class Grant:
    identity: str
    role: str
    scope_kind: str  # resource | resourceGroup | subscription | managementGroup | root | unknown
    scope_name: Optional[str]
    source: str
    plane: str = "rbac"  # rbac | cosmos | kv-access-policy
    scope: Optional[str] = None
    scope_path: Optional[str] = None  # set when the scope is a child of the resource (container, queue, secret)


@dataclass
class Fic:
    identity: str
    name: str
    issuer: Optional[str]
    subject: Optional[str]
    audiences: List[str]
    flexible: bool
    source: str


@dataclass
class Target:
    resource: str
    service: str
    target_name: Optional[str]
    identity: Optional[str]  # identity key; None when unresolved
    via: str
    explicit: bool  # identity-based connection or platform slot, not a guess from a URL
    value: Optional[str] = None  # the endpoint the consumer uses, when known


@dataclass
class CodeEvidence:
    file: str
    line: int
    kind: str  # credential | scope | endpoint | local-setting
    detail: str
    service: Optional[str] = None
    resource: Optional[str] = None


@dataclass
class Finding:
    rule: str
    severity: str
    identity: Optional[str]
    resource: Optional[str]
    message: str
    fix: str


@dataclass
class Model:
    origin: str
    identities: Dict[str, Identity] = field(default_factory=dict)
    resources: Dict[str, Resource] = field(default_factory=dict)
    grants: List[Grant] = field(default_factory=list)
    fics: List[Fic] = field(default_factory=list)
    code: List[CodeEvidence] = field(default_factory=list)
    notes: List[Finding] = field(default_factory=list)
    targets: List[Target] = field(default_factory=list)
    vault_rbac: Dict[str, bool] = field(default_factory=dict)
    resource_types: Dict[str, str] = field(default_factory=dict)  # resource name (lower) -> type (lower)

    def note(self, message: str, fix: str = "", resource: Optional[str] = None, identity: Optional[str] = None) -> None:
        self.notes.append(Finding("MIR000", "note", identity, resource, message, fix or "Pass --parameters or review the reference by hand."))

    def add_identity(self, identity: Identity) -> Identity:
        existing = self.identities.get(identity.key)
        if existing:
            for attr in ("client_id", "principal_id", "resource_id", "resource_group"):
                if getattr(identity, attr) and not getattr(existing, attr):
                    setattr(existing, attr, getattr(identity, attr))
            return existing
        self.identities[identity.key] = identity
        return identity

    def system_identity(self, resource: str, source: str) -> str:
        key = f"system:{resource}"
        self.add_identity(Identity(key=key, kind="system", name=f"{resource} (system-assigned)", source=source))
        return key


# --------------------------------------------------------------------------
# ARM expression evaluation
# --------------------------------------------------------------------------

class Unknown:
    def __init__(self, label: str) -> None:
        self.label = label

    def __repr__(self) -> str:
        return f"{{{self.label}}}"


class Partial(str):
    """A string that contains unresolved parts, rendered as {label}."""


@dataclass
class ResourceRef:
    type: str
    name: Any  # str, Partial, or Unknown


@dataclass
class PropRef:
    ref: ResourceRef
    path: List[str]


def as_text(value: Any) -> Any:
    if isinstance(value, Unknown):
        return Partial(repr(value))
    if isinstance(value, ResourceRef):
        return value
    if value is None:
        return Partial("{null}")
    if isinstance(value, (dict, list, PropRef)):
        return Partial("{object}")
    return str(value)


class ArmExpr:
    TOKEN = re.compile(r"\s*(?:(?P<str>'(?:[^']|'')*')|(?P<num>-?\d+(?:\.\d+)?)|(?P<id>[A-Za-z_][A-Za-z0-9_]*)|(?P<punct>[().,\[\]]))")

    def __init__(self, text: str) -> None:
        self.tokens: List[Tuple[str, str]] = []
        pos = 0
        while pos < len(text):
            if text[pos:].strip() == "":
                break
            match = self.TOKEN.match(text, pos)
            if not match:
                raise ValueError(f"cannot parse expression near: {text[pos:pos + 20]}")
            kind = match.lastgroup or ""
            self.tokens.append((kind, match.group(kind)))
            pos = match.end()
        self.index = 0

    def peek(self) -> Optional[Tuple[str, str]]:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def take(self, value: Optional[str] = None) -> Tuple[str, str]:
        token = self.peek()
        if token is None or (value is not None and token[1] != value):
            raise ValueError(f"expected {value}")
        self.index += 1
        return token

    def parse(self) -> Any:
        node = self.parse_postfix()
        if self.peek() is not None:
            raise ValueError("trailing tokens")
        return node

    def parse_postfix(self) -> Any:
        node = self.parse_primary()
        while True:
            token = self.peek()
            if token and token[1] == ".":
                self.take(".")
                node = ("prop", node, self.take()[1])
            elif token and token[1] == "[":
                self.take("[")
                index = self.parse_postfix()
                self.take("]")
                node = ("index", node, index)
            else:
                return node

    def parse_primary(self) -> Any:
        kind, value = self.take()
        if kind == "str":
            return ("lit", value[1:-1].replace("''", "'"))
        if kind == "num":
            return ("lit", value)
        if kind == "id":
            if value in ("true", "false", "null"):
                return ("lit", value)
            args: List[Any] = []
            self.take("(")
            if self.peek() and self.peek()[1] != ")":
                args.append(self.parse_postfix())
                while self.peek() and self.peek()[1] == ",":
                    self.take(",")
                    args.append(self.parse_postfix())
            self.take(")")
            return ("call", value.lower(), args)
        raise ValueError(f"unexpected token {value}")


def resource_ref_from_id(text: str) -> Optional[ResourceRef]:
    matches = re.findall(r"/providers/([A-Za-z0-9.]+/[A-Za-z0-9]+)/([^/]+)", text)
    if not matches:
        return None
    rtype, name = matches[-1]
    return ResourceRef(rtype, name)


class ArmContext:
    def __init__(self, params: Dict[str, Any], variables: Dict[str, Any], symbols: Dict[str, ResourceRef], source: str) -> None:
        self.params = params
        self.variables = variables
        self.symbols = symbols
        self.source = source
        self._var_cache: Dict[str, Any] = {}

    def variable(self, name: str) -> Any:
        if name not in self._var_cache:
            self._var_cache[name] = Unknown(f"var:{name}")
            self._var_cache[name] = self.value(self.variables.get(name, Unknown(f"var:{name}")))
        return self._var_cache[name]

    def value(self, raw: Any) -> Any:
        if isinstance(raw, str):
            if raw.startswith("[[") or not (raw.startswith("[") and raw.endswith("]")):
                return raw[1:] if raw.startswith("[[") else raw
            try:
                return self.eval(ArmExpr(raw[1:-1]).parse())
            except (ValueError, RecursionError):
                return Unknown("expr")
        return raw

    def eval(self, node: Any) -> Any:
        kind = node[0]
        if kind == "lit":
            return node[1]
        if kind == "prop":
            base = self.eval(node[1])
            return self.member(base, node[2])
        if kind == "index":
            base = self.eval(node[1])
            index = self.eval(node[2])
            if isinstance(base, (dict, list, PropRef)):
                return self.member(base, str(index))
            return Unknown("index")
        name, args = node[1], [self.eval(arg) for arg in node[2]]
        if name == "parameters":
            key = str(args[0])
            return self.params.get(key, Unknown(f"param:{key}"))
        if name == "variables":
            return self.variable(str(args[0]))
        if name in ("concat", "format"):
            if name == "format":
                fmt = args[0]
                if not isinstance(fmt, str):
                    return Unknown("format")
                parts = [as_text(a) for a in args[1:]]
                if any(isinstance(p, ResourceRef) for p in parts):
                    refs = [p for p in parts if isinstance(p, ResourceRef)]
                    if fmt.strip() == "{0}" and len(parts) == 1:
                        return refs[0]
                    parts = [resource_id_text(p) if isinstance(p, ResourceRef) else p for p in parts]
                text = re.sub(r"\{(\d+)(?::[^}]*)?\}", lambda m: str(parts[int(m.group(1))]) if int(m.group(1)) < len(parts) else "{?}", fmt)
                return Partial(text) if any(isinstance(p, Partial) for p in parts) else text
            if args and all(isinstance(a, list) for a in args):
                return [item for a in args for item in a]
            parts = [as_text(a) for a in args]
            parts = [resource_id_text(p) if isinstance(p, ResourceRef) else p for p in parts]
            text = "".join(str(p) for p in parts)
            return Partial(text) if any(isinstance(p, Partial) for p in parts) else text
        if name in ("tolower", "toupper", "trim", "string"):
            value = args[0] if args else Unknown(name)
            if isinstance(value, ResourceRef) or not isinstance(value, str):
                return value
            result = value.lower() if name == "tolower" else value.upper() if name == "toupper" else value.strip()
            return Partial(result) if isinstance(value, Partial) else result
        if name in ("resourceid", "subscriptionresourceid", "tenantresourceid", "extensionresourceid"):
            strings = list(args)
            if name == "extensionresourceid":
                strings = strings[1:]
            type_index = next((i for i, a in enumerate(strings) if isinstance(a, str) and "/" in a and "." in a.split("/")[0]), None)
            if type_index is None:
                return Unknown("resourceId")
            rtype = strings[type_index]
            names = strings[type_index + 1:]
            name_text = "/".join(str(as_text(n)) for n in names)
            if any(isinstance(n, (Unknown, Partial)) for n in names):
                name_text = Partial(name_text)
            return ResourceRef(rtype, name_text)
        if name == "reference":
            target = args[0] if args else None
            if isinstance(target, ResourceRef):
                return PropRef(target, [])
            if isinstance(target, str):
                if target in self.symbols:
                    return PropRef(self.symbols[target], [])
                ref = resource_ref_from_id(target)
                if ref:
                    return PropRef(ref, [])
            return Unknown("reference")
        if name == "resourceinfo" and args and isinstance(args[0], str) and args[0] in self.symbols:
            return self.symbols[args[0]]
        if name == "if" and len(args) == 3:
            return args[1] if not isinstance(args[1], Unknown) else args[2]
        return Unknown(name)

    def member(self, base: Any, name: str) -> Any:
        if isinstance(base, PropRef):
            return PropRef(base.ref, base.path + [name])
        if isinstance(base, ResourceRef):
            if name == "id":
                return base
            if name == "name":
                return base.name
            return PropRef(base, [name])
        if isinstance(base, dict):
            return self.value(base.get(name, Unknown(f"prop:{name}")))
        if isinstance(base, list) and name.isdigit() and int(name) < len(base):
            return self.value(base[int(name)])
        if isinstance(base, Unknown):
            return Unknown(f"{base.label}.{name}")
        return Unknown(name)


def resource_id_text(ref: ResourceRef) -> Any:
    text = f"/providers/{ref.type}/{as_text(ref.name)}"
    return Partial(text) if isinstance(ref.name, (Partial, Unknown)) else text


def is_uami(ref: Any) -> bool:
    return isinstance(ref, ResourceRef) and ref.type.lower() == UAMI_ARM_TYPE


def uami_ref(value: Any) -> Optional[ResourceRef]:
    """The user-assigned identity a value refers to: an expression or a literal resource ID."""
    if is_uami(value):
        return value
    if isinstance(value, PropRef) and is_uami(value.ref):
        return value.ref
    if isinstance(value, str) and "/userassignedidentities/" in value.lower():
        ref = resource_ref_from_id(value)
        return ref if is_uami(ref) else None
    return None


def target_from_value(value: Any) -> Optional[str]:
    """Name of the resource a value points at: an IaC reference, an endpoint, or a registry login server."""
    if isinstance(value, PropRef):
        return name_key(value.ref.name)
    if isinstance(value, ResourceRef):
        return name_key(value.name)
    if isinstance(value, str) and value:
        if ".azurecr." in value.lower():
            name = re.sub(r"^[A-Za-z]+\|", "", value).split("//")[-1].split(".")[0]
            return None if "{" in name else name
        return target_name_from_endpoint(value)
    return None


def split_resource_path(text: str) -> Optional[Tuple[str, str, Optional[str]]]:
    """(type, name, child path) from '/providers/<ns>/<type>/<name>[/<child>...]' or '<ns>/<type>/<name>[/...]'."""
    match = re.search(r"(?:^|/providers/)([A-Za-z][A-Za-z0-9]*\.[A-Za-z0-9.]+/[A-Za-z0-9]+)/([^/]+)((?:/[^/]+)*)$", text)
    if not match:
        return None
    rest = match.group(3).strip("/")
    return match.group(1), match.group(2), f"{match.group(2)}/{rest}" if rest else None


def name_key(name: Any) -> str:
    text = str(as_text(name))
    return text.split("/")[0] if "/" in text and not text.startswith("{") else text


# --------------------------------------------------------------------------
# Static: ARM / Bicep
# --------------------------------------------------------------------------

def bicep_command() -> Optional[List[str]]:
    if shutil.which("bicep"):
        return ["bicep", "build", "--stdout"]
    if shutil.which("az"):
        return ["az", "bicep", "build", "--stdout", "--file"]
    return None


def bicep_env() -> Dict[str, str]:
    env = dict(os.environ)
    # Bicep is a .NET single-file app; sandboxes without a writable home need an extraction dir.
    env.setdefault("DOTNET_BUNDLE_EXTRACT_BASE_DIR", os.path.join(tempfile.gettempdir(), "bicep-extract"))
    return env


def compile_bicep(path: Path, model: Model) -> Optional[dict]:
    command = bicep_command()
    if command is None:
        model.note(f"{path}: Bicep CLI not found; skipped.", "Install the Bicep CLI (az bicep install) or pass compiled ARM JSON.")
        return None
    executable = shutil.which(command[0]) or command[0]
    try:
        result = subprocess.run([executable, *command[1:], str(path)], capture_output=True, text=True,
                                encoding="utf-8", timeout=300, env=bicep_env())
    except (OSError, subprocess.TimeoutExpired) as error:
        model.note(f"{path}: Bicep build failed: {error}")
        return None
    if result.returncode != 0:
        first = next((line for line in result.stderr.splitlines() if "error" in line.lower()), result.stderr.strip()[:200])
        model.note(f"{path}: Bicep build failed: {first}", "Fix the Bicep compile error and rerun.")
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        model.note(f"{path}: Bicep build produced no JSON.")
        return None


def bicep_entry_files(root: Path, files: List[Path]) -> List[Path]:
    module_refs = set()
    pattern = re.compile(r"^\s*module\s+\w+\s+'([^']+\.bicep)'", re.M)
    for file in files:
        for ref in pattern.findall(file.read_text(encoding="utf-8", errors="replace")):
            module_refs.add((file.parent / ref).resolve())
    return [f for f in files if f.resolve() not in module_refs]


def load_parameters(files: List[str]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    for file in files:
        data = json.loads(Path(file).read_text(encoding="utf-8"))
        if "parametersJson" in data:  # az bicep build-params --stdout
            data = json.loads(data["parametersJson"])
        for name, entry in data.get("parameters", {}).items():
            if isinstance(entry, dict) and "value" in entry:
                values[name] = entry["value"]
    return values


def arm_resources(template: dict) -> List[Tuple[Optional[str], dict]]:
    resources = template.get("resources", [])
    if isinstance(resources, dict):  # languageVersion 2.0: symbolic names
        return list(resources.items())
    return [(None, r) for r in resources if isinstance(r, dict)]


def ingest_arm(template: dict, model: Model, source: str, params: Dict[str, Any], depth: int = 0) -> None:
    if depth > 8:
        return
    param_values: Dict[str, Any] = {}
    for name, definition in (template.get("parameters") or {}).items():
        if name in params:
            param_values[name] = params[name]
        elif isinstance(definition, dict) and "defaultValue" in definition:
            param_values[name] = definition["defaultValue"]
        else:
            param_values[name] = Unknown(f"param:{name}")
    schema = str(template.get("$schema", "")).lower()
    deploy_scope = "subscription" if "subscriptiondeploymenttemplate" in schema else \
        "managementGroup" if "managementgroupdeploymenttemplate" in schema else \
        "root" if "tenantdeploymenttemplate" in schema else "resourceGroup"
    entries = arm_resources(template)
    symbols: Dict[str, ResourceRef] = {}
    ctx = ArmContext({}, template.get("variables") or {}, symbols, source)
    for name, value in param_values.items():
        ctx.params[name] = ctx.value(value) if isinstance(value, str) else value
    for symbol, res in entries:
        if symbol:
            symbols[symbol] = ResourceRef(str(res.get("type", "")), ctx.value(res.get("name", "")))

    for symbol, res in entries:
        rtype = str(res.get("type", ""))
        ltype = rtype.lower()
        name = ctx.value(res.get("name", ""))
        props = res.get("properties") or {}
        if ltype != "microsoft.resources/deployments" and "/" in ltype:
            model.resource_types.setdefault(name_key(name).lower(), ltype)
        if ltype == "microsoft.resources/deployments":
            nested = props.get("template")
            if isinstance(nested, dict):
                passed = {}
                for pname, entry in (props.get("parameters") or {}).items():
                    if isinstance(entry, dict) and "value" in entry:
                        passed[pname] = evaluate_deep(ctx, entry["value"])
                ingest_arm(nested, model, f"{source} > module {as_text(name)}", passed, depth + 1)
            continue
        if ltype == UAMI_ARM_TYPE:
            key = name_key(name)
            model.add_identity(Identity(key=key, kind="user", name=key, source=source, resolved=not isinstance(name, (Partial, Unknown))))
            if isinstance(name, (Partial, Unknown)):
                model.note(f"Identity name {key} cannot be resolved statically.", identity=key)
            continue
        if ltype == UAMI_ARM_TYPE + "/federatedidentitycredentials":
            full = str(as_text(name))
            parent = full.split("/")[0]
            if res.get("parent") and symbol is not None:
                parent_ref = symbols.get(res["parent"]) if isinstance(res["parent"], str) else None
                if parent_ref is not None:
                    parent = name_key(parent_ref.name)
            audiences = [str(as_text(ctx.value(a))) for a in props.get("audiences", [])]
            model.fics.append(Fic(identity=parent, name=full.split("/")[-1], issuer=str(as_text(ctx.value(props.get("issuer")))) if props.get("issuer") else None,
                                  subject=str(as_text(ctx.value(props.get("subject")))) if props.get("subject") else None,
                                  audiences=audiences, flexible="claimsMatchingExpression" in props, source=source))
            continue
        if ltype == "microsoft.authorization/roleassignments" or ltype.endswith("/providers/roleassignments"):
            ingest_arm_role_assignment(ctx, model, res, name, deploy_scope, source)
            continue
        if ltype == "microsoft.documentdb/databaseaccounts/sqlroleassignments":
            principal = identity_from_principal(ctx.value(props.get("principalId")), model, source)
            role_id = str(as_text(ctx.value(props.get("roleDefinitionId", ""))))
            guid = role_id.rstrip("/").split("/")[-1]
            role = COSMOS_DATA_ROLES.get(guid.lower(), f"Cosmos DB custom role {guid}")
            account = str(as_text(name)).split("/")[0]
            if principal:
                model.grants.append(Grant(principal, role, "resource", account, source, plane="cosmos"))
            else:
                model.note(f"Cosmos DB SQL role assignment on {account} has an unresolvable principalId.", resource=account)
            continue
        if ltype == "microsoft.keyvault/vaults":
            vault = name_key(name)
            model.vault_rbac[vault] = bool(ctx.value(props.get("enableRbacAuthorization", False)) in (True, "true", "True"))
            for policy in props.get("accessPolicies", []) or []:
                ingest_access_policy(ctx, model, vault, policy, source)
            continue
        if ltype == "microsoft.keyvault/vaults/accesspolicies":
            vault = str(as_text(name)).split("/")[0]
            for policy in props.get("accessPolicies", []) or []:
                ingest_access_policy(ctx, model, vault, policy, source)
            continue
        if ltype == "microsoft.web/sites/config":
            site, _, config = str(as_text(name)).partition("/")
            if config.lower() == "appsettings":
                resource = model.resources.setdefault(site, Resource(key=site, type="Microsoft.Web/sites", source=source))
                for key, value in props.items():
                    resource.settings[key] = arm_setting(ctx, key, value)
            continue
        ingest_arm_consumer(ctx, model, res, rtype, name, source)


def evaluate_deep(ctx: ArmContext, value: Any) -> Any:
    if isinstance(value, str):
        return ctx.value(value)
    if isinstance(value, dict):
        return {k: evaluate_deep(ctx, v) for k, v in value.items()}
    if isinstance(value, list):
        return [evaluate_deep(ctx, v) for v in value]
    return value


def identity_from_principal(value: Any, model: Model, source: str) -> Optional[str]:
    if isinstance(value, PropRef):
        path = [p.lower() for p in value.path]
        if is_uami(value.ref) and path and path[-1] == "principalid":
            key = name_key(value.ref.name)
            model.add_identity(Identity(key=key, kind="user", name=key, source=source))
            return key
        if path[-2:] == ["identity", "principalid"]:
            return model.system_identity(name_key(value.ref.name), source)
    return None


def scope_from_ref(value: Any, default_kind: str) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
    """(kind, resource name, resource type, child path) of a role assignment scope."""
    if isinstance(value, PropRef) and value.path == []:
        value = value.ref
    if isinstance(value, ResourceRef):
        full = str(as_text(value.name))
        return "resource", name_key(value.name), value.type, full if "/" in full and not full.startswith("{") else None
    if isinstance(value, str) and value:
        text = str(value).rstrip("/")
        if "managementGroups/" in text and "/subscriptions/" not in text:
            return "managementGroup", text.split("/")[-1], None, None
        parsed = split_resource_path(text)
        if parsed and "/providers/microsoft.management/" not in text.lower():
            rtype, name, child = parsed
            return "resource", name, rtype, child
        if re.match(r"^/subscriptions/[^/]+/resourceGroups/[^/]+$", text, re.I):
            return "resourceGroup", text.split("/")[-1], None, None
        if re.match(r"^/subscriptions/[^/]+$", text, re.I):
            return "subscription", text.split("/")[-1], None, None
        if text == "":
            return "root", None, None, None
        return "unknown", None, None, None
    return (default_kind, None, None, None) if value in (None, "") else ("unknown", None, None, None)


def ingest_arm_role_assignment(ctx: ArmContext, model: Model, res: dict, name: Any, deploy_scope: str, source: str) -> None:
    props = res.get("properties") or {}
    principal = identity_from_principal(ctx.value(props.get("principalId")), model, source)
    role_raw = ctx.value(props.get("roleDefinitionId", ""))
    role_text = resource_id_text(role_raw) if isinstance(role_raw, ResourceRef) else str(as_text(role_raw))
    if isinstance(role_raw, ResourceRef):
        role_text = str(as_text(role_raw.name))
    guid = role_text.rstrip("/").split("/")[-1].lower()
    role = ROLE_IDS.get(guid, f"role {guid}")
    if "scope" in res:
        kind, scope_name, scope_type, child = scope_from_ref(ctx.value(res["scope"]), deploy_scope)
    elif str(res.get("type", "")).lower().endswith("/providers/roleassignments"):
        parent_type = str(res.get("type")).split("/providers/")[0]
        kind, scope_name, scope_type, child = "resource", str(as_text(name)).split("/")[0], parent_type, None
    else:
        kind, scope_name, scope_type, child = deploy_scope, None, None, None
    if principal is None:
        model.note(f"Role assignment ({role}) has a principalId that does not resolve to a managed identity in these templates.",
                   "Check whether the principal is a managed identity passed in as a parameter.")
        return
    model.grants.append(Grant(principal, role, kind, scope_name, source, scope=scope_type, scope_path=child))


def ingest_access_policy(ctx: ArmContext, model: Model, vault: str, policy: dict, source: str) -> None:
    principal = identity_from_principal(ctx.value(policy.get("objectId")), model, source)
    if principal:
        perms = policy.get("permissions") or {}
        summary = ",".join(f"{k}:{'/'.join(str(p) for p in v)}" for k, v in perms.items() if v)
        model.grants.append(Grant(principal, f"Access policy ({summary})", "resource", vault, source, plane="kv-access-policy"))


def walk_strings(value: Any, path: str = "") -> Iterable[Tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_strings(child, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_strings(child, f"{path}[{index}]")
    else:
        yield path, value


def arm_setting(ctx: ArmContext, name: str, raw: Any) -> Setting:
    value = ctx.value(raw)
    setting = Setting(name=name, value=None)
    if isinstance(value, PropRef):
        if is_uami(value.ref):
            setting.identity_ref = name_key(value.ref.name)
            setting.value = f"<{value.ref.name}.{'.'.join(value.path)}>"
            return setting
        service = TYPE_SERVICE.get(value.ref.type.lower())
        if service:
            joined = ".".join(value.path).lower()
            for part, sub in (("blob", "storage-blob"), ("queue", "storage-queue"), ("table", "storage-table"), ("file", "storage-file")):
                if part in joined and service == "storage":
                    service = sub
            setting.service, setting.target_name = service, name_key(value.ref.name)
        setting.value = f"<{as_text(value.ref.name)}.{'.'.join(value.path)}>"
        return setting
    if uami_ref(value):
        setting.identity_ref = name_key(uami_ref(value).name)
        setting.value = f"<{as_text(uami_ref(value).name)} resource ID>"
        return setting
    if isinstance(value, ResourceRef):
        setting.value = f"<{value.type}/{as_text(value.name)}>"
        return setting
    text = str(as_text(value))
    setting.value = text
    return setting


def ingest_arm_consumer(ctx: ArmContext, model: Model, res: dict, rtype: str, name: Any, source: str) -> None:
    identity = res.get("identity") or {}
    key = name_key(name)
    ids: List[str] = []
    for raw_key in (identity.get("userAssignedIdentities") or {}).keys():
        ref = uami_ref(ctx.value(raw_key))
        if ref:
            ids.append(name_key(ref.name))
        else:
            model.note(f"{key}: user-assigned identity reference {raw_key} cannot be resolved.", resource=key)
    system = "systemassigned" in str(ctx.value(identity.get("type", ""))).lower().replace(" ", "").replace(",", "")
    props = res.get("properties") or {}
    slots: List[Tuple[str, str]] = []
    settings: Dict[str, Setting] = {}
    slot_targets: Dict[str, str] = {}
    for path, raw in walk_strings(props):
        if not isinstance(raw, str) or not (raw.startswith("[") or "/userassignedidentities/" in raw.lower()):
            continue
        ref = uami_ref(ctx.value(raw))
        if ref and not re.search(r"appSettings\[\d+\]\.value$|env\[\d+\]\.value$", path):
            slots.append((path, name_key(ref.name)))
            target = None
            registry = re.match(r"configuration\.registries\[(\d+)\]", path)
            if registry:
                target = target_from_value(ctx.value(props["configuration"]["registries"][int(registry.group(1))].get("server", "")))
            elif "encryption" in path.lower():
                kv = ((props.get("encryption") or {}).get("keyvaultproperties") or {}).get("keyvaulturi", "")
                target = target_from_value(ctx.value(kv))
            elif path.lower().endswith("acrusermanagedidentityid"):
                site = props.get("siteConfig") or {}
                target = target_from_value(ctx.value(site.get("linuxFxVersion") or site.get("windowsFxVersion") or ""))
            if target:
                slot_targets[path] = target
    for index, item in enumerate(((props.get("siteConfig") or {}).get("appSettings") or [])):
        if isinstance(item, dict) and "name" in item:
            settings[str(ctx.value(item["name"]))] = arm_setting(ctx, str(ctx.value(item["name"])), item.get("value", ""))
    for container in ((props.get("template") or {}).get("containers") or []):
        for env in (container.get("env") or []):
            if isinstance(env, dict) and "name" in env:
                settings[str(env["name"])] = arm_setting(ctx, str(env["name"]), env.get("value", f"secretref:{env.get('secretRef', '')}"))
    for secret in ((props.get("configuration") or {}).get("secrets") or []):
        if isinstance(secret, dict) and secret.get("keyVaultUrl"):
            url = str(as_text(ctx.value(secret["keyVaultUrl"])))
            ident = ctx.value(secret.get("identity", ""))
            settings[f"secret:{secret.get('name')}"] = Setting(name=f"secret:{secret.get('name')}", value=f"keyVaultUrl={url}",
                                                               identity_ref=name_key(ident.name) if is_uami(ident) else ("system" if str(ident).lower() == "system" else None),
                                                               service="keyvault", target_name=target_name_from_endpoint(url))
    if not ids and not system and not slots and not settings:
        return
    resource = model.resources.setdefault(key, Resource(key=key, type=rtype, source=source))
    resource.type = rtype
    resource.user_identities = sorted(set(resource.user_identities + ids))
    resource.system_assigned = resource.system_assigned or system
    resource.slots.extend(slots)
    resource.slot_targets.update(slot_targets)
    resource.settings.update(settings)
    for ident in ids:
        model.add_identity(Identity(key=ident, kind="user", name=ident, source=source))
    if system:
        model.system_identity(key, source)


# --------------------------------------------------------------------------
# Static: Terraform
# --------------------------------------------------------------------------

@dataclass
class HclBlock:
    type: str
    labels: List[str]
    attrs: Dict[str, str]
    blocks: List["HclBlock"]


class HclParser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def skip(self, newlines: bool = True) -> None:
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch in " \t\r" or (newlines and ch == "\n"):
                self.pos += 1
            elif self.text.startswith("#", self.pos) or self.text.startswith("//", self.pos):
                end = self.text.find("\n", self.pos)
                self.pos = len(self.text) if end < 0 else end
            elif self.text.startswith("/*", self.pos):
                end = self.text.find("*/", self.pos)
                self.pos = len(self.text) if end < 0 else end + 2
            else:
                return

    def parse_body(self, closing: Optional[str] = None) -> Tuple[Dict[str, str], List[HclBlock]]:
        attrs: Dict[str, str] = {}
        blocks: List[HclBlock] = []
        while True:
            self.skip()
            if self.pos >= len(self.text):
                return attrs, blocks
            if closing and self.text[self.pos] == closing:
                self.pos += 1
                return attrs, blocks
            match = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]*|\"(?:[^\"\\]|\\.)*\"").match(self.text, self.pos)
            if not match:
                self.pos += 1
                continue
            word = match.group(0).strip('"')
            self.pos = match.end()
            self.skip(newlines=False)
            if self.pos < len(self.text) and self.text[self.pos] in "=:" and not self.text.startswith("==", self.pos):
                self.pos += 1
                attrs[word] = self.read_expression().strip()
                continue
            labels: List[str] = []
            while True:
                self.skip(newlines=False)
                label = re.compile(r"\"(?:[^\"\\]|\\.)*\"|[A-Za-z_][A-Za-z0-9_\-]*").match(self.text, self.pos)
                if label and self.text[self.pos] != "{":
                    labels.append(label.group(0).strip('"'))
                    self.pos = label.end()
                    continue
                break
            if self.pos < len(self.text) and self.text[self.pos] == "{":
                self.pos += 1
                sub_attrs, sub_blocks = self.parse_body("}")
                blocks.append(HclBlock(word, labels, sub_attrs, sub_blocks))

    def read_expression(self) -> str:
        start = self.pos
        depth = 0
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch == '"':
                self.skip_string()
                continue
            if self.text.startswith("<<", self.pos):
                match = re.compile(r"<<-?([A-Za-z_]+)\n").match(self.text, self.pos)
                if match:
                    end = re.compile(r"^\s*" + match.group(1) + r"\s*$", re.M).search(self.text, match.end())
                    self.pos = end.end() if end else len(self.text)
                    continue
            if self.text.startswith("#", self.pos) and depth == 0:
                break
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif ch == "\n" and depth == 0:
                break
            self.pos += 1
        return self.text[start:self.pos]

    def skip_string(self) -> None:
        self.pos += 1
        depth = 0
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch == "\\":
                self.pos += 2
                continue
            if self.text.startswith("${", self.pos):
                depth += 1
                self.pos += 2
                continue
            if ch == "}" and depth:
                depth -= 1
            elif ch == '"' and depth == 0:
                self.pos += 1
                return
            self.pos += 1


def hcl_map(expr: str) -> Dict[str, str]:
    """Parse a map literal `{ KEY = value, ... }` into raw expressions."""
    expr = expr.strip()
    if not (expr.startswith("{") and expr.endswith("}")):
        return {}
    attrs, _ = HclParser(expr[1:-1]).parse_body()
    return attrs


def hcl_list(expr: str) -> List[str]:
    expr = expr.strip()
    if not (expr.startswith("[") and expr.endswith("]")) or re.match(r"^\[\s*for\b", expr):
        return [expr] if expr else []
    items, depth, current, in_string = [], 0, "", False
    for ch in expr[1:-1]:
        if ch == '"':
            in_string = not in_string
        if not in_string and ch in "([{":
            depth += 1
        elif not in_string and ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0 and not in_string:
            items.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        items.append(current.strip())
    return items


TF_UNRESOLVED_FIX = "Review the module or variable source too, pass --tf-plan-json, or use live mode."
TF_REF = re.compile(r"\b(data\.)?(azurerm_[a-z0-9_]+)\.([A-Za-z0-9_\-]+)((?:\[[^\]]*\])?(?:\.[A-Za-z0-9_]+(?:\[[^\]]*\])?)*)")


def tf_literal(expr: str) -> Optional[str]:
    expr = expr.strip()
    if re.fullmatch(r'"(?:[^"\\$]|\\.|\$(?!\{))*"', expr):
        return expr[1:-1]
    return None


def tf_string(expr: str, labels: Dict[Tuple[str, str], str]) -> str:
    expr = expr.strip()
    if expr.startswith('"') and expr.endswith('"'):
        expr = expr[1:-1]

    def replace(match: re.Match) -> str:
        inner = match.group(1)
        ref = TF_REF.search(inner)
        if ref:
            key = labels.get((ref.group(2), ref.group(3)), f"{ref.group(2)}.{ref.group(3)}")
            return key if ref.group(4).endswith(".name") else "{" + inner.strip() + "}"
        return "{" + inner.strip() + "}"
    return re.sub(r"\$\{([^}]*)\}", replace, expr)


class TerraformModel:
    def __init__(self, model: Model) -> None:
        self.model = model
        self.labels: Dict[Tuple[str, str], str] = {}
        self.types: Dict[Tuple[str, str], str] = {}
        self.blocks: Dict[Tuple[str, str], HclBlock] = {}

    def resource_key(self, block: HclBlock) -> str:
        literal = tf_literal(block.attrs.get("name", ""))
        return literal or f"{block.labels[0]}.{block.labels[1]}"

    def ref(self, expr: str) -> Optional[Tuple[str, str, str]]:
        """Return (terraform type, model key, attribute path) for a direct reference."""
        match = TF_REF.search(expr or "")
        if not match:
            return None
        rtype, label, path = match.group(2), match.group(3), match.group(4)
        key = self.labels.get((rtype, label), f"{rtype}.{label}")
        return rtype, key, path.lstrip(".")

    def ingest(self, blocks: List[Tuple[HclBlock, str]]) -> None:
        resources = [(b, s) for b, s in blocks if b.type in ("resource", "data") and len(b.labels) == 2]
        for block, _ in resources:
            self.labels[(block.labels[0], block.labels[1])] = self.resource_key(block)
            self.types[(block.labels[0], block.labels[1])] = block.labels[0]
            self.blocks[(block.labels[0], block.labels[1])] = block
            if block.type == "resource":
                self.model.resource_types.setdefault(self.resource_key(block).lower(), block.labels[0])
        for block, source in resources:
            self.ingest_resource(block, source)
        for block, source in blocks:
            if block.type == "module":
                for attr, expr in block.attrs.items():
                    ref = self.ref(expr)
                    if ref and ref[0] == "azurerm_user_assigned_identity":
                        self.model.note(f"module {block.labels[0] if block.labels else '?'} receives identity {ref[1]} as `{attr}`; resources inside the module are not resolved.",
                                        "Run static on the module source too, or use live mode.", identity=ref[1])

    def identity_from_principal(self, expr: str, source: str) -> Optional[str]:
        ref = self.ref(expr)
        if not ref:
            return None
        rtype, key, path = ref
        if rtype == "azurerm_user_assigned_identity" and path.endswith("principal_id"):
            self.model.add_identity(Identity(key=key, kind="user", name=key, source=source))
            return key
        if re.match(r"identity(\[0\])?\.principal_id$", path):
            return self.model.system_identity(key, source)
        return None

    def block_of(self, expr: str) -> Optional[HclBlock]:
        match = TF_REF.search(expr or "")
        return self.blocks.get((match.group(2), match.group(3))) if match else None

    def parent_name(self, block: HclBlock, *attrs: str) -> Optional[str]:
        for attr in attrs:
            expr = block.attrs.get(attr, "")
            ref = self.ref(expr)
            if ref:
                return ref[1]
            if tf_literal(expr):
                return tf_literal(expr)
        return None

    def scope(self, expr: str) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
        """(kind, resource name, resource type, child path) of a role assignment scope."""
        ref = self.ref(expr)
        if ref:
            rtype, key, _ = ref
            if rtype in ("azurerm_resource_group",):
                return "resourceGroup", key, None, None
            if rtype in ("azurerm_subscription", "azurerm_client_config"):
                return "subscription", None, None, None
            if rtype == "azurerm_management_group":
                return "managementGroup", key, None, None
            if rtype in ("azurerm_storage_container", "azurerm_storage_queue", "azurerm_storage_table", "azurerm_storage_share",
                         "azurerm_key_vault_secret", "azurerm_key_vault_key", "azurerm_servicebus_queue", "azurerm_servicebus_topic",
                         "azurerm_eventhub"):
                block = self.block_of(expr)
                parent = self.parent_name(block, "storage_account_id", "storage_account_name", "key_vault_id", "namespace_id",
                                          "namespace_name") if block else None
                if parent:
                    return "resource", parent, rtype, f"{parent}/{key}"
            return "resource", key, rtype, None
        return scope_from_ref(tf_literal(expr) or "", "unknown")

    def setting(self, name: str, expr: str) -> Setting:
        setting = Setting(name=name, value=None)
        ref = self.ref(expr)
        stripped = expr.strip()
        if ref and not stripped.startswith('"'):
            rtype, key, path = ref
            if rtype == "azurerm_user_assigned_identity":
                setting.identity_ref = key
            else:
                service = TYPE_SERVICE.get(rtype)
                if service == "storage":
                    for part, sub in (("blob", "storage-blob"), ("queue", "storage-queue"), ("table", "storage-table"), ("file", "storage-file")):
                        if part in path:
                            service = sub
                if service:
                    setting.service, setting.target_name = service, key
            setting.value = f"<{key}.{path}>"
            return setting
        setting.value = tf_string(expr, self.labels)
        return setting

    def ingest_resource(self, block: HclBlock, source: str) -> None:
        rtype = block.labels[0]
        key = self.labels[(rtype, block.labels[1])]
        model = self.model
        if block.type == "data":
            return
        if rtype == "azurerm_user_assigned_identity":
            model.add_identity(Identity(key=key, kind="user", name=key, source=source, resolved=bool(tf_literal(block.attrs.get("name", "")))))
            if not tf_literal(block.attrs.get("name", "")):
                model.note(f"Identity {key} has a computed name; using the Terraform address.", TF_UNRESOLVED_FIX, identity=key)
            return
        if rtype == "azurerm_federated_identity_credential":
            parent_expr = block.attrs.get("parent_id") or block.attrs.get("user_assigned_identity_id") or ""
            ref = self.ref(parent_expr)
            parent = ref[1] if ref else "?"
            if not ref:
                model.note(f"Federated credential {key} has an unresolvable parent identity.", TF_UNRESOLVED_FIX)
            audiences = [tf_string(a, self.labels) for a in hcl_list(block.attrs.get("audience", ""))]
            model.fics.append(Fic(parent, tf_literal(block.attrs.get("name", "")) or block.labels[1],
                                  tf_string(block.attrs.get("issuer", ""), self.labels) or None,
                                  tf_string(block.attrs.get("subject", ""), self.labels) or None,
                                  audiences, False, source))
            return
        if rtype == "azurerm_role_assignment":
            principal = self.identity_from_principal(block.attrs.get("principal_id", ""), source)
            role = tf_literal(block.attrs.get("role_definition_name", "")) or ""
            if not role:
                guid = (tf_string(block.attrs.get("role_definition_id", ""), self.labels).rstrip("/").split("/") or [""])[-1].lower()
                role = ROLE_IDS.get(guid, f"role {guid or '?'}")
            kind, name, scope_type, child = self.scope(block.attrs.get("scope", ""))
            if principal:
                model.grants.append(Grant(principal, role, kind, name, source, scope=scope_type, scope_path=child))
            else:
                model.note(f"Role assignment {block.labels[1]} ({role}) has a principal_id that is not a managed identity in this configuration.", TF_UNRESOLVED_FIX)
            return
        if rtype == "azurerm_cosmosdb_sql_role_assignment":
            principal = self.identity_from_principal(block.attrs.get("principal_id", ""), source)
            role_expr = block.attrs.get("role_definition_id", "")
            guid = tf_string(role_expr, self.labels).rstrip("/").split("/")[-1].lower()
            role = COSMOS_DATA_ROLES.get(guid, "Cosmos DB custom role")
            account_ref = self.ref(block.attrs.get("account_name", "")) or self.ref(block.attrs.get("scope", ""))
            account = account_ref[1] if account_ref else tf_literal(block.attrs.get("account_name", ""))
            if principal:
                model.grants.append(Grant(principal, role, "resource", account, source, plane="cosmos"))
            return
        if rtype == "azurerm_key_vault_access_policy":
            principal = self.identity_from_principal(block.attrs.get("object_id", ""), source)
            vault_ref = self.ref(block.attrs.get("key_vault_id", ""))
            if principal and vault_ref:
                model.grants.append(Grant(principal, "Access policy", "resource", vault_ref[1], source, plane="kv-access-policy"))
            return
        if rtype == "azurerm_key_vault":
            model.vault_rbac[key] = block.attrs.get("enable_rbac_authorization", block.attrs.get("rbac_authorization_enabled", "false")).strip() == "true"
            for policy in [b for b in block.blocks if b.type == "access_policy"]:
                principal = self.identity_from_principal(policy.attrs.get("object_id", ""), source)
                if principal:
                    model.grants.append(Grant(principal, "Access policy", "resource", key, source, plane="kv-access-policy"))
            return
        if rtype == "azurerm_storage_account_customer_managed_key":
            account = self.ref(block.attrs.get("storage_account_id", ""))
            ident = self.ref(block.attrs.get("user_assigned_identity_id", ""))
            if account and ident:
                resource = model.resources.setdefault(account[1], Resource(key=account[1], type="azurerm_storage_account", source=source))
                resource.slots.append(("customer_managed_key.user_assigned_identity_id", ident[1]))
                vault = self.vault_of_key(block.attrs.get("key_vault_key_id", "")) or self.parent_name(block, "key_vault_id")
                if vault:
                    resource.slot_targets["customer_managed_key.user_assigned_identity_id"] = vault
            return
        self.ingest_consumer(block, rtype, key, source)

    def vault_of_key(self, expr: str) -> Optional[str]:
        block = self.block_of(expr)
        if block is not None and block.labels[0] in ("azurerm_key_vault_key", "azurerm_key_vault_secret"):
            return self.parent_name(block, "key_vault_id")
        return None

    def ingest_consumer(self, block: HclBlock, rtype: str, key: str, source: str) -> None:
        model = self.model
        ids: List[str] = []
        system = False
        for ident in [b for b in block.blocks if b.type == "identity"]:
            itype = (tf_literal(ident.attrs.get("type", "")) or "").lower()
            system = system or "systemassigned" in itype.replace(" ", "").replace(",", "")
            for item in hcl_list(ident.attrs.get("identity_ids", "")):
                ref = self.ref(item)
                if ref and ref[0] == "azurerm_user_assigned_identity":
                    ids.append(ref[1])
                else:
                    model.note(f"{key}: identity_ids entry `{item}` cannot be resolved to a user-assigned identity in this configuration.",
                               TF_UNRESOLVED_FIX, resource=key)
        slots: List[Tuple[str, str]] = []

        slot_targets: Dict[str, str] = {}

        def walk(b: HclBlock, prefix: str) -> None:
            for attr, expr in b.attrs.items():
                if attr in ("app_settings", "identity_ids"):
                    continue
                for match in TF_REF.finditer(expr):
                    if match.group(2) == "azurerm_user_assigned_identity":
                        path = f"{prefix}{attr}"
                        slots.append((path, self.labels.get((match.group(2), match.group(3)), match.group(3))))
                        target = None
                        if b.type == "registry":
                            server = self.ref(b.attrs.get("server", ""))
                            target = server[1] if server and server[0] == "azurerm_container_registry" else target_from_value(tf_literal(b.attrs.get("server", "")) or "")
                        elif b.type == "customer_managed_key":
                            target = self.vault_of_key(b.attrs.get("key_vault_key_id", ""))
                        if target:
                            slot_targets[path] = target
            counts: Dict[str, int] = {}
            for child in b.blocks:
                if child.type not in ("identity", "env"):
                    index = counts.get(child.type, 0)
                    counts[child.type] = index + 1
                    walk(child, f"{prefix}{child.type}[{index}].")
        walk(block, "")
        settings: Dict[str, Setting] = {}
        app_settings = block.attrs.get("app_settings", "").strip()
        if app_settings and not app_settings.startswith("{"):
            model.note(f"{key}: app_settings is an expression (`{app_settings.split(chr(10))[0][:60]}`); its keys are not read.",
                       TF_UNRESOLVED_FIX, resource=key)
        for name, expr in hcl_map(app_settings).items():
            settings[name] = self.setting(name, expr)

        def envs(b: HclBlock) -> None:
            for child in b.blocks:
                if child.type == "env" and "name" in child.attrs:
                    name = tf_literal(child.attrs["name"]) or child.attrs["name"]
                    settings[name] = self.setting(name, child.attrs.get("value", child.attrs.get("secret_name", '"secretref"')))
                else:
                    envs(child)
        envs(block)
        for secret in [b for b in block.blocks if b.type == "secret" and "key_vault_secret_id" in b.attrs]:
            ident_ref = self.ref(secret.attrs.get("identity", ""))
            ident_text = tf_literal(secret.attrs.get("identity", "")) or ""
            name = f"secret:{tf_literal(secret.attrs.get('name', '')) or '?'}"
            kv_ref = self.ref(secret.attrs["key_vault_secret_id"])
            settings[name] = Setting(name, "key_vault_secret_id", identity_ref=ident_ref[1] if ident_ref else ("system" if ident_text.lower() == "system" else None),
                                     service="keyvault", target_name=None if not kv_ref else None)
        if not ids and not system and not slots and not settings:
            return
        resource = model.resources.setdefault(key, Resource(key=key, type=rtype, source=source))
        resource.type = rtype
        resource.user_identities = sorted(set(resource.user_identities + ids))
        resource.system_assigned = resource.system_assigned or system
        resource.slots.extend(s for s in slots if s not in resource.slots)
        resource.slot_targets.update(slot_targets)
        resource.settings.update(settings)
        for ident in ids:
            model.add_identity(Identity(key=ident, kind="user", name=ident, source=source))
        if system:
            model.system_identity(key, source)


def tf_plan_blocks(plan: dict) -> List[HclBlock]:
    """Convert `terraform show -json` output into HclBlock trees with raw expressions.

    `configuration` keeps references; a map such as app_settings is a single
    expression there, so its keys and literal values come from `planned_values`.
    """

    def expr_text(expression: Any) -> str:
        if isinstance(expression, dict):
            if "constant_value" in expression:
                return json.dumps(expression["constant_value"])
            if expression.get("references"):
                return expression["references"][0]
        return ""

    planned: Dict[str, dict] = {}
    unknown: Dict[str, dict] = {}

    def collect(module: dict) -> None:
        for res in module.get("resources", []):
            planned[res["address"]] = res.get("values") or {}
        for child in module.get("child_modules", []):
            collect(child)
    collect((plan.get("planned_values") or {}).get("root_module") or {})
    for change in plan.get("resource_changes", []):
        unknown[change["address"]] = (change.get("change") or {}).get("after_unknown") or {}

    def convert(btype: str, labels: List[str], expressions: dict) -> HclBlock:
        attrs: Dict[str, str] = {}
        blocks: List[HclBlock] = []
        for name, value in (expressions or {}).items():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        blocks.append(convert(name, [], item))
            elif isinstance(value, dict) and ({"constant_value", "references"} & set(value) or not value):
                attrs[name] = expr_text(value)
            elif isinstance(value, dict):
                blocks.append(convert(name, [], value))
        return HclBlock(btype, labels, attrs, blocks)

    blocks: List[HclBlock] = []

    def visit(module: dict, prefix: str) -> None:
        for res in module.get("resources", []):
            block = convert("resource" if res.get("mode") == "managed" else "data", [res["type"], res["name"]], res.get("expressions", {}))
            address = prefix + res.get("address", f"{res['type']}.{res['name']}")
            values = planned.get(address, {})
            if isinstance(values.get("name"), str):
                block.attrs["name"] = json.dumps(values["name"])
            settings = dict(values.get("app_settings") or {})
            for key, is_unknown in (unknown.get(address, {}).get("app_settings") or {}).items():
                if is_unknown and key not in settings:
                    settings[key] = "(known after apply)"
            if settings:
                block.attrs["app_settings"] = "{" + "\n".join(f"{json.dumps(k)} = {json.dumps(str(v))}" for k, v in settings.items()) + "}"
            blocks.append(block)
        for name, call in (module.get("module_calls") or {}).items():
            visit(call.get("module") or {}, f"{prefix}module.{name}.")
    visit((plan.get("configuration") or {}).get("root_module") or {}, "")
    return blocks


# --------------------------------------------------------------------------
# Static: code and local settings
# --------------------------------------------------------------------------

CREDENTIAL_PATTERN = re.compile(r"\b(DefaultAzureCredential|ChainedTokenCredential|AzureCliCredential|AzureDeveloperCliCredential|VisualStudioCredential|ManagedIdentityCredential|WorkloadIdentityCredential)\b")
SCOPE_LITERAL = re.compile(r"[\"'](https://[A-Za-z0-9.\-]+(?:/[A-Za-z0-9.\-]*)?/\.default|api://[^\"'\s]+)[\"']")
ENDPOINT_LITERAL = re.compile(r"[\"']((?:https://)?[A-Za-z0-9\-{}]+\.(?:blob|queue|table|dfs|vault|servicebus|documents|database|azconfig|openai|cognitiveservices|search)\.(?:core\.windows\.net|azure\.net|windows\.net|azure\.com|io)[A-Za-z0-9./\-]*)")


def scan_code(root: Path, model: Model, mapping: Dict[str, str]) -> None:
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts) or not path.is_file():
            continue
        if path.suffix.lower() not in CODE_EXTS and path.name not in ("local.settings.json", "appsettings.json", "appsettings.Development.json"):
            continue
        try:
            if path.stat().st_size > 1_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        resource = next((res for prefix, res in sorted(mapping.items(), key=lambda kv: -len(kv[0])) if rel.startswith(prefix.rstrip("/") + "/") or rel == prefix), None)
        if path.name == "local.settings.json":
            scan_local_settings(rel, text, model, resource)
            continue
        if path.name.startswith("appsettings"):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for match in CREDENTIAL_PATTERN.finditer(line):
                detail = match.group(1)
                if detail == "ManagedIdentityCredential" and re.search(r"ManagedIdentityCredential\s*\(\s*\)", line):
                    detail = "ManagedIdentityCredential() (system-assigned)"
                model.code.append(CodeEvidence(rel, number, "credential", detail, resource=resource))
            for match in SCOPE_LITERAL.finditer(line):
                model.code.append(CodeEvidence(rel, number, "scope", match.group(1), service_from_text(match.group(1)), resource))
            for match in ENDPOINT_LITERAL.finditer(line):
                model.code.append(CodeEvidence(rel, number, "endpoint", match.group(1), service_from_text(match.group(1)), resource))


def scan_local_settings(rel: str, text: str, model: Model, resource: Optional[str]) -> None:
    try:
        values = (json.loads(text).get("Values") or {})
    except (json.JSONDecodeError, AttributeError):
        return
    prefixes = {}
    for name, value in values.items():
        prefix, _, prop = name.partition("__")
        if prop:
            prefixes.setdefault(prefix, {})[prop.lower()] = str(value)
    for prefix, props in prefixes.items():
        service = next((CONNECTION_PROPS.get(p) for p in props if CONNECTION_PROPS.get(p)), None)
        service = service or next((service_from_text(v) for v in props.values() if service_from_text(v)), None)
        if service and "credential" not in props:
            model.code.append(CodeEvidence(rel, 0, "local-setting", f"{prefix}__* identity-based connection without __credential (developer identity locally)", service, resource))


# --------------------------------------------------------------------------
# Targets: what each resource reaches, and with which identity
# --------------------------------------------------------------------------

def setting_identity(setting: Optional[Setting], resource: Resource, model: Model) -> Tuple[Optional[str], bool]:
    """Resolve a client ID / resource ID setting to an identity key. Returns (key, explicit)."""
    if setting is None:
        return None, False
    if setting.identity_ref:
        return setting.identity_ref, True
    value = (setting.value or "").strip()
    for identity in model.identities.values():
        if identity.client_id and value.lower() == identity.client_id.lower():
            return identity.key, True
        if identity.resource_id and value.lower() == identity.resource_id.lower():
            return identity.key, True
    if value:
        if len(resource.user_identities) == 1:
            model.note(f"{resource.key}: {setting.name} value cannot be matched to an identity; assuming {resource.user_identities[0]}.",
                       "Confirm the value is that identity's client ID.", resource=resource.key)
            return resource.user_identities[0], True
        model.note(f"{resource.key}: {setting.name} value cannot be matched to an identity.",
                   "Reference the identity's clientId in IaC, or run live mode to match client IDs.", resource=resource.key)
        return "?", True
    return None, False


def default_identity(resource: Resource, model: Model, setting_name: str = "") -> Tuple[str, str]:
    """Identity used by SDK code in this resource, and how it was chosen.

    AZURE_CLIENT_ID wins (DefaultAzureCredential reads it). Otherwise, an app
    setting that holds an attached identity's client ID is assumed to be passed
    to the credential by the code; the one sharing the longest name prefix with
    `setting_name` is chosen. Otherwise the platform uses the system-assigned
    identity.
    """
    key, _ = setting_identity(resource.settings.get("AZURE_CLIENT_ID"), resource, model)
    if key:
        return key, "AZURE_CLIENT_ID"
    candidates = []
    for name, setting in resource.settings.items():
        if "__" in name or name == "AZURE_CLIENT_ID":
            continue
        if setting.identity_ref and setting.identity_ref in resource.user_identities:
            candidates.append((name, setting.identity_ref))
    if candidates:
        def shared(name: str) -> int:
            a, b = name.upper().split("_"), setting_name.upper().split("_")
            count = 0
            while count < min(len(a), len(b)) and a[count] == b[count]:
                count += 1
            return count
        name, ident = max(candidates, key=lambda c: (shared(c[0]), c[0]))
        return ident, f"client ID in {name}, assumed passed by code"
    return f"system:{resource.key}", "default credential"


def derive_targets(model: Model) -> None:
    targets: List[Target] = []
    for resource in model.resources.values():
        groups: Dict[str, Dict[str, Setting]] = {}
        for name, setting in resource.settings.items():
            prefix, sep, prop = name.partition("__")
            if sep and prop:
                groups.setdefault(prefix, {})[prop.lower()] = setting
        grouped = {f"{p}__{k}".lower() for p, props in groups.items() for k in props}
        for prefix, props in groups.items():
            credential = (props.get("credential").value or "").lower() if props.get("credential") else ""
            services = []
            for prop, setting in props.items():
                service = CONNECTION_PROPS.get(prop) if prop in CONNECTION_PROPS else None
                if prop in CONNECTION_PROPS:
                    service = setting.service or service_from_text(setting.value or "") or service
                    if prop == "fullyqualifiednamespace" and "eventhub" in prefix.lower():
                        service = "eventhubs"
                    if service:
                        services.append((service, setting.target_name or target_name_from_endpoint(setting.value or "") or
                                         (setting.value if prop == "accountname" and setting.value and "{" not in setting.value and "<" not in setting.value else None)))
            if not services:
                continue
            ident, explicit = setting_identity(props.get("clientid") or props.get("managedidentityresourceid"), resource, model)
            if ident is None:
                ident = f"system:{resource.key}"
            via = f"{prefix}__*" + (" (credential=managedidentity)" if credential == "managedidentity" else "")
            for service, target_name in dict.fromkeys(services):
                value = " ".join(s.value or "" for s in props.values())
                targets.append(Target(resource.key, service, target_name, ident, via, True, value))
        for name, setting in resource.settings.items():
            if name.lower() in grouped:
                continue
            value = setting.value or ""
            if name.startswith("secret:") and setting.service == "keyvault":
                ident = setting.identity_ref if setting.identity_ref and setting.identity_ref != "system" else f"system:{resource.key}"
                targets.append(Target(resource.key, "keyvault", setting.target_name, ident, f"secret {name[7:]} (Key Vault reference)", True))
                continue
            if "@microsoft.keyvault(" in value.lower():
                kv_ident = next((ident for path, ident in resource.slots if path.lower().endswith("keyvaultreferenceidentity") or path.endswith("key_vault_reference_identity_id")), None)
                targets.append(Target(resource.key, "keyvault", target_name_from_endpoint(value), kv_ident or f"system:{resource.key}",
                                      f"{name} (Key Vault reference)", True))
                continue
            service = setting.service or service_from_text(value)
            if service and service not in ("arm",):
                default_key, how = default_identity(resource, model, name)
                targets.append(Target(resource.key, service, setting.target_name or target_name_from_endpoint(value), default_key,
                                      f"{name} (SDK + {how})", False, value))
        for path, ident in resource.slots:
            lpath = path.lower()
            slot_target = resource.slot_targets.get(path)
            if "encryption" in lpath or "customer_managed_key" in lpath:
                targets.append(Target(resource.key, "keyvault", slot_target, ident, f"{path} (customer-managed key)", True))
            elif "registr" in lpath or "acr" in lpath:
                targets.append(Target(resource.key, "acr", slot_target, ident, f"{path} (image pull)", True))
            elif "kubelet" in lpath:
                targets.append(Target(resource.key, "acr", slot_target, ident, f"{path} (kubelet image pull)", True))
    attributed = set()
    for evidence in model.code:
        if not evidence.service or evidence.kind in ("credential", "local-setting"):
            continue
        if evidence.resource and evidence.resource in model.resources:
            resource = model.resources[evidence.resource]
            key = (resource.key, evidence.service)
            if key in attributed:
                continue
            attributed.add(key)
            ident, how = default_identity(resource, model)
            targets.append(Target(resource.key, evidence.service, None if evidence.kind != "endpoint" else target_name_from_endpoint(evidence.detail),
                                  ident, f"code {evidence.file}:{evidence.line} ({how})", False))
    for target in targets:
        # Event Hubs and Service Bus namespaces share the *.servicebus.* host; the resource type decides.
        rtype = model.resource_types.get((target.target_name or "").lower(), "")
        if target.service == "servicebus" and rtype in ("microsoft.eventhub/namespaces", "azurerm_eventhub_namespace"):
            target.service = "eventhubs"
        if target.identity and target.identity.startswith("system:"):
            model.system_identity(target.resource, model.resources[target.resource].source)
    model.targets = targets


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------

def consumers_of(model: Model, identity: str) -> List[Tuple[str, str]]:
    result = []
    for resource in model.resources.values():
        if identity in resource.user_identities:
            result.append((resource.key, "identity"))
        for path, ident in resource.slots:
            if ident == identity and identity not in resource.user_identities:
                result.append((resource.key, path))
    return result


def grant_covers(grant: Grant, target: Target, model: Model) -> bool:
    if grant.plane == "cosmos":
        if target.service != "cosmos":
            return False
    elif grant.plane == "kv-access-policy":
        if target.service != "keyvault":
            return False
    elif target.service in SERVICES and SERVICES[target.service][2]:
        return False
    elif target.service not in SERVICES or not role_covers(grant.role, target.service):
        return False
    if grant.scope_kind in ("subscription", "managementGroup", "root", "unknown", "resourceGroup"):
        return True
    if not target.target_name or not grant.scope_name or "{" in (grant.scope_name or "") or "{" in (target.target_name or ""):
        return True
    return grant.scope_name.split("/")[0].lower() == target.target_name.lower()


def needed_by(grant: Grant, model: Model) -> List[str]:
    return sorted({t.resource for t in model.targets if t.identity == grant.identity and grant_covers(grant, t, model)})


def run_rules(model: Model) -> List[Finding]:
    findings: List[Finding] = list(model.notes)
    users = [i for i in model.identities.values() if i.kind == "user"]
    for identity in users:
        consumers = consumers_of(model, identity.key)
        names = sorted({c[0] for c in consumers})
        fics = [f for f in model.fics if f.identity == identity.key]
        grants = [g for g in model.grants if g.identity == identity.key]
        if len(names) > 1:
            purposes = []
            for name in names:
                services = sorted({t.service for t in model.targets if t.resource == name and t.identity == identity.key})
                purposes.append(f"{name} → {', '.join(services) or 'no target found'}")
            findings.append(Finding("MIR001", "warning", identity.key, None,
                                    f"Identity is attached to {len(names)} resources: {'; '.join(purposes)}. Every grant on it is usable by all of them.",
                                    "Confirm each consumer's targets are granted (MIR002) and that no consumer needs fewer rights; prefer one identity per purpose."))
        shared = len(names) > 1 or (names and fics)
        if shared:
            for grant in grants:
                users_of_grant = needed_by(grant, model)
                broad = grant.scope_kind in ("subscription", "managementGroup", "root", "resourceGroup")
                privileged = grant.role.lower() in PRIVILEGED_ROLES or grant.role.lower().endswith("data owner")
                if broad or privileged:
                    findings.append(Finding("MIR003", "warning", identity.key, None,
                                            f"{grant.role} at {scope_label(grant)} is held by a shared identity ({', '.join(names)}{' + federated workloads' if fics else ''}).",
                                            "Narrow the scope to the target resource and the least-privileged data role, or move the consumer that needs it to its own identity."))
                elif users_of_grant and set(names) - set(users_of_grant):
                    others = sorted(set(names) - set(users_of_grant))
                    findings.append(Finding("MIR003", "warning" if fics else "info", identity.key, None,
                                            f"{grant.role} at {scope_label(grant)} is needed by {', '.join(users_of_grant)} but also usable by {', '.join(others)}"
                                            f"{' and by federated workloads' if fics else ''}.",
                                            "Accept explicitly in review, or give the other consumers their own identity."))
        for fic in fics:
            audience_ok = all(a.lower() in FIC_AUDIENCES for a in fic.audiences)
            if names:
                findings.append(Finding("MIR004", "warning", identity.key, None,
                                        f"Federated credential {fic.name} lets issuer {fic.issuer or '?'} / subject {fic.subject or '(expression)'} act as this identity, "
                                        f"which is also attached to {', '.join(names)}. It holds every grant: {', '.join(sorted({g.role for g in grants})) or 'none found'}.",
                                        "Use a dedicated identity for the external workload, or confirm in review that it may hold all these grants."))
            if not audience_ok:
                findings.append(Finding("MIR004", "warning", identity.key, None,
                                        f"Federated credential {fic.name} uses audience {', '.join(fic.audiences) or '(none)'} instead of api://AzureADTokenExchange.",
                                        "Use the standard token exchange audience unless the issuer requires another one."))
            if fic.flexible:
                findings.append(Finding("MIR004", "warning", identity.key, None,
                                        f"Federated credential {fic.name} matches subjects by expression (flexible FIC); more workloads than intended may match.",
                                        "Review the claimsMatchingExpression or replace it with exact subjects."))
    # MIR002 / MIR006: targets without a grant
    seen = set()
    unmatched = set()
    for target in model.targets:
        if target.identity is None:
            continue
        if target.identity == "?":
            if (target.resource, target.via) not in unmatched:
                unmatched.add((target.resource, target.via))
                findings.append(Finding("MIR005", "warning", None, target.resource,
                                        f"{target.via} on {target.resource} names a client ID that matches none of the identities attached to it "
                                        f"({', '.join(model.resources[target.resource].user_identities) or 'none'}), so its grants cannot be checked.",
                                        "Reference the identity's clientId in IaC, or run live mode to match client IDs."))
            continue
        key = (target.resource, target.service, target.target_name, target.identity)
        if key in seen:
            continue
        seen.add(key)
        grants = [g for g in model.grants if g.identity == target.identity]
        covering = [g for g in grants if grant_covers(g, target, model)]
        # A child-scoped grant (container, queue, Foundry project) counts when the endpoint points into that child.
        within = [g for g in covering if g.scope_path and any(f"/{part.lower()}" in (target.value or "").lower()
                                                              for part in g.scope_path.split("/")[1:] if len(part) > 2 and part.lower() not in
                                                              ("default", "blobservices", "queueservices", "tableservices", "fileservices",
                                                               "containers", "queues", "tables", "shares", "projects", "agents", "secrets", "keys"))]
        if covering and not within and all(g.scope_path for g in covering):
            ident = model.identities.get(target.identity)
            findings.append(Finding("MIR002", "warning", target.identity, target.resource,
                                    f"{target.resource} reaches {SERVICES[target.service][0]}{' ' + target.target_name if target.target_name else ''} with "
                                    f"{ident.name if ident else target.identity} via {target.via}, but the identity is granted only on "
                                    f"{', '.join(sorted({g.scope_path for g in covering}))}.",
                                    "Confirm the consumer uses only that child resource, or grant the role on the resource it reaches."))
            continue
        if covering:
            continue
        ident = model.identities.get(target.identity)
        label = ident.name if ident else target.identity
        where = f"{SERVICES.get(target.service, (target.service,))[0]}{' ' + target.target_name if target.target_name else ''}"
        if target.identity.startswith("system:") and not model.resources[target.resource].system_assigned:
            continue  # reported by MIR005
        if target.service in SERVICES and SERVICES[target.service][2]:
            findings.append(Finding("MIR006", "info", target.identity, target.resource,
                                    f"{target.resource} reaches {where} with {label} via {target.via}; this needs a non-RBAC grant ({SERVICES[target.service][2]}), which templates rarely show.",
                                    "Verify the grant exists for this identity (see references/review-checklist.md)."))
            continue
        roles = SERVICES.get(target.service, ("", ()))[1]
        findings.append(Finding("MIR002", "error" if target.explicit else "warning", target.identity, target.resource,
                                f"{target.resource} reaches {where} with {label} via {target.via}, but no grant for that identity covers it"
                                f"{' (inferred from a URL; confirm the app uses Entra auth)' if not target.explicit else ''}.",
                                f"Grant {' or '.join(roles[:3])} on the target to {label}, in IaC."))
    # MIR005: identity selection
    for resource in model.resources.values():
        reported = set()
        for target in [t for t in model.targets if t.resource == resource.key and t.identity and t.identity.startswith("system:")]:
            if target.via in reported:
                continue
            reported.add(target.via)
            if not resource.system_assigned and resource.user_identities:
                findings.append(Finding("MIR005", "error", None, resource.key,
                                        f"{target.via} on {resource.key} names no client ID, so the platform requests a token for the system-assigned identity, which is not enabled "
                                        f"(user-assigned: {', '.join(resource.user_identities)}).",
                                        "Set <prefix>__clientId (or AZURE_CLIENT_ID for SDK code) to the intended identity's client ID."))
            elif resource.system_assigned and resource.user_identities:
                findings.append(Finding("MIR005", "warning", None, resource.key,
                                        f"{target.via} on {resource.key} names no client ID and uses the system-assigned identity, although user-assigned identities "
                                        f"({', '.join(resource.user_identities)}) are attached.",
                                        "Confirm the system-assigned identity is intended, or set the client ID explicitly."))
    # MIR007: local development masks identity gaps
    by_file: Dict[str, List[CodeEvidence]] = {}
    for evidence in model.code:
        if evidence.kind == "credential" and evidence.detail in ("DefaultAzureCredential", "ChainedTokenCredential", "AzureCliCredential",
                                                                  "AzureDeveloperCliCredential", "VisualStudioCredential"):
            by_file.setdefault(evidence.file, []).append(evidence)
        if evidence.kind == "local-setting":
            by_file.setdefault(evidence.file, []).append(evidence)
    for file, items in sorted(by_file.items()):
        kinds = sorted({e.detail if e.kind == "credential" else "identity-based connection without __credential" for e in items})
        findings.append(Finding("MIR007", "info", None, items[0].resource, f"{file}: {', '.join(kinds)} runs as the developer locally, so local E2E cannot reveal missing grants for the deployed identity.",
                                "Verify after deployment with the deployed identity (see references/review-checklist.md), and review MIR002 findings."))
    unattributed = sorted({(e.service, e.file) for e in model.code if e.service and not e.resource and e.kind in ("scope", "endpoint")})
    if unattributed:
        services = sorted({s for s, _ in unattributed})
        granted = {s for s in services if any(role_covers(g.role, s) for g in model.grants if g.plane == "rbac" and s in SERVICES and SERVICES[s][1])}
        for service in services:
            files = sorted({f for s, f in unattributed if s == service})
            if service in SERVICES and SERVICES[service][2]:
                findings.append(Finding("MIR006", "info", None, None, f"Code requests {SERVICES[service][0]} tokens ({', '.join(files[:3])}); this needs a non-RBAC grant ({SERVICES[service][2]}).",
                                        "Verify the grant for the identity the code runs as; pass --map <dir>=<resource> to attribute code to a resource."))
            elif service not in granted:
                findings.append(Finding("MIR002", "warning", None, None, f"Code reaches {SERVICES.get(service, (service,))[0]} ({', '.join(files[:3])}) but no identity in scope has a grant for it.",
                                        "Pass --map <dir>=<resource> to attribute the code, then grant the role to that resource's identity."))
    findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.rule, f.identity or "", f.resource or ""))
    return findings


def scope_label(grant: Grant) -> str:
    if grant.scope_kind == "resource":
        return f"{grant.scope_path or grant.scope_name or '?'}"
    return grant.scope_kind + (f" {grant.scope_name}" if grant.scope_name else "")


# --------------------------------------------------------------------------
# Drift (MIR008)
# --------------------------------------------------------------------------

def drift(static: Model, live: Model) -> List[Finding]:
    findings = []
    for ident in [i for i in live.identities.values() if i.kind == "user"]:
        if ident.key not in static.identities:
            continue
        live_consumers = {c[0].lower() for c in consumers_of(live, ident.key)}
        static_consumers = {c[0].lower() for c in consumers_of(static, ident.key) if "{" not in c[0]}
        for extra in sorted(live_consumers - static_consumers):
            findings.append(Finding("MIR008", "warning", ident.key, extra, f"{extra} holds {ident.key} in Azure but not in IaC.",
                                    "Add the attachment to IaC or remove it from the resource."))
        for missing in sorted(static_consumers - live_consumers):
            findings.append(Finding("MIR008", "warning", ident.key, missing, f"IaC attaches {ident.key} to {missing}, but Azure does not show it.",
                                    "Deploy, or remove the stale attachment from IaC."))
        live_grants = {(g.role.lower(), (g.scope_name or "").lower()) for g in live.grants if g.identity == ident.key}
        static_grants = {(g.role.lower(), (g.scope_name or "").lower()) for g in static.grants if g.identity == ident.key}
        for role, scope in sorted(live_grants - static_grants):
            if any(r == role and (not s or "{" in s) for r, s in static_grants):
                continue
            findings.append(Finding("MIR008", "warning", ident.key, None, f"{ident.key} holds {role} on {scope or '(scope)'} in Azure, but IaC does not declare it.",
                                    "Declare the grant in IaC so reviews see it, or remove it."))
        live_fics = {(f.issuer, f.subject) for f in live.fics if f.identity == ident.key}
        static_fics = {(f.issuer, f.subject) for f in static.fics if f.identity == ident.key}
        for issuer, subject in sorted(live_fics - static_fics, key=str):
            findings.append(Finding("MIR008", "warning", ident.key, None, f"Federated credential {issuer} / {subject} exists in Azure but not in IaC.",
                                    "Declare it in IaC or delete it."))
    return findings


# --------------------------------------------------------------------------
# Live collection (read-only az)
# --------------------------------------------------------------------------

KEEP_SETTING = re.compile(r"(__clientid|__credential|__managedidentityresourceid|__accountname|__fullyqualifiednamespace|__accountendpoint|__endpoint|"
                          r"__serviceuri|__blobserviceuri|__queueserviceuri|__tableserviceuri|__vaulturi|__topicendpointuri|^azure_client_id$|^azure_tenant_id$)", re.I)
SECRET_VALUE = re.compile(r"(accountkey=|sharedaccesskey|sig=|password|pwd=|secret=|token=)", re.I)
GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def mask_value(name: str, value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if SECRET_VALUE.search(text):
        return "***"
    if text.lower().startswith("@microsoft.keyvault("):
        match = re.search(r"(VaultName=[^;)]+|SecretUri=https://[^/]+)", text, re.I)
        return f"@Microsoft.KeyVault({match.group(1) if match else '***'})"
    # Service endpoints keep their path (container, queue, project) but never the query string (SAS tokens).
    if KEEP_SETTING.search(name) or GUID.match(text):
        match = re.match(r"^(https?://[^?#]+)", text)
        return match.group(1) if match else text
    match = re.match(r"^(https?://[^?#]+)", text)
    if match and service_from_text(match.group(1)):
        return match.group(1)
    return "***"


def mask_appsettings(data: Any) -> Any:
    if isinstance(data, list):
        return [{"name": item.get("name"), "value": mask_value(str(item.get("name", "")), item.get("value"))} for item in data if isinstance(item, dict)]
    return data


def mask_graph(data: Any) -> Any:
    for row in (data or {}).get("data", []) if isinstance(data, dict) else []:
        for container in row.get("containers") or []:
            for env in container.get("env") or []:
                env["value"] = mask_value(str(env.get("name", "")), env.get("value")) if "value" in env else None
    return data


class AzRunner:
    def __init__(self, replay: Optional[str], record: Optional[str]) -> None:
        self.replay = Path(replay) if replay else None
        self.record = Path(record) if record else None
        self.index: Dict[str, str] = {}
        if self.replay:
            self.index = json.loads((self.replay / "index.json").read_text(encoding="utf-8"))
        if self.record:
            self.record.mkdir(parents=True, exist_ok=True)

    def run(self, key: str, args: List[str], body: Optional[dict] = None, mask: Optional[Callable[[Any], Any]] = None) -> Any:
        if self.replay:
            name = self.index.get(key)
            if name is None:
                return None
            return json.loads((self.replay / name).read_text(encoding="utf-8"))
        az = shutil.which("az")
        if not az:
            raise SystemExit("az not found; install Azure CLI or use --replay.")
        body_file = None
        try:
            if body is not None:
                handle, body_file = tempfile.mkstemp(suffix=".json")
                with os.fdopen(handle, "w", encoding="utf-8") as stream:
                    json.dump(body, stream)
                args = [*args, "--body", f"@{body_file}"]
            env = dict(os.environ, PYTHONIOENCODING="utf-8", AZURE_CORE_ONLY_SHOW_ERRORS="true")
            result = subprocess.run([az, *args, "--output", "json"], capture_output=True, text=True, encoding="utf-8", timeout=600, env=env)
        finally:
            if body_file:
                os.unlink(body_file)
        if result.returncode != 0:
            lines = [line.strip() for line in result.stderr.splitlines() if line.strip()]
            message = next((line for line in lines if line.startswith("ERROR") or "Error" in line), lines[0] if lines else "unknown error")
            raise RuntimeError(f"az {' '.join(args[:3])} failed: {message}")
        data = json.loads(result.stdout) if result.stdout.strip() else None
        if mask:
            data = mask(data)
        if self.record:
            name = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12] + ".json"
            (self.record / name).write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.index[key] = name
            (self.record / "index.json").write_text(json.dumps(self.index, indent=2, sort_keys=True), encoding="utf-8")
        return data


def graph(runner: AzRunner, key: str, subscription: str, query: str, mask: Optional[Callable[[Any], Any]] = None) -> List[dict]:
    rows: List[dict] = []
    skip = None
    page = 0
    while True:
        body: Dict[str, Any] = {"subscriptions": [subscription], "query": query, "options": {"$top": 1000}}
        if skip:
            body["options"]["$skipToken"] = skip
        data = runner.run(f"{key}#{page}", ["rest", "--method", "post", "--url", "/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01"], body, mask)
        if not data:
            return rows
        rows.extend(data.get("data", []))
        skip = data.get("$skipToken")
        page += 1
        if not skip:
            return rows


def parse_scope(scope: str) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
    scope = scope or ""
    if scope in ("/", ""):
        return "root", None, None, None
    if "/providers/Microsoft.Management/managementGroups/" in scope and "/subscriptions/" not in scope:
        return "managementGroup", scope.rstrip("/").split("/")[-1], None, None
    parsed = split_resource_path(scope.rstrip("/"))
    if parsed:
        return "resource", parsed[1], parsed[0], parsed[2]
    if re.match(r"^/subscriptions/[^/]+/resourceGroups/[^/]+/?$", scope, re.I):
        return "resourceGroup", scope.rstrip("/").split("/")[-1], None, None
    return "subscription", scope.rstrip("/").split("/")[-1], None, None


def collect_live(args: argparse.Namespace) -> Model:
    runner = AzRunner(args.replay, args.record)
    sub = args.subscription
    model = Model(origin=f"live subscription {sub}")
    identities = graph(runner, "graph:identities", sub,
                       "resources | where type =~ 'microsoft.managedidentity/userassignedidentities' "
                       "| project id, name, resourceGroup, principalId = tostring(properties.principalId), clientId = tostring(properties.clientId)")
    for row in identities:
        model.add_identity(Identity(key=row["name"], kind="user", name=row["name"], source="live", client_id=row.get("clientId"),
                                    principal_id=row.get("principalId"), resource_id=row["id"], resource_group=row.get("resourceGroup")))
    holders = graph(runner, "graph:holders", sub,
                    "resources | where isnotnull(identity) or type =~ 'microsoft.containerservice/managedclusters' "
                    "| project id, name, type, resourceGroup, identity, kvRef = properties.keyVaultReferenceIdentity, "
                    "encryption = properties.encryption, identityProfile = properties.identityProfile, "
                    "registries = properties.configuration.registries, secrets = properties.configuration.secrets, "
                    "containers = properties.template.containers, acrClientId = properties.siteConfig.acrUserManagedIdentityID",
                    mask_graph)
    by_id = {i.resource_id.lower(): i.key for i in model.identities.values() if i.resource_id}
    by_client = {i.client_id.lower(): i.key for i in model.identities.values() if i.client_id}
    by_principal = {i.principal_id.lower(): i.key for i in model.identities.values() if i.principal_id}
    vaults = graph(runner, "graph:vaults", sub,
                   "resources | where type =~ 'microsoft.keyvault/vaults' | project id, name, resourceGroup, "
                   "rbac = properties.enableRbacAuthorization, accessPolicies = properties.accessPolicies")
    cosmos = graph(runner, "graph:cosmos", sub,
                   "resources | where type =~ 'microsoft.documentdb/databaseaccounts' | project id, name, resourceGroup")
    for row in graph(runner, "graph:eventhubs", sub, "resources | where type =~ 'microsoft.eventhub/namespaces' | project name"):
        model.resource_types[row["name"].lower()] = "microsoft.eventhub/namespaces"
    for row in holders:
        identity = row.get("identity") or {}
        uamis = [by_id.get(k.lower(), resource_ref_from_id(k).name if resource_ref_from_id(k) else k) for k in (identity.get("userAssignedIdentities") or {})]
        resource = Resource(key=row["name"], type=row.get("type", ""), source="live", user_identities=sorted(uamis),
                            system_assigned="systemassigned" in str(identity.get("type", "")).lower().replace(",", "").replace(" ", ""),
                            resource_id=row["id"])
        if resource.system_assigned and identity.get("principalId"):
            key = model.system_identity(resource.key, "live")
            model.identities[key].principal_id = identity["principalId"]
            by_principal[identity["principalId"].lower()] = key
        for path, value in (("keyVaultReferenceIdentity", row.get("kvRef")),
                            ("encryption.identity.userAssignedIdentity", ((row.get("encryption") or {}).get("identity") or {}).get("userAssignedIdentity")),
                            ("identityProfile.kubeletidentity", ((row.get("identityProfile") or {}).get("kubeletidentity") or {}).get("resourceId"))):
            if isinstance(value, str) and value.lower() in by_id:
                resource.slots.append((path, by_id[value.lower()]))
        for index, registry in enumerate(row.get("registries") or []):
            ident = str(registry.get("identity") or "")
            if ident.lower() in by_id:
                path = f"configuration.registries[{index}].identity"
                resource.slots.append((path, by_id[ident.lower()]))
                server = target_from_value(str(registry.get("server") or ""))
                if server:
                    resource.slot_targets[path] = server
        acr_client = str(row.get("acrClientId") or "")
        if acr_client.lower() in by_client:
            resource.slots.append(("siteConfig.acrUserManagedIdentityID", by_client[acr_client.lower()]))
        for secret in row.get("secrets") or []:
            if secret.get("keyVaultUrl"):
                ident = str(secret.get("identity") or "")
                resource.settings[f"secret:{secret.get('name')}"] = Setting(
                    f"secret:{secret.get('name')}", mask_value("keyvault", secret["keyVaultUrl"]),
                    identity_ref=by_id.get(ident.lower()) or ("system" if ident.lower() == "system" else None),
                    service="keyvault", target_name=target_name_from_endpoint(secret["keyVaultUrl"]))
        for container in row.get("containers") or []:
            for env in container.get("env") or []:
                resource.settings[str(env.get("name"))] = Setting(str(env.get("name")), env.get("value"))
        model.resources[resource.key] = resource
    selected = select_identities(model, args)
    relevant = related_resources(model, selected, args)
    for name in sorted(relevant):
        resource = model.resources[name]
        if resource.type.lower() == "microsoft.web/sites":
            group = re.search(r"/resourceGroups/([^/]+)/", resource.resource_id or "", re.I)
            settings = runner.run(f"appsettings:{resource.resource_id}", ["webapp", "config", "appsettings", "list", "--name", resource.key,
                                                                          "--resource-group", group.group(1) if group else "", "--subscription", sub],
                                  mask=mask_appsettings) or []
            for item in settings:
                resource.settings[item["name"]] = Setting(item["name"], item.get("value"))
    for resource in [model.resources[n] for n in relevant]:
        for setting in resource.settings.values():
            value = (setting.value or "").lower()
            if value in by_client:
                setting.identity_ref = by_client[value]
            elif value in by_id:
                setting.identity_ref = by_id[value]
    principals = {model.identities[k].principal_id: k for k in selected if k in model.identities and model.identities[k].principal_id}
    for name in relevant:
        key = f"system:{name}"
        if key in model.identities and model.identities[key].principal_id:
            principals[model.identities[key].principal_id] = key
    for principal, key in sorted(principals.items()):
        assignments = runner.run(f"roles:{principal}", ["role", "assignment", "list", "--assignee-object-id", principal, "--all",
                                                         "--include-inherited", "--fill-principal-name", "false", "--subscription", sub]) or []
        for item in assignments:
            kind, scope_name, scope_type, child = parse_scope(item.get("scope", ""))
            model.grants.append(Grant(key, item.get("roleDefinitionName") or "?", kind, scope_name, "live", scope=item.get("scope"), scope_path=child))
    for vault in vaults:
        model.vault_rbac[vault["name"]] = bool(vault.get("rbac"))
        for policy in vault.get("accessPolicies") or []:
            key = by_principal.get(str(policy.get("objectId", "")).lower())
            if key:
                model.grants.append(Grant(key, "Access policy", "resource", vault["name"], "live", plane="kv-access-policy"))
    for key in sorted(k for k in selected if k in model.identities and model.identities[k].kind == "user"):
        ident = model.identities[key]
        fics = runner.run(f"fic:{ident.resource_id}", ["identity", "federated-credential", "list", "--identity-name", ident.name,
                                                       "--resource-group", ident.resource_group or "", "--subscription", sub]) or []
        for fic in fics:
            model.fics.append(Fic(key, fic.get("name", "?"), fic.get("issuer"), fic.get("subject"), list(fic.get("audiences") or []),
                                  bool(fic.get("claimsMatchingExpression")), "live"))
    derive_targets(model)
    if any(t.service == "cosmos" for t in model.targets):
        for account in cosmos:
            assignments = runner.run(f"cosmos:{account['id']}", ["cosmosdb", "sql", "role", "assignment", "list", "--account-name", account["name"],
                                                               "--resource-group", account["resourceGroup"], "--subscription", sub]) or []
            for item in assignments:
                key = by_principal.get(str(item.get("principalId", "")).lower())
                if key:
                    guid = str(item.get("roleDefinitionId", "")).rstrip("/").split("/")[-1].lower()
                    model.grants.append(Grant(key, COSMOS_DATA_ROLES.get(guid, "Cosmos DB custom role"), "resource", account["name"], "live", plane="cosmos"))
    return model


def select_identities(model: Model, args: argparse.Namespace) -> set:
    users = {k for k, i in model.identities.items() if i.kind == "user"}
    selected = set()
    for value in args.identity or []:
        name = value.rstrip("/").split("/")[-1] if "/userassignedidentities/" in value.lower() else value
        match = next((k for k in users if (model.identities[k].resource_id or "").lower() == value.lower()), None) or \
            next((k for k in users if k.lower() == name.lower()), None)
        if match is None:
            raise SystemExit(f"identity not found: {value}")
        selected.add(match)
    for value in args.resource or []:
        resource = next((r for r in model.resources.values() if r.key.lower() == value.lower()), None)
        if resource is None:
            raise SystemExit(f"resource not found: {value}")
        selected.update(resource.user_identities)
        selected.update(i for _, i in resource.slots)
        selected.add(f"system:{resource.key}")
    if not (args.identity or args.resource):
        selected = {k for k in users if consumers_of(model, k)}
    return selected


def related_resources(model: Model, selected: set, args: argparse.Namespace) -> set:
    """Resources that hold a selected identity, plus the resources named with --resource."""
    related = {r.key for r in model.resources.values() if set(r.user_identities) & selected or any(i in selected for _, i in r.slots)}
    named = {v.lower() for v in (args.resource or [])}
    return related | {r.key for r in model.resources.values() if r.key.lower() in named}


# --------------------------------------------------------------------------
# Static entry point
# --------------------------------------------------------------------------

def collect_static(args: argparse.Namespace) -> Model:
    root = Path(args.path).resolve()
    if not root.exists():
        raise FileNotFoundError(root)
    model = Model(origin=f"static {args.path}")
    params = load_parameters(args.parameters or [])
    files = [root] if root.is_file() else [p for p in sorted(root.rglob("*")) if p.is_file() and not any(part in SKIP_DIRS for part in p.relative_to(root).parts)]
    bicep = [f for f in files if f.suffix == ".bicep"]
    bicep_stems = {(f.parent, f.stem) for f in bicep}
    if args.no_bicep_build and bicep:
        model.note(f"{len(bicep)} Bicep file(s) skipped (--no-bicep-build); only committed ARM JSON is read.", "Drop --no-bicep-build to compile them.")
    if not args.no_bicep_build:
        for file in bicep_entry_files(root, bicep):
            template = compile_bicep(file, model)
            if template:
                ingest_arm(template, model, display_path(file, root), params)
    for file in [f for f in files if f.suffix == ".json"]:
        try:
            data = json.loads(file.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict) or "deploymenttemplate" not in str(data.get("$schema", "")).lower():
            continue
        generator = ((data.get("metadata") or {}).get("_generator") or {}).get("name")
        if generator == "bicep" and (file.parent, file.stem) in bicep_stems and not args.no_bicep_build:
            continue
        ingest_arm(data, model, display_path(file, root), params)
    blocks: List[Tuple[HclBlock, str]] = []
    for file in [f for f in files if f.suffix == ".tf"]:
        attrs, parsed = HclParser(file.read_text(encoding="utf-8", errors="replace")).parse_body()
        blocks.extend((b, display_path(file, root)) for b in parsed)
    if args.tf_plan_json:
        plan = json.loads(Path(args.tf_plan_json).read_text(encoding="utf-8"))
        blocks.extend((b, Path(args.tf_plan_json).name) for b in tf_plan_blocks(plan))
    if blocks:
        TerraformModel(model).ingest(blocks)
    mapping: Dict[str, str] = {}
    for item in args.map or []:
        directory, sep, resource = item.partition("=")
        if not sep or not directory or not resource:
            raise SystemExit(f"invalid --map {item!r}: expected DIR=RESOURCE")
        if resource not in model.resources:
            raise SystemExit(f"--map {item!r}: resource not found: {resource} (known: {', '.join(sorted(model.resources)) or 'none'})")
        mapping[directory] = resource
    if not args.no_code and root.is_dir():
        if not mapping:
            hosts = [r for r in model.resources.values() if r.settings]
            app_dirs = sorted({p.parent.relative_to(root).as_posix() for p in root.rglob("host.json") if not any(part in SKIP_DIRS for part in p.relative_to(root).parts)})
            if len(hosts) == 1 and len(app_dirs) == 1:
                mapping[app_dirs[0]] = hosts[0].key
                model.note(f"Code under {app_dirs[0]}/ attributed to {hosts[0].key} (only app and only Functions project).", "Pass --map <dir>=<resource> to override.")
        scan_code(root, model, mapping)
    derive_targets(model)
    return model


def display_path(file: Path, root: Path) -> str:
    try:
        return file.relative_to(root if root.is_dir() else root.parent).as_posix()
    except ValueError:
        return file.as_posix()


def filter_scope(model: Model, findings: List[Finding], args: argparse.Namespace) -> Tuple[set, List[Finding]]:
    if not (args.identity or args.resource):
        return set(model.identities), findings
    selected = select_identities(model, args)
    related = related_resources(model, selected, args)
    keep = [f for f in findings if (f.identity in selected) or (f.resource in related and f.identity is None) or
            (f.identity and f.identity.startswith("system:") and f.resource in related) or
            (f.rule == "MIR000" and f.identity is None and f.resource is None)]
    return selected | {f"system:{r}" for r in related}, keep


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def render_markdown(model: Model, findings: List[Finding], selected: set) -> str:
    lines = [f"# Managed identity review ({model.origin})", ""]
    users = [i for i in model.identities.values() if i.kind == "user" and i.key in selected]
    if not users:
        lines += ["No user-assigned managed identities found.", ""]
    for ident in sorted(users, key=lambda i: i.key):
        consumers = consumers_of(model, ident.key)
        lines += [f"## Identity `{ident.key}`", ""]
        if ident.client_id:
            lines += [f"Client ID `{ident.client_id}`, principal ID `{ident.principal_id}`.", ""]
        lines += ["| Consumer | Type | Attached via | Uses it for |", "| --- | --- | --- | --- |"]
        for name, via in consumers or [("(none)", "")]:
            resource = model.resources.get(name)
            uses = sorted({f"{t.service}{' ' + t.target_name if t.target_name else ''}" for t in model.targets if t.resource == name and t.identity == ident.key})
            lines.append(f"| {name} | {resource.type if resource else ''} | {via} | {', '.join(uses) or '—'} |")
        grants = [g for g in model.grants if g.identity == ident.key]
        lines += ["", "| Grant | Scope | Needed by |", "| --- | --- | --- |"]
        for grant in grants or [Grant(ident.key, "(none)", "unknown", None, "")]:
            lines.append(f"| {grant.role} | {scope_label(grant) if grant.role != '(none)' else ''} | {', '.join(needed_by(grant, model)) or '—'} |")
        fics = [f for f in model.fics if f.identity == ident.key]
        if fics:
            lines += ["", "| Federated credential | Issuer | Subject | Audience |", "| --- | --- | --- | --- |"]
            for fic in fics:
                lines.append(f"| {fic.name} | {fic.issuer or '?'} | {fic.subject or '(expression)'} | {', '.join(fic.audiences)} |")
        lines.append("")
    system_targets = [t for t in model.targets if t.identity and t.identity.startswith("system:") and t.identity in selected]
    if system_targets:
        lines += ["## System-assigned identities", "", "| Resource | Target | Via |", "| --- | --- | --- |"]
        for target in system_targets:
            lines.append(f"| {target.resource} | {target.service}{' ' + target.target_name if target.target_name else ''} | {target.via} |")
        lines.append("")
    lines += ["## Findings", ""]
    if not findings:
        lines.append("No findings.")
    else:
        lines += ["| Rule | Severity | Identity | Resource | Finding | Fix |", "| --- | --- | --- | --- | --- | --- |"]
        for f in findings:
            lines.append(f"| {f.rule} | {f.severity} | {f.identity or ''} | {f.resource or ''} | {md(f.message)} | {md(f.fix)} |")
    return "\n".join(lines) + "\n"


def md(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def output(model: Model, findings: List[Finding], selected: set, as_json: bool) -> int:
    if as_json:
        data = {
            "origin": model.origin,
            "identities": [asdict(i) for i in model.identities.values() if i.key in selected],
            "resources": [asdict(r) for r in model.resources.values()],
            "grants": [asdict(g) for g in model.grants if g.identity in selected],
            "federatedCredentials": [asdict(f) for f in model.fics if f.identity in selected],
            "targets": [asdict(t) for t in model.targets],
            "findings": [asdict(f) for f in findings],
        }
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        sys.stdout.write(render_markdown(model, findings, selected))
    return 1 if any(f.severity in ("error", "warning") for f in findings) else 0


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--identity", action="append", help="Limit the review to this identity (name or resource ID). Repeatable.")
    common.add_argument("--resource", action="append", help="Review the identities this resource uses and every other consumer of them. Repeatable.")
    common.add_argument("--json", action="store_true", help="Emit the model and findings as JSON.")
    static_opts = argparse.ArgumentParser(add_help=False)
    static_opts.add_argument("--parameters", action="append", help="ARM parameters JSON (or az bicep build-params output). Repeatable.")
    static_opts.add_argument("--map", action="append", help="Attribute code under DIR to RESOURCE: DIR=RESOURCE. Repeatable.")
    static_opts.add_argument("--tf-plan-json", help="Output of `terraform show -json <plan>` to read instead of / in addition to *.tf.")
    static_opts.add_argument("--no-code", action="store_true", help="Skip the source code scan.")
    static_opts.add_argument("--no-bicep-build", action="store_true", help="Do not compile *.bicep; read committed ARM JSON only.")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_static = sub.add_parser("static", parents=[common, static_opts], help="Review IaC, app settings, and code in a directory.")
    p_static.add_argument("path")
    p_live = sub.add_parser("live", parents=[common, static_opts], help="Review a subscription with read-only az calls.")
    p_live.add_argument("--subscription", required=True)
    p_live.add_argument("--static", dest="static_path", help="Also read IaC from this path and report drift (MIR008).")
    p_live.add_argument("--replay", help="Read recorded az output from this directory instead of calling az.")
    p_live.add_argument("--record", help="Record (masked) az output to this directory for later --replay.")
    args = parser.parse_args(argv)
    try:
        if args.command == "static":
            model = collect_static(args)
            findings = run_rules(model)
        else:
            model = collect_live(args)
            findings = run_rules(model)
            if args.static_path:
                static_args = argparse.Namespace(**vars(args))
                static_args.path = args.static_path
                static_model = collect_static(static_args)
                findings += drift(static_model, model)
        selected, findings = filter_scope(model, findings, args)
    except (FileNotFoundError, json.JSONDecodeError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except SystemExit as error:
        if isinstance(error.code, str):
            print(f"error: {error.code}", file=sys.stderr)
            return 2
        raise
    return output(model, findings, selected, args.json)


if __name__ == "__main__":
    sys.exit(main())
