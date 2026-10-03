#!/usr/bin/env python3
"""Normalize saved registry metadata into ReleaseRecord JSON objects."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

FULL_SEMVER = re.compile(
    r"^[vV]?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


class MetadataError(ValueError):
    """Raised when registry metadata cannot be normalized safely."""


def timestamp(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        parsed = datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc)
        return parsed.isoformat().replace("+00:00", "Z")
    if not isinstance(value, str):
        raise MetadataError("publication timestamp has an unsupported type")
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as error:
        raise MetadataError("publication timestamp is invalid") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MetadataError("publication timestamp must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def record(
    version: Any,
    published_at: Any,
    *,
    yanked: Any = False,
    listed: Any = True,
    retracted: Any = False,
    deprecated: Any = False,
    prerelease: Any = None,
    mutable: Any = False,
) -> dict[str, Any]:
    if not isinstance(version, str) or not version.strip():
        raise MetadataError("registry record is missing a version")
    result: dict[str, Any] = {
        "version": version.strip(),
        "published_at": timestamp(published_at),
        "yanked": bool(yanked),
        "listed": bool(listed),
        "retracted": bool(retracted),
        "deprecated": bool(deprecated),
        "mutable": bool(mutable),
    }
    if prerelease is not None:
        result["prerelease"] = bool(prerelease)
    return result


def normalize_npm(payload: dict[str, Any], package: str) -> list[dict[str, Any]]:
    versions = payload.get("versions")
    times = payload.get("time", {})
    if not isinstance(versions, dict) or not isinstance(times, dict):
        raise MetadataError("npm packument must contain versions and time objects")
    output = []
    for version, metadata in versions.items():
        metadata = metadata if isinstance(metadata, dict) else {}
        output.append(
            record(
                version,
                times.get(version),
                deprecated=bool(metadata.get("deprecated")),
            )
        )
    return output


def nuget_leaves(items: Iterable[Any]) -> Iterable[dict[str, Any]]:
    for item in items:
        if not isinstance(item, dict):
            continue
        nested = item.get("items")
        if isinstance(nested, list):
            yield from nuget_leaves(nested)
        if isinstance(item.get("catalogEntry"), dict):
            yield item


def normalize_nuget(payload: dict[str, Any], package: str) -> list[dict[str, Any]]:
    items = payload.get("items")
    if not isinstance(items, list):
        raise MetadataError("NuGet registration must contain an items array")
    output = []
    for leaf in nuget_leaves(items):
        catalog = leaf["catalogEntry"]
        output.append(
            record(
                catalog.get("version"),
                catalog.get("published") or leaf.get("published"),
                listed=leaf.get("listed", catalog.get("listed", True)),
                deprecated=bool(catalog.get("deprecation")),
            )
        )
    return output


def strip_archive_suffix(filename: str) -> str:
    for suffix in (".tar.gz", ".tar.bz2", ".tar.xz", ".whl", ".zip", ".tgz"):
        if filename.lower().endswith(suffix):
            return filename[: -len(suffix)]
    return filename.rsplit(".", 1)[0]


def python_file_version(filename: str, package: str) -> str:
    base = strip_archive_suffix(filename.rsplit("/", 1)[-1])
    normalized_package = re.sub(r"[-_.]+", "-", package).lower()
    if filename.lower().endswith(".whl"):
        parts = base.split("-")
        if len(parts) >= 2 and re.sub(r"[-_.]+", "-", parts[0]).lower() == normalized_package:
            return parts[1]
    prefix_patterns = {
        package + "-",
        package.replace("-", "_") + "-",
        package.replace("_", "-") + "-",
        normalized_package + "-",
    }
    for prefix in sorted(prefix_patterns, key=len, reverse=True):
        if base.lower().startswith(prefix.lower()):
            return base[len(prefix) :]
    raise MetadataError("Python file version cannot be determined without a version field")


def normalize_python(payload: dict[str, Any], package: str) -> list[dict[str, Any]]:
    files = payload.get("files")
    if not isinstance(files, list):
        raise MetadataError("Python Simple JSON must contain a files array")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in files:
        if not isinstance(item, dict):
            continue
        version = item.get("version")
        if not isinstance(version, str):
            filename = item.get("filename")
            if not isinstance(filename, str):
                raise MetadataError("Python file is missing filename and version")
            version = python_file_version(filename, package)
        grouped.setdefault(version, []).append(item)
    output = []
    for version, artifacts in grouped.items():
        upload_times = [timestamp(item.get("upload-time") or item.get("upload_time")) for item in artifacts]
        known_times = [item for item in upload_times if item is not None]
        published = max(known_times) if len(known_times) == len(artifacts) and known_times else None
        all_yanked = all(bool(item.get("yanked", False)) for item in artifacts)
        output.append(record(version, published, yanked=all_yanked))
    return output


def normalize_maven(payload: dict[str, Any], package: str) -> list[dict[str, Any]]:
    response = payload.get("response", payload)
    docs = response.get("docs") if isinstance(response, dict) else None
    if not isinstance(docs, list):
        raise MetadataError("Maven search metadata must contain response.docs")
    output = []
    for item in docs:
        if not isinstance(item, dict):
            continue
        version = item.get("v") or item.get("version")
        output.append(record(version, item.get("timestamp") or item.get("published")))
    return output


def normalize_cargo(payload: dict[str, Any], package: str) -> list[dict[str, Any]]:
    versions = payload.get("versions")
    if not isinstance(versions, list):
        raise MetadataError("Cargo metadata must contain a versions array")
    return [
        record(
            item.get("num") or item.get("version"),
            item.get("created_at") or item.get("published_at"),
            yanked=item.get("yanked", False),
        )
        for item in versions
        if isinstance(item, dict)
    ]


def normalize_go(payload: Any, package: str) -> list[dict[str, Any]]:
    values = payload.get("versions", payload) if isinstance(payload, dict) else payload
    if not isinstance(values, list):
        values = [values]
    output = []
    for item in values:
        if not isinstance(item, dict):
            continue
        retracted = item.get("Retracted", item.get("retracted", False))
        output.append(
            record(
                item.get("Version") or item.get("version"),
                item.get("Time") or item.get("time"),
                retracted=bool(retracted),
            )
        )
    return output


def normalize_actions(payload: Any, package: str) -> list[dict[str, Any]]:
    releases = payload.get("releases", payload) if isinstance(payload, dict) else payload
    if not isinstance(releases, list):
        raise MetadataError("GitHub Actions metadata must be a release array")
    output = []
    for item in releases:
        if not isinstance(item, dict) or item.get("draft", False):
            continue
        tag = item.get("tag_name")
        if not isinstance(tag, str):
            raise MetadataError("GitHub Actions release is missing tag_name")
        mutable = FULL_SEMVER.fullmatch(tag.strip()) is None
        output.append(
            record(
                tag,
                item.get("published_at") or item.get("created_at"),
                prerelease=item.get("prerelease", False),
                mutable=mutable,
            )
        )
    return output


NORMALIZERS = {
    "npm": normalize_npm,
    "yarn": normalize_npm,
    "pnpm": normalize_npm,
    "nuget": normalize_nuget,
    "python": normalize_python,
    "pip": normalize_python,
    "pypi": normalize_python,
    "poetry": normalize_python,
    "uv": normalize_python,
    "maven": normalize_maven,
    "gradle": normalize_maven,
    "cargo": normalize_cargo,
    "go": normalize_go,
    "gomod": normalize_go,
    "actions": normalize_actions,
    "github-actions": normalize_actions,
}


def normalize(ecosystem: str, package: str, payload: Any) -> dict[str, Any]:
    key = ecosystem.strip().lower()
    if key not in NORMALIZERS:
        raise MetadataError(f"unsupported ecosystem: {key}")
    if not package.strip():
        raise MetadataError("package is required")
    if not isinstance(payload, (dict, list)):
        raise MetadataError("registry payload must be an object or array")
    releases = NORMALIZERS[key](payload, package.strip())
    if not releases:
        raise MetadataError("registry payload contains no releases")
    return {"ecosystem": key, "package": package.strip(), "releases": releases}


def load_payload(path: str | None) -> Any:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecosystem", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--input", help="JSON input file; defaults to standard input")
    args = parser.parse_args(argv)
    try:
        result = normalize(args.ecosystem, args.package, load_payload(args.input))
    except (MetadataError, OSError, json.JSONDecodeError) as error:
        result = {"error": str(error) if isinstance(error, MetadataError) else f"invalid input: {error.__class__.__name__}"}
        json.dump(result, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 2
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
