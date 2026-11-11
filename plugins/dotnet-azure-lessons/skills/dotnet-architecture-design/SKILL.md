---
name: dotnet-architecture-design
description: 'Design guidance for .NET and Azure systems. Use when writing or revising architecture, version support, external API, connection or quota behavior, solution-format, or package and SDK upgrade plans.'
---

# .NET / Azure Architecture Design

Use these checks while the design is still changeable. They come from observed implementation failures, review feedback, and designs that needed revision; apply only the checks relevant to the proposed system and scope.

## When not to use

- C# implementation details: `dotnet-coding`.
- ADR, architecture, and setup document templates or approval gates: `project-documentation`.
- Tracking issues and plan publishing: `github-plan-issues` and `github-wiki-plan`, or the Azure DevOps Boards and Wiki skills.

## Rules

### 1. Gate version-dependent features on the connected peer

- **Rule:** Gate features on the connected peer's reported version or negotiated capabilities, not the build-time version. Record recommended, minimum supported, and distributed versions when they affect compatibility. For shared settings, specify read and write eligibility separately.
- **Check:** The design covers relevant version boundaries, unknown versions, and the fallback for affected features.
- **Why:** A feature gated on build-time version broke against an older peer.

### 2. Verify external API requirements and blocking preconditions

- **Rule:** For a new external API write, use its official schema to identify required properties, API version, and blocking preconditions. Pin serialized payloads in tests where the code owns that contract (`dotnet-testing`, "Pin serialization of external payloads"). A missing precondition that makes the operation invalid must stop the operation with an actionable explanation; warn only when the condition is recoverable and the operation can safely continue.
- **Check:** The design identifies relevant resource-specific requirements and defines whether each unmet precondition blocks, retries, or permits continuation.
- **Why:** An upload failed because required fields were unset, and an apply step attempted an operation while a required feature was disabled.

### 3. Confirm the hosting service supports the stack

- **Rule:** Check current service documentation for support of the chosen language, runtime, framework, and listening port.
- **Check:** Cite the service documentation and supported stack in the design.
- **Why:** A design selected a stack the hosting service could not run and a container listened on a port the platform did not route.

### 4. Separate browser CORS behavior from API authorization

- **Rule:** Model the browser origins that must read responses and the preflight/credential behavior required by the client. CORS controls whether browsers expose cross-origin responses; it does not replace server-side authentication or authorization. Define authorization for protected operations and CSRF defenses for cookie-authenticated state changes according to the application design. Do not exempt reads from CORS requirements by default.
- **Check:** The design covers expected browser origins, relevant response methods and headers, credentials when used, protected operations, and state-changing request defenses.
- **Why:** Origin handling was treated as a write-only server check, although browser CORS controls response access and is distinct from API authorization.

### 5. Keep canonical event writes within one transaction

- **Rule:** If one store is the source of truth for a log or journal, identify every related write path and use the same transaction boundary.
- **Check:** The design lists the write paths and how each records to the canonical store.
- **Why:** One event type bypassed the canonical action log.

### 6. Model connection and sign-in state as one state machine

- **Rule:** Identify the owner of connection and authentication state, its transitions, and how UI availability follows it. Reset per-session fields on re-initialization and key overlapping operations by identifier. For ordered notifications, name the queue, consumer, and overflow policy (`dotnet-coding`, "Process ordered notifications through one consumer").
- **Check:** The state model covers relevant disconnect, authentication, restart, and overlapping-operation transitions, including which owner wins when notifications race.
- **Why:** Remote disconnects and late notifications left the UI in stale states, and a single pending-operation slot broke concurrent requests.

### 7. Bound external waits and model operational limits

- **Rule:** Define timeouts, user-visible failure, and recovery for external waits that can outlive the interactive flow. Where relevant, model quota reset, pause/resume, offline state, lease expiry, and expiring upload credentials.
- **Check:** Each applicable scenario has an expected state and recovery; computed deadlines are valid.
- **Why:** A connection remained in a waiting state, quota behavior was undefined, and a long upload outlived its credential.

### 8. Match the CI platform to the repository host

- **Rule:** Select the repository's supported CI platform unless the user or repository specifies otherwise. Clarify the host only when it is unknown.
- **Check:** The design names the target repository and CI platform.
- **Why:** A workflow for GitHub Actions had to be replaced for an Azure Repos project.

### 9. Prefer .slnx for new supported solutions

- **Rule:** Prefer `.slnx` for a new solution when the repository's SDKs and tools support it. Keep an existing `.sln` unless its migration is explicitly included in the approved scope. A migration plan must cover project membership, SDK/tool compatibility, scripts, CI, and documentation in the same change.
- **Check:** The design identifies the selected format, required tooling, and all affected references when migration is in scope.
- **Why:** Stale references and divergent solution project sets caused CI and IDE builds to differ.

### 10. Stage environment and profile migrations for recovery

- **Rule:** For a user environment or profile migration, inventory the current state, stage and validate candidate output, then verify which consumers resolve the new root before switching them. Preserve the previous root and data outside the migration's ownership so a partial switch can be resumed or rolled back. Apply these steps only when that migration is part of the approved task.
- **Check:** The plan identifies the baseline, validation gate, consumers to switch and verify, preserved state, and recovery path.
- **Why:** A profile update needed conflict handling and rollback, and a tooling migration required verification across several consumers before the user completed the switch.

### 11. Trace design decisions to the records in scope

- **Rule:** Keep approved design decisions consistent across the canonical design and any ADR or task records required by repository policy. Reflect user decisions and their unresolved values without inventing defaults. Use the applicable documentation and Issue/Wiki workflows for those records.
- **Check:** Each affected decision links to its owning record, and required companion records agree.
- **Why:** A design revision omitted the meaning of an optional `null` value and left related records inconsistent.

### 12. Define retry and idempotency for queued persistence

- **Rule:** When a queue-triggered function persists a result, define completion, retry behavior, and the key that makes replay safe, using the selected trigger's delivery semantics.
- **Check:** Cover interruption before persistence, after persistence but before completion, duplicate delivery, and exhausted retries.
- **Why:** A restart after persistence but before completion can replay durable changes.

### 13. Separate package updates from framework migrations

- **Rule:** Before planning an update, identify affected projects' effective SDK, target frameworks, and resolved dependencies. Check parent version ranges; treat framework, preview-SDK, or test-framework changes as separate decisions. Use `nuget-validate` for package candidates when available.
- **Check:** The plan separates compatible package updates from migration work, and central pins apply to projects in scope.
- **Why:** Parent package constraints blocked a transitive update, while unused central pins obscured the actual change.
