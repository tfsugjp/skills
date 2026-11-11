---
name: dotnet-macos-development
description: 'Guidance for .NET and Azure work with macOS-specific toolchains or behavior. Use when selecting an SDK or runtime architecture, writing zsh or system-bash commands, investigating native macOS crashes, packaging for macOS, or checking platform behavior from a Mac.'
---

# .NET Development on macOS

Apply these only where macOS, Apple silicon, or its system tools affect the work. Other skills in this plugin still apply.

## When not to use

- Permission or sandbox denials in an agent session: `agent-sandbox-troubleshooting`.
- Choosing or translating container commands: `native-container-cli`.
- Azure SQL Database container-specific setup: `azuresql-db-*`, when installed.
- Intune manifest fields: `relaypublisher-manifest`.
- General verification criteria: `dotnet-testing` and `dotnet-ci-cd`.

## Rules

### 1. Select and verify the intended .NET architecture

- **Rule:** On Apple silicon, verify the architecture and install root of the `dotnet` process the project actually invokes. Set architecture-specific `DOTNET_ROOT_*` variables only when their target process needs them; they take precedence over `DOTNET_ROOT`. Select SDK versions from project requirements and the chosen tool's support policy. Do not change target frameworks or `global.json` as a side effect of installing an SDK.
- **Check:** Report the invoked SDK, architecture, and install root; build and test a relevant project when the change requires it.
- **Why:** An SDK migration pointed an x64 variable at an arm64 install, and an information-only check had not verified the project build.

### 2. Write commands for the shell and system tools that run them

- **Rule:** Quote arguments that the active shell may expand (such as `?`, `*`, or `[` in zsh). Avoid Bash features newer than 3.2 in scripts that must run under macOS `/bin/bash`, and avoid GNU-only options when using BSD tools. Use a temporary path that is explicit and permitted by the current environment.
- **Check:** Run the script with each declared shell/platform target, or identify which targets were inspected but unavailable.
- **Why:** A zsh API command treated `?` as a glob, and a script using newer Bash and GNU grep features failed on macOS.

### 3. Run Linux containers with the native Mac architecture

- **Rule:** On Apple silicon, use an image's arm64 variant when supported; use emulation only when the image lacks a compatible build and report that limitation. Check the service's actual memory requirement and whether the selected runtime supports the container API that the application or test library needs. Container command selection and fallback are covered by `native-container-cli`.
- **Check:** Confirm the image architecture and runtime capabilities; identify any emulation and verify the configured memory against the service requirement.
- **Why:** An amd64 database image crashed under Rosetta while its arm64 image was stable, and a test library requiring the Docker API could not use a runtime without that API.

### 4. Locate macOS-only crashes from native evidence

- **Rule:** When a crash is specific to macOS, inspect the native crash frames and identify the faulting layer before changing application code. Check relevant dependency release notes or issues, then verify the proposed fix on the affected path.
- **Check:** Record the faulting layer and symbol, the evidence for the selected fix, and the affected path tested or left unverified.
- **Why:** A live-region failure originated in the UI framework's native accessibility layer and was fixed by a patch release.

### 5. Compare package parsing with macOS tools

- **Rule:** When parsing `.pkg` internals, compare derived bundle identifiers, versions, architectures, or compression details with `pkgutil` and `xar` output for the same package, including multi-bundle packages. Keep API-version tables aligned with the implementation (`dotnet-documentation`, "Make prose, tables, diagrams, XML docs, and help agree with the code"). Validate all input needed after a remote write before the first side effect (`dotnet-coding`, "Validate everything before the first side effect").
- **Check:** Compare parser output for single-bundle and multi-bundle packages with native-tool output.
- **Why:** A package parser mishandled a compression format; a separate publish path threw after upload because a platform-specific result property was absent.

### 6. Verify the credential source and identity in use

- **Rule:** Identify which credential store and identity the configured CLI or library uses; macOS Keychain integration and prompts depend on the tool and configuration. A session that cannot answer an interactive prompt may be blocked. Do not delete credential-store entries or token caches as a sign-in reset without authorization. For `DefaultAzureCredential`, select or configure the intended local credential and document how deployed identity differs.
- **Check:** State the configured local identity and deployed identity; document an interactive setup requirement only when the selected provider uses it.
- **Why:** An agent could not answer an interactive credential prompt, and the local and deployed credential chains resolved differently.

### 7. Name where non-macOS behavior is verified

- **Rule:** A Mac cannot establish Windows- or Linux-specific behavior such as Win32 packaging, case-sensitive paths, or Linux-only services. Use the relevant CI job or target environment where available; report the result and leave unavailable checks explicitly unverified. Build and run each macOS runtime identifier required by the release scope.
- **Check:** For each affected platform, state where it was exercised or that it remains unverified.
- **Why:** Windows packaging behavior was established only by a Windows CI job after it could not be reproduced locally.

### 8. Verify native desktop interactions on macOS

- **Rule:** For a macOS desktop change involving window focus, keyboard interaction, or layout, headless tests alone do not show the native window behavior. Exercise the changed interaction in the app and inspect a screenshot when visual layout or focus is part of the acceptance criteria. Use an isolated test session when other windows interfere with automation; change unrelated windows only when authorized.
- **Check:** Record the build, interaction tested, and observed result; report unavailable visual checks separately.
- **Why:** Keyboard confirmation left focus on the wrong control, and another window interfered with UI automation.
