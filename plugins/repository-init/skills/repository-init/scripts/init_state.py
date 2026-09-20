#!/usr/bin/env python3
"""Manage repository-init progress without editing repository policy files."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile

MARKER = ".repository-init.json"
LOCK = ".repository-init.lock"
LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "LICENCE.md", "LICENCE.txt", "COPYING", "COPYING.md", "COPYING.txt")
LOCK_FIELDS = {"version", "pid", "created_utc", "token"}
MIT_LICENSE_NAMES = {"mit", "mit license", "the mit license"}


class StateError(ValueError):
    """The saved decision cannot be safely used or changed."""


def inspect(root: Path) -> dict:
    if not root.is_dir():
        raise StateError("The target directory must already exist.")
    path = root / MARKER
    if path.is_symlink():
        raise StateError("The initialization record must not be a symbolic link.")
    if not path.exists():
        return {"status": "missing"}
    try:
        state = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StateError("Cannot read initialization record; preserve it for explicit repair.") from error
    if not isinstance(state, dict) or set(state) != {"schema_version", "status", "license", "language_profile"}:
        raise StateError("Invalid initialization record fields; no automatic repair is performed.")
    if type(state["schema_version"]) is not int or state["schema_version"] != 1:
        raise StateError("Unsupported initialization record version.")
    if state["status"] not in ("in_progress", "complete"):
        raise StateError("Invalid initialization status.")
    validate_decision(state["license"], state["language_profile"])
    return state


def normalize_license_name(license_name: str) -> str:
    if not isinstance(license_name, str) or not license_name.strip():
        raise StateError("A resolved license identifier or name is required.")
    if any(ord(character) < 32 for character in license_name):
        raise StateError("The license name must be a single line.")
    normalized = " ".join(license_name.split())
    if normalized.casefold() in MIT_LICENSE_NAMES:
        return "MIT"
    return normalized


def validate_decision(license_name: str, profile: str) -> str:
    license_name = normalize_license_name(license_name)
    if profile not in ("mit", "non-mit"):
        raise StateError("The language profile must be mit or non-mit.")
    if (license_name == "MIT") != (profile == "mit"):
        raise StateError("Use the mit profile only for the MIT license identifier.")
    return license_name


def _read_lock(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StateError("The lock is unreadable; inspect it and remove it manually only after confirming no initializer is running.") from error
    if not isinstance(payload, dict) or set(payload) != LOCK_FIELDS:
        raise StateError("The lock format is invalid; inspect it and remove it manually only after confirming no initializer is running.")
    if payload["version"] != 1 or type(payload["pid"]) is not int or payload["pid"] <= 0:
        raise StateError("The lock metadata is invalid; inspect it and remove it manually only after confirming no initializer is running.")
    if not isinstance(payload["created_utc"], str) or not isinstance(payload["token"], str) or not re.fullmatch(r"[0-9a-f]{32}", payload["token"]):
        raise StateError("The lock metadata is invalid; inspect it and remove it manually only after confirming no initializer is running.")
    return payload


def _process_is_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return ctypes.get_last_error() == 5  # ERROR_ACCESS_DENIED still means the process exists.
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as error:
        return error.errno != errno.ESRCH
    return True


def recover_lock(root: Path, token: str) -> dict:
    path = root / LOCK
    if not path.is_file() or path.is_symlink():
        raise StateError("No recoverable lock exists.")
    payload = _read_lock(path)
    if token != payload["token"]:
        raise StateError("The recovery token does not match the current lock.")
    if _process_is_alive(payload["pid"]):
        raise StateError("The lock owner is still running; do not recover an active lock.")
    # The token check is repeated immediately before removal so a replacement lock is not removed.
    current = _read_lock(path)
    if current["token"] != token:
        raise StateError("The lock changed during recovery; inspect it before retrying.")
    path.unlink()
    return {"status": "lock_recovered", "token": token}


@contextmanager
def exclusive(root: Path):
    path = root / LOCK
    payload = {
        "version": 1,
        "pid": os.getpid(),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "token": secrets.token_hex(16),
    }
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        if path.is_symlink():
            raise StateError("The lock must not be a symbolic link; inspect it before explicit repair.") from error
        existing = _read_lock(path)
        if _process_is_alive(existing["pid"]):
            raise StateError("Another state operation is running; do not remove its lock.") from error
        raise StateError(f"A stale lock exists; run recover-lock with token {existing['token']} after confirming the owner is stopped.") from error
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            descriptor = None
            json.dump(payload, stream, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            current = _read_lock(path)
        except StateError:
            pass
        else:
            if current["token"] == payload["token"]:
                path.unlink()


def save(root: Path, state: dict) -> None:
    """Replace the record atomically; a failed write leaves the previous record intact."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=root, prefix=".repository-init-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, root / MARKER)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def begin(root: Path, license_name: str, profile: str) -> dict:
    state = inspect(root)
    if state["status"] == "complete":
        return state
    license_name = validate_decision(license_name, profile)
    with exclusive(root):
        state = inspect(root)
        if state["status"] == "complete":
            return state
        if state["status"] == "in_progress":
            if normalize_license_name(state["license"]) != license_name or state["language_profile"] != profile:
                raise StateError("Saved decisions differ. Resume with them or request explicit reconfiguration.")
            return state
        state = {"schema_version": 1, "status": "in_progress", "license": license_name, "language_profile": profile}
        save(root, state)
        return state


def complete(root: Path) -> dict:
    state = inspect(root)
    if state["status"] == "complete":
        return state
    if state["status"] == "missing":
        raise StateError("Resolve and save initialization decisions before completing.")
    with exclusive(root):
        state = inspect(root)
        if state["status"] == "complete":
            return state
        if state["status"] != "in_progress":
            raise StateError("Initialization state changed; inspect it before retrying.")
        for name in ("AGENTS.md", "SECURITY.md"):
            path = root / name
            if not path.is_file() or not path.read_bytes().strip():
                raise StateError(f"A nonempty {name} is required before completion.")
        if not any((root / name).is_file() and (root / name).read_bytes().strip() for name in LICENSE_NAMES):
            raise StateError("A nonempty root LICENSE/LICENCE/COPYING file (.md or .txt also accepted) is required.")
        # The invoking agent must verify meaning, language, and preservation first.
        state = {**state, "status": "complete"}
        save(root, state)
        return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("inspect", "begin", "complete", "recover-lock"):
        subparser = commands.add_parser(command)
        subparser.add_argument("--root", type=Path, required=True)
        if command == "begin":
            subparser.add_argument("--license", required=True)
            subparser.add_argument("--profile", choices=("mit", "non-mit"), required=True)
        elif command == "recover-lock":
            subparser.add_argument("--token", required=True)
    args = parser.parse_args()
    try:
        root = args.root.expanduser().resolve()
        if args.command == "begin":
            state = begin(root, args.license, args.profile)
        elif args.command == "complete":
            state = complete(root)
        elif args.command == "recover-lock":
            state = recover_lock(root, args.token)
        else:
            state = inspect(root)
        print(json.dumps(state, ensure_ascii=True))
        return 0
    except (StateError, OSError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
