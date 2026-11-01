# macOS: Apple container

Use Apple's **container** CLI for Linux containers. Confirm that the resolved executable is Apple's tool, not another program sharing the same name.

## Discover the installation

```bash
sw_vers -productVersion
uname -m
command -v container
# Run only if Apple's container was found.
container --version
container --help
container run --help
```

```powershell
# For a PowerShell 7 session on macOS.
sw_vers -productVersion
uname -m
Get-Command container -CommandType Application -ErrorAction SilentlyContinue
# Run only if Apple's container was found.
container --version
container --help
container run --help
```

Apple's README, checked 2026-11-01, specifies Apple silicon and macOS 26 support. Check the installed release's requirements before using it on a particular OS; do not assume Intel support or infer support solely from a version number greater than the documented one.

`container system start` starts services and can require first-run setup/downloads. Run it when necessary and authorized for the requested container work, not just to gather help for an unrelated task. CLI plugins such as the builder may be absent from top-level help while the service is stopped; missing help alone does not prove build is unsupported. Diagnose service state using available read-only help/status commands and official documentation.

## Candidate translations

Check operation-specific help and every flag before execution:

| Source operation | Apple container candidate |
|---|---|
| `docker run ...` | `container run ...` |
| `docker build ...` | `container build ...` when the builder is available |
| `docker ps -a` | `container list --all` |
| `docker images` | `container image list` |
| `docker pull <image>` | `container image pull <image>` |
| `docker push <image>` | `container image push <image>` |
| `docker tag <source> <target>` | `container image tag <source> <target>` |
| `docker rmi <image>` | `container image delete <image>` |
| `docker login ...` | `container registry login ...` |
| `docker exec ...`, `logs`, `stop`, `start` | `container exec ...`, `logs`, `stop`, `start` |
| `docker rm <name>` | `container delete <name>` |
| `docker inspect <name>` | `container inspect <name>` for a container; `container image inspect` for an image |

For example, after verifying support, a documented `docker run --rm -p 8080:80 --name web nginx` becomes:

```bash
container run --rm -p 8080:80 --name web nginx
```

```powershell
container run --rm -p 8080:80 --name web nginx
```

Do not turn `docker ps --format '{{.Names}}'` into the same flags on `container list`: verify a supported structured output format and adapt its consumer. Preserve bind-mount paths and modes, published-port binding scope, architecture/emulation requirements, network reachability, and credential handling. Native image stores and registry login state are separate from Docker's; do not assume existing Docker images, containers, or credentials are available.

## Capability gaps

Check Compose, Buildx, host networking, privileged/device features, and Docker socket/API integrations individually. OCI image compatibility does not imply these behaviors are supported. Do not automatically install a Compose bridge or point `DOCKER_HOST` at an invented native socket. Use the `SKILL.md` Docker approval gate when faithful translation is unavailable.

Official sources to locate when requirements or behavior need confirmation: Apple's **apple/container** README, **Container CLI Command Reference** (`docs/command-reference.md`), and release notes matching the installed version. The installed help takes precedence over unverified command-name assumptions.
