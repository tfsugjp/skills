# Hook Installation Guide — Mechanical Enforcement

The skill's policy in `SKILL.md` is instruction-based ("soft") guidance for the model. For defense-in-depth, install [scripts/azure-guardrails-hook.ps1](../scripts/azure-guardrails-hook.ps1) as a **Claude Code PreToolUse hook**: it intercepts every Bash/PowerShell command and Azure MCP tool call before execution and mechanically enforces the same policy.

## What the hook does

| Situation | Decision emitted |
|-----------|------------------|
| Command matches a `deny` entry in `.azure-guardrails.yml` | `deny` — blocked, with the entry's reason |
| Command matches an `allow` entry (and is not an identity op) | `allow` — runs without a prompt |
| Identity operation (Entra ID / RBAC / Graph writes) | `ask` — always; the allowlist cannot exempt it |
| Other mutating Azure operation (Tier 3) | `ask` — permission prompt with policy context |
| Read-only or non-Azure command | no output — Claude Code's normal permission flow applies |
| Config file exists but cannot be parsed | `ask` — fails closed for mutating operations |

## Prerequisites

- **PowerShell 7+** (`pwsh`) on PATH — Windows, macOS, and Linux are all supported
- **powershell-yaml module** (only if you use the YAML config format):

  ```powershell
  Install-Module powershell-yaml -Scope CurrentUser
  ```

  Alternatively, name your config `.azure-guardrails.json` (same schema as JSON) and no module is needed.

## Registration

Add to your Claude Code settings — project-level `.claude/settings.json` (recommended, so the whole team gets it) or user-level `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|PowerShell|mcp__.*[Aa]zure.*",
        "hooks": [
          {
            "type": "command",
            "command": "pwsh -NoProfile -File \"<REPO>/.github/skills/azure-guardrails/scripts/azure-guardrails-hook.ps1\""
          }
        ]
      }
    ]
  }
}
```

Replace `<REPO>` with the absolute path to your checkout of this skills repository, or copy `azure-guardrails-hook.ps1` into your project (e.g., `.claude/hooks/`) and point at that path. Windows example:

```json
"command": "pwsh -NoProfile -File \"D:/GitHub/tfsug/skills/.github/skills/azure-guardrails/scripts/azure-guardrails-hook.ps1\""
```

macOS / Linux example:

```json
"command": "pwsh -NoProfile -File \"$HOME/repos/skills/.github/skills/azure-guardrails/scripts/azure-guardrails-hook.ps1\""
```

After editing settings, restart the Claude Code session (hooks are loaded at startup).

## Verifying the installation

Feed the hook a sample payload and check the decision:

```powershell
'{"tool_name":"Bash","tool_input":{"command":"az group delete -n rg-test"},"cwd":"."}' |
  pwsh -NoProfile -File azure-guardrails-hook.ps1
# expected: {"hookSpecificOutput":{"permissionDecision":"ask", ...}}

'{"tool_name":"Bash","tool_input":{"command":"az vm list -o table"},"cwd":"."}' |
  pwsh -NoProfile -File azure-guardrails-hook.ps1
# expected: no output (read-only)
```

Then, in a live session, ask the agent to run a harmless mutating command (e.g., `az tag update` on a sandbox resource) and confirm a permission prompt appears with the `[azure-guardrails]` reason.

## Skill-only vs. skill + hook

| | Skill only | Skill + hook |
|---|---|---|
| Model follows approval workflow | Yes (instruction-based) | Yes |
| Protection if the model misclassifies or forgets | None | Commands are still intercepted |
| `deny` entries enforced absolutely | No (model could be persuaded) | Yes — hook blocks regardless |
| Setup effort | None | settings.json edit + pwsh |

The hook is a safety net, not a replacement: classification by regex has blind spots (obfuscated commands, scripts invoked from files), so the model-facing policy in SKILL.md remains the first line of defense.

## Limitations

- The hook inspects the command string of `Bash`/`PowerShell` tool calls. Mutations buried inside script **files** that the command merely executes (`./deploy.sh`, `pwsh ./cleanup.ps1`) are not visible to it — the skill policy still applies to those.
- Resource-group scoping relies on an explicit `-g`/`--resource-group`/`-ResourceGroupName` argument; scoped `allow` entries fail closed when the resource group cannot be determined from the command.
- Azure MCP tool classification is keyword-based over the tool parameters; unknown read-style calls pass through to the normal permission flow.
