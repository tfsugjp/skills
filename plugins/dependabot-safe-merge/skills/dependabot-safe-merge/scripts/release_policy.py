#!/usr/bin/env python3
"""Select an age-qualified dependency release and emit a fail-closed decision."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from functools import total_ordering
from pathlib import Path
from typing import Any, Iterable

ACTIONS = {"merge", "refresh", "major-plan", "blocked"}
MINIMUM_AGE = timedelta(hours=24)
SEMVER_RE = re.compile(
    r"^[vV]?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
NUGET_RE = re.compile(
    r"^[vV]?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
PEP440_RE = re.compile(
    r"^[vV]?(?:(\d+)!)?(\d+(?:\.\d+)*)"
    r"(?:(?:[-_.]?)(a|alpha|b|beta|c|rc|pre|preview)(?:[-_.]?(\d+))?)?"
    r"(?:(?:-(\d+))|(?:[-_.]?(?:post|rev|r)(?:[-_.]?(\d+))?))?"
    r"(?:[-_.]?dev(?:[-_.]?(\d+))?)?"
    r"(?:\+([a-zA-Z0-9]+(?:[-_.][a-zA-Z0-9]+)*))?$",
    re.IGNORECASE,
)
MAVEN_PRERELEASE = {"alpha", "a", "beta", "b", "milestone", "m", "rc", "cr", "snapshot", "preview", "eap"}
MAVEN_QUALIFIERS = {
    "alpha": -50,
    "a": -50,
    "beta": -40,
    "b": -40,
    "milestone": -30,
    "m": -30,
    "rc": -20,
    "cr": -20,
    "snapshot": -10,
    "": 0,
    "ga": 0,
    "final": 0,
    "release": 0,
    "sp": 10,
}


class PolicyError(ValueError):
    """Raised when policy input cannot be evaluated safely."""


def parse_timestamp(value: Any) -> datetime:
    """Parse an RFC 3339 timestamp and normalize it to UTC."""
    if not isinstance(value, str) or not value.strip():
        raise PolicyError("publication timestamp is missing")
    raw = value.strip()
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as error:
        raise PolicyError("publication timestamp is invalid") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PolicyError("publication timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def prerelease_key(value: str | None) -> tuple[Any, ...]:
    if value is None:
        return (1,)
    parts: list[tuple[int, Any]] = []
    for part in value.split("."):
        if part.isdigit():
            parts.append((0, int(part)))
        else:
            parts.append((1, part.lower()))
    return (0, tuple(parts))


def semver_key(version: str) -> tuple[Any, ...]:
    match = SEMVER_RE.fullmatch(version.strip())
    if not match:
        raise PolicyError(f"non-comparable semantic version: {version}")
    major, minor, patch = (int(match.group(index)) for index in range(1, 4))
    return major, minor, patch, prerelease_key(match.group(4))


def nuget_key(version: str) -> tuple[Any, ...]:
    match = NUGET_RE.fullmatch(version.strip())
    if not match:
        raise PolicyError(f"non-comparable NuGet version: {version}")
    numeric = tuple(int(match.group(index) or 0) for index in range(1, 5))
    return numeric + (prerelease_key(match.group(5)),)


def pep440_key(version: str) -> tuple[Any, ...]:
    match = PEP440_RE.fullmatch(version.strip())
    if not match:
        raise PolicyError(f"non-comparable PEP 440 version: {version}")
    epoch = int(match.group(1) or 0)
    release = tuple(int(part) for part in match.group(2).split("."))
    release = (release + (0, 0, 0, 0))[:4]
    pre_name = (match.group(3) or "").lower()
    pre_number = int(match.group(4) or 0)
    dev_number = match.group(7)
    if not pre_name and dev_number is not None:
        pre = (-1, 0)
    elif pre_name:
        phase = {"a": 0, "alpha": 0, "b": 1, "beta": 1, "c": 2, "rc": 2, "pre": 2, "preview": 2}[pre_name]
        pre = (phase, pre_number)
    else:
        pre = (3, 0)
    post_raw = match.group(5) or match.group(6)
    post = (1, int(post_raw or 0)) if post_raw is not None else (0, 0)
    dev = (0, int(dev_number or 0)) if dev_number is not None else (1, 0)
    local = tuple(re.split(r"[-_.]", (match.group(8) or "").lower()))
    local_key = tuple((0, int(part)) if part.isdigit() else (1, part) for part in local)
    return epoch, release, pre, post, dev, local_key


def maven_tokens(version: str) -> list[str]:
    raw = version.strip().lower()
    if not raw or not re.fullmatch(r"[0-9a-z][0-9a-z._+-]*", raw):
        raise PolicyError(f"non-comparable Maven version: {version}")
    return re.findall(r"\d+|[a-z]+", raw)


def maven_key(version: str) -> tuple[Any, ...]:
    tokens = maven_tokens(version)
    result: list[tuple[int, Any, str]] = []
    for token in tokens:
        if token.isdigit():
            result.append((2, int(token), ""))
        else:
            rank = MAVEN_QUALIFIERS.get(token, 1)
            result.append((1, rank, token if rank == 1 else ""))
    while result and (result[-1] == (2, 0, "") or result[-1] == (1, 0, "")):
        result.pop()
    return tuple(result)


def normalize_ecosystem(value: str) -> str:
    normalized = value.strip().lower()
    aliases = {
        "yarn": "npm",
        "pnpm": "npm",
        "pip": "python",
        "pypi": "python",
        "poetry": "python",
        "uv": "python",
        "gradle": "maven",
        "crates.io": "cargo",
        "github-actions": "actions",
        "github_actions": "actions",
        "gomod": "go",
        "go-modules": "go",
    }
    return aliases.get(normalized, normalized)


def version_key(ecosystem: str, version: str) -> tuple[Any, ...]:
    ecosystem = normalize_ecosystem(ecosystem)
    if ecosystem in {"npm", "cargo", "actions", "go"}:
        return semver_key(version)
    if ecosystem == "nuget":
        return nuget_key(version)
    if ecosystem == "python":
        return pep440_key(version)
    if ecosystem == "maven":
        return maven_key(version)
    raise PolicyError(f"unsupported ecosystem: {ecosystem}")


def is_prerelease(ecosystem: str, version: str) -> bool:
    ecosystem = normalize_ecosystem(ecosystem)
    if ecosystem in {"npm", "cargo", "actions", "go"}:
        match = SEMVER_RE.fullmatch(version.strip())
        if not match:
            raise PolicyError(f"non-comparable semantic version: {version}")
        return match.group(4) is not None
    if ecosystem == "nuget":
        match = NUGET_RE.fullmatch(version.strip())
        if not match:
            raise PolicyError(f"non-comparable NuGet version: {version}")
        return match.group(5) is not None
    if ecosystem == "python":
        match = PEP440_RE.fullmatch(version.strip())
        if not match:
            raise PolicyError(f"non-comparable PEP 440 version: {version}")
        return match.group(3) is not None or match.group(7) is not None
    if ecosystem == "maven":
        return any(token in MAVEN_PRERELEASE for token in maven_tokens(version))
    raise PolicyError(f"unsupported ecosystem: {ecosystem}")


def release_components(ecosystem: str, version: str) -> tuple[int, int]:
    ecosystem = normalize_ecosystem(ecosystem)
    if ecosystem in {"npm", "cargo", "actions", "go"}:
        key = semver_key(version)
        return int(key[0]), int(key[1])
    if ecosystem == "nuget":
        key = nuget_key(version)
        return int(key[0]), int(key[1])
    if ecosystem == "python":
        match = PEP440_RE.fullmatch(version.strip())
        if not match:
            raise PolicyError(f"non-comparable PEP 440 version: {version}")
        values = [int(part) for part in match.group(2).split(".")]
        return values[0], values[1] if len(values) > 1 else 0
    if ecosystem == "maven":
        numeric = [int(token) for token in maven_tokens(version) if token.isdigit()]
        if not numeric:
            raise PolicyError(f"Maven version has no numeric compatibility boundary: {version}")
        return numeric[0], numeric[1] if len(numeric) > 1 else 0
    raise PolicyError(f"unsupported ecosystem: {ecosystem}")


def is_incompatible(ecosystem: str, current: str, target: str, forced: bool = False) -> bool:
    if forced:
        return True
    current_major, current_minor = release_components(ecosystem, current)
    target_major, target_minor = release_components(ecosystem, target)
    if target_major > current_major:
        return True
    return current_major == 0 and target_major == 0 and target_minor > current_minor


@dataclass(frozen=True)
class ReleaseRecord:
    """Normalized release data from a package registry."""

    version: str
    published_at: str | None
    yanked: bool = False
    listed: bool = True
    retracted: bool = False
    deprecated: bool = False
    prerelease: bool | None = None
    mutable: bool = False

    @classmethod
    def from_json(cls, value: Any) -> "ReleaseRecord":
        if not isinstance(value, dict):
            raise PolicyError("release record must be an object")
        version = value.get("version")
        if not isinstance(version, str) or not version.strip():
            raise PolicyError("release version is missing")
        return cls(
            version=version.strip(),
            published_at=value.get("published_at"),
            yanked=bool(value.get("yanked", False)),
            listed=bool(value.get("listed", True)),
            retracted=bool(value.get("retracted", False)),
            deprecated=bool(value.get("deprecated", False)),
            prerelease=value.get("prerelease"),
            mutable=bool(value.get("mutable", False)),
        )


@dataclass
class GateDecision:
    """Machine-readable result returned by the release policy."""

    action: str
    ecosystem: str
    package: str
    eligible_version: str | None = None
    published_at: str | None = None
    update_kind: str | None = None
    refresh_required: bool = False
    reasons: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        if self.action not in ACTIONS:
            raise AssertionError(f"invalid action: {self.action}")
        return asdict(self)


def blocked(ecosystem: str, package: str, reason: str) -> GateDecision:
    return GateDecision(action="blocked", ecosystem=ecosystem, package=package, reasons=[reason])


def select_eligible_release(
    ecosystem: str,
    records: Iterable[ReleaseRecord],
    now: datetime,
) -> ReleaseRecord:
    cutoff = now - MINIMUM_AGE
    candidates: list[tuple[tuple[Any, ...], ReleaseRecord, datetime]] = []
    for record in records:
        if record.yanked or record.retracted or not record.listed or record.deprecated:
            continue
        if record.mutable:
            raise PolicyError(f"mutable release identifier is not verifiable: {record.version}")
        published = parse_timestamp(record.published_at)
        inferred_prerelease = is_prerelease(ecosystem, record.version)
        if record.prerelease is True or inferred_prerelease:
            continue
        key = version_key(ecosystem, record.version)
        if published > now:
            raise PolicyError(f"release publication time is in the future: {record.version}")
        if published <= cutoff:
            candidates.append((key, record, published))
    if not candidates:
        raise PolicyError("no stable release has been public for at least 24 hours")
    _, selected, _ = max(candidates, key=lambda item: item[0])
    return selected


def evaluate(payload: Any) -> GateDecision:
    if not isinstance(payload, dict):
        return blocked("", "", "input must be a JSON object")
    ecosystem = normalize_ecosystem(str(payload.get("ecosystem", "")))
    package = str(payload.get("package", "")).strip()
    current = str(payload.get("current_version", "")).strip()
    proposed = str(payload.get("proposed_version", "")).strip()
    try:
        if not package:
            raise PolicyError("package is required")
        if not current or not proposed:
            raise PolicyError("current_version and proposed_version are required")
        now = parse_timestamp(payload.get("now") or datetime.now(timezone.utc).isoformat())
        records = [ReleaseRecord.from_json(item) for item in payload.get("releases", [])]
        if not records:
            raise PolicyError("at least one release record is required")
        selected = select_eligible_release(ecosystem, records, now)
        selected_key = version_key(ecosystem, selected.version)
        current_key = version_key(ecosystem, current)
        proposed_key = version_key(ecosystem, proposed)
        if proposed_key > selected_key:
            raise PolicyError("pull request target is newer than the 24-hour eligible release")
        if selected_key <= current_key:
            raise PolicyError("no eligible upgrade is newer than the current version")
        incompatible = is_incompatible(
            ecosystem,
            current,
            selected.version,
            bool(payload.get("compatibility_boundary", False)),
        )
        selected_published = parse_timestamp(selected.published_at).isoformat().replace("+00:00", "Z")
        update_kind = "major" if incompatible else ("refresh" if proposed_key < selected_key else "compatible")
        if incompatible:
            return GateDecision(
                action="major-plan",
                ecosystem=ecosystem,
                package=package,
                eligible_version=selected.version,
                published_at=selected_published,
                update_kind="major",
                refresh_required=proposed_key < selected_key,
                reasons=["major or compatibility boundary requires source review and an implementation plan"],
            )
        if proposed_key < selected_key:
            return GateDecision(
                action="refresh",
                ecosystem=ecosystem,
                package=package,
                eligible_version=selected.version,
                published_at=selected_published,
                update_kind=update_kind,
                refresh_required=True,
                reasons=["pull request does not target the newest 24-hour eligible stable release"],
            )
        return GateDecision(
            action="merge",
            ecosystem=ecosystem,
            package=package,
            eligible_version=selected.version,
            published_at=selected_published,
            update_kind="compatible",
            reasons=["release policy passed; pull request gates must still be evaluated"],
        )
    except (PolicyError, TypeError) as error:
        return blocked(ecosystem, package, str(error))


def load_payload(path: str | None) -> Any:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="JSON input file; defaults to standard input")
    args = parser.parse_args(argv)
    try:
        result = evaluate(load_payload(args.input))
    except (OSError, json.JSONDecodeError) as error:
        result = blocked("", "", f"invalid input: {error.__class__.__name__}")
    json.dump(result.to_json(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result.action != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
