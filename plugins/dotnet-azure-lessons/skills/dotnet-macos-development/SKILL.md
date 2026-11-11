---
name: dotnet-macos-development
description: 'Rules for building, testing, packaging, and debugging .NET and Azure projects on macOS, learned from failures that appeared only on a Mac. Use on macOS or Apple silicon when installing or selecting a .NET SDK (mise, Homebrew, DOTNET_ROOT), running SQL or other Linux containers, writing shell scripts or commands for zsh and the system bash, investigating a crash with native macOS frames (Avalonia, AppKit), building or inspecting a .pkg, using Keychain-backed sign-in (MSAL, az, gh, DefaultAzureCredential), publishing for osx-arm64, or verifying Windows or Linux behavior from a Mac.'
---

# .NET Development on macOS

Rules that hold on Windows and Linux runners fail in specific ways on a Mac. Apply these when the work runs on macOS; the other skills in this plugin still apply.

## When not to use

- Permission or sandbox denials in an agent session: `agent-sandbox-troubleshooting`.
- Choosing and translating container commands (Apple `container`, Docker fallback): `native-container-cli`.
- The Azure SQL Database container itself: the `azuresql-db-*` skills, when installed.
- Intune manifest fields for macOS apps: `relaypublisher-manifest`.

## Rules

### 1. Select the SDK by architecture and verify with a build

- **Rule:** On Apple silicon, point `DOTNET_ROOT` (and `DOTNET_ROOT_ARM64` when set) at the arm64 install; use `DOTNET_ROOT_X64` only for an x64 install. When a version manager (mise) owns the SDK, pin a major version, not `latest` or `lts`, and resolve the patch at install time. An SDK consolidation does not change any project's target framework or `global.json`. Verify with `dotnet build` and `dotnet test` of a real project, not `dotnet --info` alone, and do not hide a slow or broken environment by raising timeouts.
- **Check:** `dotnet --info` shows the expected RID (`osx-arm64`) and base path, and a project builds and tests with that SDK.
- **Why:** A consolidation plan pointed an x64 variable at an arm64 install and passed its check on `dotnet --info` alone; both were caught in plan review.

### 2. Run containers natively on arm64

- **Rule:** Let the runtime select the image's arm64 variant. Do not force `amd64` under Rosetta for a database engine unless the image has no arm64 build, and then say that emulation is in use. Give a SQL container enough memory (4 GB was needed). Libraries that need a Docker API endpoint (Testcontainers) do not work with a runtime that has none; start the container yourself and pass its connection string through the test's environment variable.
- **Check:** The image inspection shows `arm64`; the integration tests name the connection-string variable they used.
- **Why:** An Azure SQL image started as amd64 under Rosetta crashed later with a null-pointer fault and was stable when recreated as arm64.

### 3. Write shell for zsh and the system tools

- **Rule:** Single-quote any argument that contains `?`, `*`, or `[` (API paths with query strings); zsh treats them as glob patterns and fails with `no matches found`. Single-quote values that contain `!` or `$` (passwords) in commands you run or document, or pass them through an environment variable. Scripts that may run under `/bin/bash` (3.2) do not use `mapfile`, associative arrays, or `grep -P`; use `while read` loops and `grep -E`. Pass `mktemp` an explicit template under `$TMPDIR` (`mktemp -d "$TMPDIR/work.XXXXXX"`) so the location does not depend on the platform's default. Do not rely on GNU-only options of `sed`, `date`, or `base64`.
- **Check:** The script runs with `/bin/bash` on macOS and with bash on Linux; commands with query strings are quoted.
- **Why:** A `gh api` path with `?sha=` failed with `no matches found`, a script using `mapfile` and `grep -P` failed on macOS, a documented `sqlcmd` command broke on a password ending in `!` (the exact mechanism was not confirmed), and a bare `mktemp -d` in an agent session created its directory outside the session's writable temporary directory.

### 4. Locate a macOS-only crash by its native frames

- **Rule:** When a crash happens only on macOS, read the crash report's native frames to find the layer (UI framework native code, AppKit, runtime) before changing application code. Search that dependency's release notes and issues for the symbol, and prefer a patch update over a workaround. Then repeat the user's exact UI path on the real screen with the updated build.
- **Check:** The report names the faulting layer and symbol, the dependency version that fixes it, and the UI path that was repeated.
- **Why:** An application crashed when a live-region text became empty; the fault was in the UI framework's macOS accessibility layer and a patch release fixed it with no application change.

### 5. Verify packages with native tools, and validate before the first side effect

- **Rule:** A `.pkg` is a xar archive. Verify what the code derives from it (bundle identifiers, versions, architectures, compression) against `pkgutil` and `xar` output for the same file, including a package with several bundles. Platform-specific properties are not interchangeable: validate everything the result or report needs before the first upload or API write, so that a missing macOS property cannot fail after the remote change succeeded. Keep API version choices (v1.0 or beta per resource type) identical in the code and the documentation table. Say in the install guide when a download is unsigned or not notarized and which install path avoids the Gatekeeper warning.
- **Check:** Parser output matches `pkgutil --expand` or `xar -tf` for a single-bundle and a multi-bundle package; a publish with a missing property fails before any remote call.
- **Why:** A TOC parser mishandled a compression format, a publish threw on a property macOS manifests do not have after the upload had succeeded, and a documented API version contradicted the code.

### 6. Expect Keychain-backed credentials, and pin the credential chain

- **Rule:** MSAL token caches, `gh`, and the git credential helper use the Keychain on macOS; a first run can raise a Keychain prompt, and an agent session may be unable to answer it. `az` needs its configuration directory writable to refresh tokens. Do not delete Keychain items or token caches to "reset" sign-in without asking. Do not depend on the resolution order of `DefaultAzureCredential`: select the credential explicitly, or set `AZURE_TOKEN_CREDENTIALS`, and state which identity local runs use; a call that works as the signed-in developer proves nothing about the deployed identity.
- **Check:** Setup documentation mentions the Keychain prompt; the design states the credential used locally and in the deployed environment.
- **Why:** Sign-in checks stalled on a Keychain prompt, an expired `az` session file could not be refreshed from the agent session, and a design had to fix the credential chain because its order differs by environment.

### 7. Name where other-OS behavior is verified

- **Rule:** Windows- and Linux-only behavior (cmd.exe quoting, Win32 packaging, case-sensitive paths, Linux containers in CI) cannot be confirmed on a Mac. Name the CI job that exercises it (`windows-latest`, `ubuntu-latest`), read that job's result, and record it in the PR. When publishing, build each runtime identifier the release lists (`osx-arm64` included) and run the published macOS binary once. macOS and Windows runners are billed at a higher rate in private repositories: when the user limits them, keep those jobs to the default branch or releases, and when hosted CI is unavailable run the workflow's steps locally and say which jobs did not run.
- **Check:** The PR states, per OS, whether the behavior was observed locally, in a named CI job, or not at all.
- **Why:** Windows behavior was verified only through a `windows-latest` job after local reproduction proved impossible, and the user asked to restrict macOS and Windows pull-request builds because of runner cost.

### 8. Judge desktop UI on the real macOS screen

- **Rule:** For a desktop UI change (Avalonia, MAUI), headless tests cover logic only. Launch the Release build on macOS, follow the changed path, and judge focus, keyboard confirmation, and layout from screenshots (`dotnet-testing`, "Judge UI changes from screenshots"). Close unrelated windows that can intercept UI automation before a full UI test run.
- **Check:** The report lists the build configuration, the path followed, and a pass or fail per screenshot.
- **Why:** Focus did not return to the expected control after confirming with Enter, and another window on screen interfered with UI automation during a full test run.
