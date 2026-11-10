---
name: dotnet-coding
description: 'Implementation rules for C# and .NET code, learned from review findings and regressions. Use while writing or changing C# that handles JSON-RPC or WebSocket connections and notification handlers, Channel-based queues, ObservableCollection or list updates during an async send, enum or option parsing, duplicate detection keys, optional versus null configuration values, file paths, CLI exit codes and result messages, or localhost/loopback connections. Not for Visual Studio Remote UI XAML or view-model binding (vs-extension-remote-ui) or PowerShell (powershell-scripting).'
---

# .NET Coding

Each rule is a defect that shipped or reached review at least once. Apply it while writing the code and add the test named in the check.

## When not to use

- Remote UI view models, `[DataMember]`, and XAML: `vs-extension-remote-ui`.
- State ownership and version gates: `dotnet-architecture-design`.
- NuGet package versions: `nuget-validate`.

## Rules

### 1. Never await a request on the same connection inside a notification handler

- **Rule:** A handler running on a connection's read loop must not send a request on that connection and await the response; queue the follow-up to another task or a channel. Keep the read loop alive: catch and log handler exceptions, including the handler's own `OperationCanceledException`.
- **Check:** A test sends a notification whose handler issues a request over a real pipe or socket and completes within the timeout.
- **Why:** A sign-in notification awaited an account read on the same JSON-RPC connection; the response sat behind the blocked parse loop until a 15-second timeout.

### 2. Process ordered notifications through one consumer

- **Rule:** Write notifications to a `Channel<T>` read by one consumer (`ReadAllAsync`), not a task per notification. The read loop must not block on the channel: use an unbounded channel, or a bounded one written with `TryWrite` and an explicit overflow policy (for example `DropOldest` for progress deltas, or fail the connection). The consumer follows rule 1.
- **Check:** A test sends A, B, C and observes A, B, C; a test fills the queue and the read loop still parses responses.
- **Why:** Parallel handling reordered message deltas and turn completion and corrupted Busy/Ready transitions.

### 3. Apply async results to the original target

- **Rule:** Carry the target (and, when operations overlap, the operation ID) into success, failure, and notification handlers. Update the active view only when the target still matches. After a successful send, remove only the items captured in the send snapshot, by reference or ID.
- **Check:** Tests add an item while the send is pending and switch targets before the response arrives; the new item remains and the late result affects only its original target.
- **Why:** Send cleanup deleted newly added attachments, and a delayed result appeared in another view.

### 4. Reject unknown enum and option values

- **Rule:** When `Enum.TryParse` fails or a string is outside the known set, throw or report a validation error; never fall back to a default. When displaying data from a peer, show an unknown item type as an explicit fallback that names the type; never drop it or show it blank.
- **Check:** A test passes an unknown value and expects the error, matching the XML documentation; a display test covers an unsupported item type.
- **Why:** An unknown `Mode` silently became `include` and produced a wrong plan.

### 5. Include every distinguishing field in uniqueness keys

- **Rule:** Duplicate-detection keys include every field that changes meaning (mode, type, scope), not only target and group.
- **Check:** The same target in include and exclude mode passes validation.
- **Why:** Keying on `Target|GroupId` rejected a valid include/exclude pair.

### 6. Keep omitted, null, and value distinct

- **Rule:** Preserve the contract's distinctions between omitted, explicit `null`, empty, and other values, using a presence flag when omission and `null` differ. When merging into an existing settings file, handle each shape it contains (arrays, metadata maps) and preserve data the merge does not own.
- **Check:** Round-trip tests cover each supported state, and the serialized request matches the receiver's required fields; merge tests show existing metadata survives.
- **Why:** An explicit `null` meaning "any app" was treated as omitted, and a merge processed a metadata map as an array.

### 7. Use Path APIs for paths

- **Rule:** Use `Path.GetFileName`, `Path.Combine`, and related APIs; never split on `\` or `/`.
- **Why:** A naming helper split on a hard-coded separator and broke on another OS.

### 8. Make result messages agree with the exit code

- **Rule:** Derive the final message from the same counts that decide the exit code. When any item failed, print no success or dry-run-complete message.
- **Check:** A test with one failure asserts a non-zero exit code and a failure summary.
- **Why:** A CLI printed "Dry run: no changes were applied." even when items failed.

### 9. Try every loopback address

- **Rule:** When connecting to `localhost`, try each resolved loopback address (`::1` and `127.0.0.1`) until one connects.
- **Check:** A server listening only on IPv6 loopback is reachable.
- **Why:** A client that pinned IPv4 could not reach a server listening only on `::1`.

### 10. Parse every input shape the user named

- **Rule:** Test each requested input shape before implementing a parser or recognizer. For a parsing bug, keep the exact failing input, including markup and line boundaries; normalize only what recognition needs and preserve exclusions such as fenced code.
- **Check:** Tests cover each requested shape, the original failing input, and a similar input that must stay excluded.
- **Why:** A choice recognizer missed requested shapes, and emphasis after a question mark hid a valid question.

## Done checklist

- [ ] No notification handler awaits a request on its own connection; the read loop survives handler exceptions.
- [ ] Ordered streams use one consumer and have an order test.
- [ ] Async results stay with their original target; post-send cleanup removes only the snapshot.
- [ ] Unknown enum values fail; uniqueness keys include every distinguishing field.
- [ ] Omitted, `null`, and values round-trip; merges preserve metadata.
- [ ] Paths use `System.IO.Path`; messages match exit codes; loopback tries IPv6 and IPv4.
- [ ] Requested parser shapes, regression inputs, and exclusions have tests.
