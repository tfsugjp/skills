---
name: azure-devops-testplans
description: 'Manage Azure Test Plans: create test plans, suites, and test cases, update test steps, and read test results from builds. Use when the user asks to create or organize test plans/suites/cases, generate test cases from work items, or check test results in Azure DevOps. Prefers Azure DevOps MCP Server tools and falls back to the REST API.'
compatibility: 'Azure DevOps Services. MCP tools require the Azure DevOps MCP Server (testplan toolset). Creating test plans requires Basic + Test Plans access level.'
---

# Azure Test Plans

Create and organize test plans, suites, and cases, and read test results. Read [azure-devops-foundation](../azure-devops-foundation/SKILL.md) first for the MCP-first/REST-fallback strategy and authentication.

## When to use

- Creating a test plan for a sprint/release and structuring suites under it
- Creating test cases (including generating them from user story descriptions)
- Updating test case steps
- Adding existing test cases to suites
- Reading test results associated with a build

## MCP tools (preferred)

| Tool | Action | Purpose |
|---|---|---|
| `testplan` | `list_plans`, `list_suites`, `list_cases` | Browse plans, suites, and cases |
| `testplan_show_test_results_from_build_id` | — | Test results for a build |
| `testplan_test_plan_write` | `create` | Create a test plan |
| `testplan_test_suite_write` | `create`, `add_test_cases` | Create suites, add cases to suites |
| `testplan_test_case_write` | `create`, `update_steps` | Create test cases, update steps |

Test cases are work items under the hood — field updates beyond steps (priority, assignee, tags) go through `wit_work_item_write` ([azure-devops-boards](../azure-devops-boards/SKILL.md)).

## REST API fallback

Base: `https://dev.azure.com/{organization}/{project}/_apis/testplan` — verify with `microsoft_docs_search("Azure DevOps Test Plans REST API <operation>")` before calling.

| Operation | Method and endpoint | api-version |
|---|---|---|
| List / create plans | `GET/POST .../plans` | `7.1` |
| List / create suites | `GET/POST .../Plans/{planId}/suites` | `7.1` |
| List cases in suite | `GET .../Plans/{planId}/Suites/{suiteId}/TestCase` | `7.1` |
| Add cases to suite | `POST .../Plans/{planId}/Suites/{suiteId}/TestCase` | `7.1` |
| Test results for build | `GET /_apis/test/ResultDetailsByBuild?buildId={id}` | `7.1` |

Creating a test case via REST is a work item create (`POST /_apis/wit/workitems/$Test%20Case`) where steps live in the `Microsoft.VSTS.TCM.Steps` field as XML.

## Common workflows

### Sprint test plan setup
1. `testplan_test_plan_write` `create` named after the iteration, with the iteration path set.
2. `testplan_test_suite_write` `create` one requirement-based or static suite per user story/feature.
3. Create or add cases per suite.

### Generate test cases from a user story
1. `wit_work_item` `get` the story; read description and acceptance criteria.
2. Derive cases: one per acceptance criterion plus negative/boundary cases.
3. `testplan_test_case_write` `create` with explicit step/expected-result pairs; add to the story's suite via `add_test_cases`.
4. Link the cases to the story (`wit_work_item_link_write` `link`, type "Tested By") for traceability.

### Build quality check
1. `testplan_show_test_results_from_build_id` for the build in question.
2. Summarize pass rate and list failed tests with owning suites; cross-reference failures to recent changes via `pipelines_build` `get_changes`.

## Guardrails

- Authoring test plans/suites requires the **Basic + Test Plans** access level (or equivalent); plain Basic users get 403 on plan creation — report, don't retry.
- Test suites and plans reference shared test cases; deleting a suite does not delete its cases, but deleting cases affects every suite using them.
- Keep generated test case steps concrete (action + expected result per step) — vague generated steps create review debt.

## Learn more

- `microsoft_docs_search("Azure DevOps Test Plans REST API plans suites")`
- `microsoft_docs_search("create test cases Azure Test Plans")`
- `microsoft_docs_search("Azure Test Plans access level requirements")`
