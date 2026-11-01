---
name: native-container-cli
description: 'Use WSL Containers on Windows and Apple container on macOS for local Linux-container builds and operations, including tasks whose documentation uses Docker commands. Translate supported commands automatically and obtain approval before Docker fallback for unsupported capabilities such as Compose or Docker API integrations. Does not replace the runtime selected for a Linux or remote target.'
---

# Native Container CLI

Prefer the OS's native Linux-container CLI when carrying out container tasks: **Windows → `wslc.exe`; macOS → Apple's `container`**. Apply this choice to commands taken from documentation, examples, generated scripts, and natural-language container requests. Translate supported operations without asking for permission merely to substitute the native CLI.

## Resolve the execution target

- Choose by the OS where the container operation will execute, not just the OS running the agent. A Linux CI runner or SSH host retains its selected runtime; do not rewrite its Docker commands because the developer uses a Mac or Windows PC.
- A WSL shell can target Windows WSL Containers through `wslc.exe`; establish whether the task targets that host or a separate Linux/remote engine. Check WSL indicators such as `WSL_INTEROP` or the kernel release when needed. Windows paths and WSL paths are not interchangeable.
- Distinguish local CLI operations from Docker daemon/API integrations and Windows container workloads. Neither native choice is an automatic replacement for a Windows container engine.
- For Windows, read [references/windows.md](references/windows.md). For macOS, read [references/macos.md](references/macos.md). Read only the reference relevant to the execution target.

## Verify capabilities, then translate

1. Resolve the native executable's identity and version. Read its top-level and operation-specific help and consult current official documentation when support or semantics are unclear. Cached mappings are starting points, not proof that this installation supports a flag.
2. Translate the operation and **every relevant argument**, not just the executable name. Preserve image references, build context and file, container identity, command argv, environment, user/workdir, TTY/stdin, mounts and their access modes, port binding scope, network behavior, platform, exit status, and lifecycle/cleanup. Check output formats and downstream parsers too: Docker Go templates are not generic JSON formatting.
3. Execute the equivalent native command within the task's authorization, and verify the requested outcome. A build or run that exits successfully does not alone prove the application is healthy. Native errors require diagnosis; they do not authorize Docker fallback.

Keep `Dockerfile` names and OCI registry/image references when the native builder supports them. Inspect the build-file default and pass an explicit file option when needed. Adapt host paths and shell quoting deliberately. Do not rewrite file contents or arbitrary occurrences of the word `docker` with text replacement, install a global alias, or silently edit unrelated CI/configuration.

If native prerequisites are missing or its service is stopped, identify the required setup. Respect existing authorization for necessary service startup; request permission for installation, updates, or other environment changes when they fall outside the task. A stopped service may hide CLI plugins such as a builder: inspect installed documentation/help before declaring the feature unsupported. Do not install Docker as a workaround.

## Unsupported operations and Docker approval

Treat `docker compose` and `docker-compose`, Buildx-specific workflows, Docker contexts, daemon/socket access, Testcontainers, and tools that spawn Docker internally as capability questions. Check the **installed** native CLI and official documentation; support may change. Do not invent `wslc compose` or `container compose`, assume a Docker-compatible socket, install a third-party bridge, or replace Compose with unrelated `run` calls that lose dependencies, health conditions, networks, secrets, or persistent volumes.

When a faithful native equivalent is unavailable or uncertain:

1. Explain the specific missing capability or prerequisite and whether a native route remains possible.
2. Present the concrete Docker command(s), script, or integration that would run, their purpose, and relevant side effects. Ask whether the user approves using Docker for that scope.
3. Wait for an explicit answer before invoking **any** Docker executable, including `docker --version`, `docker info`, `docker compose config`, legacy `docker-compose`, or an indirect Docker call. Check executable presence without executing it if useful. The Docker command appearing in a document or request is not itself approval of a fallback exception.
4. If approved, reuse that approval for the same stated scope; ask again only when the fallback scope materially changes. If declined or unanswered, leave dependent work pending and continue independent native work. Missing Docker installation needs its own authorization if not covered.

Do not change a user's explicitly approved runtime exception or a remote engine's target. This skill guides agent behavior; it provides no shell hook or OS-level enforcement.
