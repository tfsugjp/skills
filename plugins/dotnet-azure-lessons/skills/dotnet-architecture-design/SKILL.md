---
name: dotnet-architecture-design
description: 'Design-phase rules for .NET and Azure systems, learned from designs that had to be redone. Use while writing or revising a design document, ADR, or implementation plan; when deciding protocol or server version support and feature gates; when calling Microsoft Graph, Intune, or another external API for the first time; when choosing an Azure hosting service such as Static Web Apps or Functions; when designing connection, sign-in, or session state; when creating or restructuring a solution (.slnx or .sln); or when choosing the CI platform for a repository. Not for writing code (dotnet-coding) or the ADR file format (project-documentation).'
---

# .NET / Azure Architecture Design

Each rule below comes from a design that passed review and later failed in production, in the real client, or in a user review. Apply the rules while the design is still text; they are expensive to retrofit.

## When not to use

- Writing or reviewing C# implementation details: use `dotnet-coding`.
- ADR, architecture, and setup document structure and approval gates: use `project-documentation`.
- Creating tracking issues or publishing the approved plan: use `github-plan-issues` and `github-wiki-plan`, or the Azure DevOps Boards and Wiki skills.

## Rules

### 1. Gate version-dependent features on the connected peer

- **Rule:** Enable a feature that needs a newer server, CLI, or protocol only when the version reported by the connected peer (for example the `initialize` response) supports it. Do not gate on the package version you built against.
- **Check:** The design names the minimum supported version, the feature gate per version, and the error shown when the peer is below the minimum.
- **Why:** A feature gated on the build-time version broke when the user connected to an older peer, and an unsupported version had to be rejected explicitly afterwards.

### 2. List an external API's required fields and preconditions before designing the payload

- **Rule:** Before designing a write to Microsoft Graph, Intune, GitHub, or Azure DevOps, list every required property per resource type from the official schema, and every precondition (a feature that must be enabled, a parent that must exist).
- **Check:** The design has a table of required properties per resource type (for example Win32 versus macOS app types), and the plan step that creates a resource first checks its precondition and warns instead of failing.
- **Why:** A Win32 app upload failed in production with HTTP 400 because two required properties were never set, and a plan that ignored a disabled feature failed with HTTP 404 at apply time.

### 3. Confirm the hosting service supports the stack

- **Rule:** Confirm from the service documentation that the chosen Azure service (Static Web Apps, Functions, App Service, and so on) supports the language, runtime, and framework, and record the source in the design.
- **Check:** The design cites the supported-stack page or limit for the selected service.
- **Why:** A design assumed a stack that Static Web Apps cannot host and had to be redone.

### 4. Make host-dependent settings multi-valued

- **Rule:** Settings that list hosts the system is reached through (allowed origins, redirect URIs, CORS) accept multiple values, including every custom domain and the default host name.
- **Check:** The configuration schema is a list; tests cover the default host and a custom domain; origin checks apply only to state-changing methods.
- **Why:** A single-valued allowed origin rejected every write from the custom domain with HTTP 403.

### 5. Route every write of a canonical log through one transaction

- **Rule:** When one store is the source of truth (an action log, an event journal), enumerate every code path that writes related data and route all of them through the same transaction.
- **Check:** The design lists the write paths; none bypasses the canonical store.
- **Why:** A review found one event type that was saved without passing through the canonical action log.

### 6. Model connection and sign-in state as one state machine

- **Rule:** Represent connected, degraded, disconnected, and signed-out states in one owner. Remote disconnects, sign-in, sign-out, and account refresh are transitions of that state, and the UI command availability is derived from it. Reset all per-session fields on re-initialization, and key per-operation fields by their identifier (for example a thread ID) instead of a single slot.
- **Check:** The design has a state diagram that includes remote disconnect and authentication events, and states which component writes the final state when notifications race.
- **Why:** Remote disconnects were not reflected, sign-in left the connection degraded until a manual reconnect, a late notification overwrote Ready, and a single pending-turn slot broke concurrent requests.

### 7. Process ordered notifications with a single consumer

- **Rule:** When notifications must stay in order (message deltas followed by a completion), the design specifies a queue with one consumer, not concurrent handlers, and states what happens when the queue is full so the connection's read loop never blocks.
- **Check:** The design states the ordering guarantee, the overflow policy, and how both are tested.
- **Why:** Concurrent notification handling reordered deltas and completion and corrupted Busy/Ready transitions.

### 8. Match the CI platform to the repository host

- **Rule:** Use Azure Pipelines for Azure Repos and GitHub Actions for GitHub unless the user says otherwise. Ask before choosing when the host is unclear.
- **Check:** The design names the repository host and the CI platform.
- **Why:** A GitHub Actions design for an Azure Repos project had to be replaced with Azure Pipelines.

### 9. Use .slnx as the solution format

- **Rule:** New solutions use the XML solution format `.slnx`. With the .NET 10 SDK, `dotnet new sln` creates `.slnx` by default; with SDK 9.0.200 or later, pass `--format slnx`. When a repository still has an `.sln`, migrate it with `dotnet sln <name>.sln migrate`, delete the `.sln` in the same change, and update every reference to it (CI and pipeline YAML, scripts, README, `global.json` SDK version). Keep one solution file per solution, not both formats. Use `.sln` only when the user asks for it or a required tool cannot read `.slnx`, and record the reason in the design.
- **Check:** The repository contains `.slnx` files and no `.sln` files, unless the design records an exception; `git grep -nE "\.sln\b"` finds no stale references; `global.json` pins an SDK that supports `.slnx`.
- **Why:** `.slnx` is the SDK default from .NET 10 and is easier to review and merge; keeping both formats, or leaving stale `.sln` references, lets CI build a different project set than the IDE.

### 10. Change the design records together

- **Rule:** When a decision changes, update the design document, the ADR, the Wiki plan, and the tracking issue in the same change. Compare the user's decisions with the document item by item before reporting the revision as done.
- **Check:** The report lists each user decision and the section that now reflects it, including values that were undefined (for example what `null` means for an optional tier setting).
- **Why:** A revised design omitted a whole section, an ADR revision, and the meaning of a `null` value the user had specified.

## Done checklist

- [ ] Minimum versions and per-version gates are stated, based on the connected peer.
- [ ] Required properties and preconditions of each external resource are listed.
- [ ] The hosting service's supported stack is cited.
- [ ] Host-dependent settings are lists.
- [ ] Canonical-store write paths are enumerated.
- [ ] Connection and authentication state has one owner and a state diagram.
- [ ] Ordering guarantees name the queue and the consumer.
- [ ] CI platform matches the repository host.
- [ ] Solutions are `.slnx`, with no leftover `.sln` or stale references, unless an exception is recorded.
- [ ] Design, ADR, Wiki, and issue are updated together, and every user decision is traced to a section.
