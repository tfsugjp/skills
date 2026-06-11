---
name: azure-devops-pipelines
description: 'Manage Azure Pipelines: create YAML pipeline definitions, queue runs, and monitor builds including stage control and log analysis. Use when the user asks to create, run, watch, or debug Azure DevOps pipelines or builds. Prefers Azure DevOps MCP Server tools and falls back to the REST API.'
compatibility: 'Azure DevOps Services. MCP tools require the Azure DevOps MCP Server (pipelines toolset).'
---

# Azure Pipelines

Create, run, and monitor Azure Pipelines. Read [azure-devops-foundation](../azure-devops-foundation/SKILL.md) first for the MCP-first/REST-fallback strategy and authentication.

## When to use

- Creating a YAML pipeline definition from a file in a repository
- Queueing a pipeline run (optionally with parameters/variables or a specific branch)
- Monitoring a run: status, stage/job results, log retrieval, failure analysis
- Cancelling, retrying, or running specific stages of an in-flight build
- Downloading build artifacts

## MCP tools (preferred)

| Tool | Action | Purpose |
|---|---|---|
| `pipelines_definition` | `list`, `list_revisions` | Find pipeline definitions and their history |
| `pipelines_run` | `get`, `list` | Pipeline run status |
| `pipelines_build` | `list`, `get_status`, `get_changes` | Build status, issues, and associated commits/work items |
| `pipelines_build_log` | `list`, `get_content` | Enumerate and read build logs |
| `pipelines_artifact` | `list`, `download` | Build artifacts (not Azure Artifacts feeds — see guardrails) |
| `pipelines_write` | `run_pipeline`, `create_pipeline`, `update_build_stage` | Queue runs, create YAML definitions, cancel/retry/run stages |

## REST API fallback

Base: `https://dev.azure.com/{organization}/{project}/_apis` — verify with `microsoft_docs_search("Azure DevOps REST API pipelines <operation>")` before calling.

| Operation | Method and endpoint | api-version |
|---|---|---|
| Create pipeline | `POST /pipelines` (body: name, folder, repository + YAML path) | `7.1` |
| List pipelines | `GET /pipelines` | `7.1` |
| Run pipeline | `POST /pipelines/{pipelineId}/runs` | `7.1` |
| Get run | `GET /pipelines/{pipelineId}/runs/{runId}` | `7.1` |
| Get build (richer status) | `GET /build/builds/{buildId}` | `7.1` |
| Stage/job breakdown | `GET /build/builds/{buildId}/timeline` | `7.1` |
| List / read logs | `GET /build/builds/{buildId}/logs[/{logId}]` | `7.1` |
| Cancel build | `PATCH /build/builds/{buildId}` (`{"status": "cancelling"}`) | `7.1` |

```bash
# Queue a run on a specific branch with a template parameter
curl -s -X POST -H "Authorization: Bearer ${ADO_TOKEN}" -H "Content-Type: application/json" \
  "https://dev.azure.com/{org}/{project}/_apis/pipelines/{pipelineId}/runs?api-version=7.1" \
  -d '{
    "resources": {"repositories": {"self": {"refName": "refs/heads/main"}}},
    "templateParameters": {"configuration": "Release"}
  }'

# Inspect failed stages/jobs
curl -s -H "Authorization: Bearer ${ADO_TOKEN}" \
  "https://dev.azure.com/{org}/{project}/_apis/build/builds/{buildId}/timeline?api-version=7.1" \
  | jq '[.records[] | select(.result == "failed") | {name, type, log: .log.url}]'
```

## Common workflows

### Create a pipeline from YAML
1. Ensure the YAML file exists in the repository (`repo_file` `get_content` from [azure-devops-repos](../azure-devops-repos/SKILL.md) to confirm path).
2. `pipelines_write` `create_pipeline` with project, repository, YAML path, and folder/name.
3. Queue a validation run on a feature branch before relying on it for `main`.

### Run and monitor to completion
1. `pipelines_write` `run_pipeline` (record the run/build ID from the response).
2. Poll `pipelines_run` `get` (or `pipelines_build` `get_status`) — builds take minutes; poll at 30–60 s intervals, not in a tight loop.
3. On completion, report result, duration, and a link to the run.

### Diagnose a failed run
1. `pipelines_build` `get_status` to identify failing stage and surfaced issues.
2. `pipelines_build_log` `list`, then `get_content` for the failing job's log ID only — logs are large; never fetch all logs.
3. Search the tail of the log for the first `##[error]` occurrence; report root cause with the log excerpt.
4. If the cause is a flaky infrastructure failure, `pipelines_write` `update_build_stage` to retry the stage; for code errors, fix the code instead.

## Guardrails

- `pipelines_artifact` and `/build/builds/{id}/artifacts` are **build artifacts**. Package feeds (NuGet/npm/etc.) are Azure Artifacts — use [azure-devops-artifacts](../azure-devops-artifacts/SKILL.md).
- Queueing runs consumes parallel-job capacity and may deploy — confirm before running pipelines whose names suggest production deployment (`deploy`, `release`, `prod`).
- Cancelling someone else's in-flight build needs confirmation.
- Creating a pipeline does not validate the YAML; the first run does. Prefer a branch-scoped validation run.
- Log content can contain secrets if the pipeline is misconfigured — quote only the minimal excerpt needed to explain a failure.

## Learn more

- `microsoft_docs_search("Azure DevOps Pipelines REST API runs")`
- `microsoft_docs_search("Azure DevOps Build REST API timeline logs")`
- `microsoft_docs_search("Azure Pipelines YAML schema")`
- `microsoft_docs_search("Azure Pipelines run pipeline parameters REST")`
