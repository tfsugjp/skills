---
name: dotnet-coding
description: 'C#/.NET guidance for ordered notifications, async resource lifetimes, stale results, API payloads, parsing, identity keys, paths, and CLI outcomes.'
---

# .NET Coding

Apply these rules when the corresponding behavior is in scope. Add focused tests for non-obvious concurrency, parsing, payload, and resource-lifetime invariants.

## When not to use

- Visual Studio Remote UI view models and XAML: `vs-extension-remote-ui`.
- State ownership, version support, and architecture: `dotnet-architecture-design`.
- NuGet package versions: `nuget-validate`.

## Rules

### 1. Never await a request on the same connection inside a notification handler

- **Rule:** A handler called on a connection's read loop must not send a request over that same connection and await its response. Queue the follow-up elsewhere. Handle exceptions, including cancellation, so they do not terminate the read loop unexpectedly.
- **Check:** An applicable integration test sends a notification whose handler schedules the same-connection request outside the read loop. Assert the response arrives within a bounded timeout while the read loop continues processing incoming messages.
- **Why:** The response waited behind the parse loop blocked by the notification handler.

### 2. Process ordered notifications through one consumer

- **Rule:** Use one consumer for ordered notifications. Ensure queue writes do not block the connection read loop; choose capacity and overflow behavior that preserve the message semantics. Dropping deltas is unsafe when later state depends on them.
- **Check:** Relevant tests prove ordering and show the read loop still processes responses under queue pressure; overflow behavior matches the protocol.
- **Why:** Concurrent notification handlers reordered message deltas and turn completion.

### 3. Await inside using; do not return the Task

- **Rule:** Await asynchronous operations that use a local disposable before leaving its scope; do not return a task that outlives the resource.
- **Check:** A relevant delayed-I/O test completes without premature disposal.
- **Why:** A stream was disposed while its upload was still running.

### 4. Apply async results to the original target

- **Rule:** Carry target and operation identity through callbacks. Before changing either cache or visible state, reject results from superseded operations or deleted/reinitialized target instances. Update valid targets' caches even when unselected; update the visible view only for the active target. After a send, remove only items captured in its snapshot.
- **Check:** Tests cover the races the changed code permits, such as adding an item during send, switching or deleting a target, and starting a retry before an earlier callback completes.
- **Why:** Delayed results updated the wrong view, cleanup removed new items, and an earlier timer completed a later operation.

### 5. Reject unknown enum and option values

- **Rule:** Reject unknown values rather than silently using defaults when the contract defines a closed set. `Enum.TryParse` alone can accept numeric values that are not declared enum members; validate membership or the domain-specific set. For peer data, show an explicit fallback that identifies an unsupported type.
- **Check:** Applicable tests cover unknown names, undefined numeric enum values, and unsupported peer types.
- **Why:** An unrecognized mode silently became `include` and produced a wrong plan.

### 6. Include every distinguishing field in uniqueness keys

- **Rule:** A duplicate key includes every field that distinguishes valid entries, such as mode, type, or scope.
- **Check:** Tests show entries that differ in a meaningful field are accepted, while true duplicates are rejected.
- **Why:** A key that omitted mode rejected a valid include/exclude pair.

### 7. Keep omitted, null, and value distinct

- **Rule:** Preserve the external contract's distinction between omission, explicit `null`, empty, and concrete values. When merging settings, preserve data the change does not own and handle the actual container shape.
- **Check:** Relevant round-trip and merge tests cover supported states and retain unrelated metadata.
- **Why:** Explicit `null` was treated as omission, and a metadata map was processed as an array.

### 8. Validate everything before the first side effect

- **Rule:** Validate all inputs needed to complete and report a requested operation before its first upload, API write, or file mutation. Do not allow post-write result construction to fail on unvalidated input.
- **Check:** An applicable test confirms invalid input causes no remote call or file change.
- **Why:** A publish succeeded remotely, then failed while building a result from a missing platform-specific property.

### 9. Use Path APIs for paths

- **Rule:** Use `Path` APIs for paths belonging to the current platform. If parsing paths authored for another platform or a protocol, use that format's defined separator rules rather than assuming the host's `Path` behavior.
- **Check:** Relevant tests cover the path formats the feature promises on the platforms it supports.
- **Why:** Splitting a local path on a hard-coded separator failed on another OS.

### 10. Make result messages agree with the exit code

- **Rule:** Derive the final message and exit code from the same outcomes. Report failure when any item failed; do not print a success message for a partial failure.
- **Check:** A relevant CLI test covers mixed success and failure and asserts both summary and exit code.
- **Why:** A CLI printed that no changes were applied even when items failed.

### 11. Try every loopback address

- **Rule:** If the client promises to connect to `localhost`, support the loopback addresses returned by resolution instead of pinning IPv4.
- **Check:** When the implementation supports it, a test reaches a server listening only on IPv6 loopback.
- **Why:** An IPv4-only client could not reach a server listening on `::1`.

### 12. Parse every input shape the user named

- **Rule:** Preserve a parser's failing input when diagnosing a parsing bug. Test the requested shapes and nearby exclusions, including markup and line boundaries where they affect recognition. Compare archive parsing with a platform tool when that format is in scope.
- **Check:** Tests cover relevant requested shapes, the original failure, and a similar input that must remain excluded.
- **Why:** Recognition missed valid formats, and an archive parser disagreed with the native tool.
