---
name: dotnet-architecture-design
description: 'Design-phase rules for .NET and Azure systems, learned from designs that had to be redone. Use while writing or revising a design document, ADR, or implementation plan; when deciding protocol or server version support and feature gates; when calling Microsoft Graph, Intune, or another external API for the first time; when choosing an Azure hosting service such as Static Web Apps or Functions; when designing connection, sign-in, session, timeout, or quota state; when creating or restructuring a solution (.slnx or .sln); or when choosing the CI platform for a repository. Not for writing code (dotnet-coding) or the ADR file format (project-documentation).'
---

# .NET / Azure Architecture Design

Each rule comes from a design that passed review and later failed in production, in the real client, or in a user review. Apply them while the design is still text.

## When not to use

- C# implementation details: `dotnet-coding`.
- ADR, architecture, and setup document structure and approval gates: `project-documentation`.
- Tracking issues and plan publishing: `github-plan-issues` and `github-wiki-plan`, or the Azure DevOps Boards and Wiki skills.

## Rules

### 1. Gate version-dependent features on the connected peer

- **Rule:** Gate features on the connected peer's reported version or negotiated capabilities, not the build-time version. Record the recommended, minimum supported, and distributed versions and each feature threshold separately. For shared settings, specify read and write eligibility separately and when applying a setting may replace an existing draft.
- **Check:** The design covers peers below the minimum, at the minimum, at each feature boundary, and of unknown version, with the features and fallback for each.
- **Why:** A feature gated on the build-time version broke against an older peer, and unsupported versions had to be rejected afterwards.

### 2. List an external API's required fields and preconditions before designing the payload

- **Rule:** Before designing a write to Microsoft Graph, Intune, GitHub, or Azure DevOps, list every required property per resource type from the official schema and every precondition (a feature that must be enabled, a parent that must exist).
- **Check:** The design has a required-property table per resource type (for example Win32 versus macOS apps), and each create step checks its precondition and warns instead of failing.
- **Why:** A Win32 app upload failed with HTTP 400 for two unset required properties, and a plan that ignored a disabled feature failed with HTTP 404 at apply time.

### 3. Confirm the hosting service supports the stack

- **Rule:** Confirm from the service documentation that the chosen Azure service supports the language, runtime, and framework, and cite the source in the design.
- **Why:** A design assumed a stack that Static Web Apps cannot host and had to be redone.

### 4. Make host-dependent settings multi-valued

- **Rule:** Allowed origins, redirect URIs, and CORS settings accept a list that includes every custom domain and the default host name. Origin checks apply only to state-changing methods.
- **Check:** Tests cover the default host and a custom domain.
- **Why:** A single-valued allowed origin rejected every write from the custom domain with HTTP 403.

### 5. Route every write of a canonical log through one transaction

- **Rule:** When one store is the source of truth (an action log, an event journal), list every code path that writes related data and route all of them through the same transaction.
- **Why:** One event type was saved without passing through the canonical action log.

### 6. Model connection and sign-in state as one state machine

- **Rule:** One owner holds connected, degraded, disconnected, and signed-out states. Remote disconnects, sign-in, sign-out, account refresh, and worker restarts are transitions of that state, and UI command availability is derived from it. Reset per-session fields on re-initialization, and key per-operation fields by their identifier (for example a thread ID), not a single slot. When notifications must stay in order, the design names the queue, its single consumer, and its overflow policy so the read loop never blocks (`dotnet-coding` rule 2).
- **Check:** A state diagram includes remote disconnect, authentication, and restart events, and states which component writes the final state when notifications race; the ordering guarantee and overflow policy each have a planned test.
- **Why:** Remote disconnects were not reflected, sign-in and automatic worker restarts left the UI degraded, a late notification overwrote Ready, and a single pending-turn slot broke concurrent requests.

### 7. Bound every external wait and design for operational limits

- **Rule:** Every wait on a peer, sign-in, device code, or status check has a timeout and a visible failure state with a retry path. Design the behavior for quota or rate-limit exhaustion and reset, pause and resume, an offline host, and lease expiry, and validate computed times (a reset time must be later than the observation time).
- **Check:** Each scenario has an expected state, user message, and recovery in the design.
- **Why:** A connection stayed "connecting" for minutes with no timeout, the design had to be asked whether it covered a usage limit, and a computed reset time preceded its observation.

### 8. Match the CI platform to the repository host

- **Rule:** Azure Pipelines for Azure Repos, GitHub Actions for GitHub, unless the user says otherwise. Ask when the host is unclear.
- **Why:** A GitHub Actions design for an Azure Repos project had to be replaced.

### 9. Use .slnx as the solution format

- **Rule:** New solutions use `.slnx` (`dotnet new sln` in the .NET 10 SDK; `--format slnx` from SDK 9.0.200). Migrate an existing `.sln` with `dotnet sln <name>.sln migrate`, delete the `.sln` in the same change, and update every reference (CI and pipeline YAML, scripts, README, `global.json`). Keep `.sln` only when the user asks or a required tool cannot read `.slnx`, and record why.
- **Check:** No `.sln` remains unless an exception is recorded; `git grep -nE "\.sln\b"` finds no stale references; `global.json` pins an SDK that supports `.slnx`.
- **Why:** Keeping both formats or stale references lets CI build a different project set than the IDE.

### 10. Change the design records together

- **Rule:** When a decision changes, update the design document and ADR, and the Wiki plan and tracking issue when the repository rules or the user require them for this change, in the same change. Do not create issues or Wiki pages the user declined. Compare the user's decisions with the document item by item, and reflect every plan item in the repository's plan, task, or todo files.
- **Check:** The report maps each user decision to the section that reflects it, including previously undefined values (for example what `null` means for an optional setting).
- **Why:** A revision omitted a section, an ADR revision, and the meaning of `null`; plan items were missing from the task file; and Wiki pages were created after the user said they were unnecessary.

### 11. Define recovery across a queue and a store

- **Rule:** For a queue-triggered Azure Function that persists a result, define when processing is complete, what is retried, and which key makes replay safe, using the chosen trigger's delivery and retry semantics.
- **Check:** The design covers interruption before persistence, after persistence but before completion, duplicate delivery, and exhausted retries.
- **Why:** A restart between persistence and completion can replay work that already changed durable state.

### 12. Separate package updates from framework migration

- **Rule:** Before planning an update, identify each affected project's effective SDK, target frameworks, and resolved direct and transitive dependencies. Check parent version ranges before proposing a pin. Treat a required framework change or preview SDK as a separate decision, and vet candidates with `nuget-validate`.
- **Check:** The plan separates updates within the current targets from updates that need a migration; every central pin is used by a project in scope.
- **Why:** A parent package constrained a transitive update to an older major, and a central package list included unused entries.

## Done checklist

- [ ] Feature gates use the connected peer's version; minimum, recommended, and distributed versions are distinct.
- [ ] Required properties and preconditions of each external resource are listed.
- [ ] The hosting service's supported stack is cited.
- [ ] Host-dependent settings are lists.
- [ ] Canonical-store write paths are enumerated.
- [ ] Connection and authentication state has one owner and a state diagram; ordered streams name the queue, consumer, and overflow policy.
- [ ] Every external wait has a timeout; quota, offline, and lease scenarios are designed.
- [ ] CI platform matches the repository host.
- [ ] Solutions are `.slnx` with no stale `.sln` references, unless an exception is recorded.
- [ ] Every user decision is traced to a section; required records are updated together.
- [ ] Queue replay and partial persistence have defined outcomes when applicable.
- [ ] Package updates and SDK or framework migrations are distinguished.
