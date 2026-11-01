# Windows: WSL Containers

Use Microsoft's **WSL Containers** CLI, `wslc.exe`. This is distinct from running Docker Engine inside a WSL distribution and from the `wsl.exe` distribution-management CLI. Do not invent a `wsl container` subcommand. Prefer the unambiguous `wslc.exe` name over an executable named `container` on Windows.

## Discover the installation

Use PowerShell 7 on Windows:

```powershell
Get-Command wslc.exe -CommandType Application -ErrorAction SilentlyContinue
wsl --version
# Run only if wslc.exe was found.
wslc.exe version
wslc.exe --help
wslc.exe run --help
```

From a WSL Bash shell, inspect Windows interoperability and command availability without invoking Docker:

```bash
command -v wslc.exe
# Run only if wslc.exe was found.
wslc.exe version
wslc.exe --help
wslc.exe run --help
```

Microsoft's WSL container overview and tutorial, checked 2026-11-01, describe WSL 2.9.3 or newer. Verify current requirements rather than treating that historical minimum as sufficient for every feature. `wsl --update` changes the installation; do not run it just to probe support.

## Candidate translations

Check operation-specific help and all flags before executing these forms:

| Source operation | WSL Containers candidate |
|---|---|
| `docker run ...` | `wslc.exe run ...` |
| `docker build ...` | `wslc.exe build ...` |
| `docker ps -a` | `wslc.exe container list --all` |
| `docker images` | `wslc.exe image list` |
| `docker exec ...` | `wslc.exe exec ...` |
| `docker logs <name>` | `wslc.exe container logs <name>` |
| `docker stop <name>` | `wslc.exe container stop <name>` |
| `docker inspect <name>` | `wslc.exe container inspect <name>` for a container; use image help for an image |

For example, after verifying support, a documented `docker run --rm -p 8080:80 --name web nginx` becomes:

```powershell
wslc.exe run --rm -p 8080:80 --name web nginx
```

```bash
wslc.exe run --rm -p 8080:80 --name web nginx
```

For mounts and build contexts in WSL, verify which filesystem namespace `wslc.exe` expects. Do not pass `/mnt/...`, a Windows drive path, or a UNC path on the assumption that all CLI contexts interpret them identically. Use an appropriate path conversion only after establishing the expected namespace.

## Capability gaps

Check Compose and other requested features against the installed help and current Microsoft documentation. Familiar Docker-like syntax is not full Docker CLI, flag, daemon API, or plugin compatibility. Windows container images are outside this Linux-container runtime's purpose. Any required Docker fallback follows the approval gate in `SKILL.md`.

Official sources to locate when requirements or behavior need confirmation: Microsoft Learn **WSL container**, **Get started with containers on WSL**, and Microsoft's **microsoft/WSL** repository. Search by those exact titles; use the installed version's help for the final command shape.
