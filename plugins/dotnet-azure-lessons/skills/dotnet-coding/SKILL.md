---
name: dotnet-coding
description: 'Implementation rules for C# and .NET code, learned from review findings and regressions. Use while writing or changing C# that handles JSON-RPC or WebSocket connections and notification handlers, Channel-based queues, ObservableCollection or list updates during an async send, enum or option parsing, duplicate detection keys, optional versus null configuration values, file paths, CLI exit codes and result messages, or localhost/loopback connections. Not for Visual Studio Remote UI XAML or view-model binding (vs-extension-remote-ui) or PowerShell (powershell-scripting).'
---

# .NET Coding

Each rule is a defect that shipped or reached review at least once. Apply it while writing the code and add the test named in the check.

## When not to use

- Remote UI view models, `[DataMember]`, and XAML: use `vs-extension-remote-ui`.
- Architecture decisions (state ownership, version gates): use `dotnet-architecture-design`.
- NuGet package version choice: use `nuget-validate`.

## Rules

### 1. Never await a request on the same connection inside a notification handler

- **Rule:** A handler that runs on a connection's read loop must not send a request on that connection and await the response. Queue the follow-up work to another task or a channel. Keep the read loop alive: catch and log handler exceptions, including `OperationCanceledException` from the handler itself.
- **Check:** A test sends a notification whose handler issues a request over a real pipe or socket and completes within the timeout.
- **Why:** A sign-in notification awaited an account read on the same JSON-RPC connection; the response sat behind the blocked parse loop until the 15-second timeout.

### 2. Process ordered notifications through one consumer

- **Rule:** Write notifications to a `Channel<T>` and read them with one consumer (`ReadAllAsync`). Do not start a task per notification when order matters. The read loop must not block on the channel: use an unbounded channel, or a bounded one written with `TryWrite` and an explicit overflow policy (for example `BoundedChannelFullMode.DropOldest` for progress deltas, or fail the connection). The consumer follows rule 1 and never awaits a response on the same connection inline.
- **Check:** A test sends A, B, C and asserts the handler observed A, B, C; a test fills the queue and shows the read loop still parses responses.
- **Why:** Parallel handling reordered message deltas and turn completion.

### 3. Clear only what you sent

- **Rule:** After an async send succeeds, remove only the items captured in the send snapshot (by reference or ID). Never call `Clear()` on a collection the user can modify during the send.
- **Check:** A test adds an item while the send is pending and asserts it remains.
- **Why:** `Attachments.Clear()` after a successful send deleted attachments added while the send was in flight.

### 4. Reject unknown enum and option values

- **Rule:** Parse modes and kinds strictly. When `Enum.TryParse` fails or a string is not in the known set, throw or report a validation error; do not fall back to a default.
- **Check:** A test passes an unknown value and expects the error. XML documentation that says malformed values throw matches the behavior.
- **Why:** An unknown `Mode` silently became `include`, contradicting the documented behavior and producing a wrong plan.

### 5. Include every distinguishing field in uniqueness keys

- **Rule:** Duplicate detection keys include every field that changes meaning, such as mode, type, or scope, not only the target and group.
- **Check:** A test with the same target in include and exclude mode passes validation.
- **Why:** Keying on `Target|GroupId` rejected a valid include/exclude pair as a duplicate.

### 6. Keep omitted, null, and value distinct

- **Rule:** For configuration that is imported, exported, or applied, model omitted, explicit `null`, and a value as three states (`Optional<T>`, a nullable wrapper with a presence flag, or `JsonElement.ValueKind`). Write `null` back only when the source had it.
- **Check:** A round-trip test covers all three states, and the serialized request for a delete or reset matches the receiver's required fields.
- **Why:** An explicit `null` meaning "any app" was treated as omitted and pinned to a specific app on apply; a delete request with `null` failed because the receiver required the field.

### 7. Use Path APIs for paths

- **Rule:** Use `Path.GetFileName`, `Path.Combine`, and related APIs. Never split on `\` or `/`.
- **Check:** Tests run on Windows and Linux paths.
- **Why:** A naming helper split on a hard-coded separator and broke on another OS.

### 8. Make result messages agree with the exit code

- **Rule:** Derive the final message from the same counts that decide the exit code. When any item failed, do not print a success or dry-run-complete message.
- **Check:** A test with one failure asserts a non-zero exit code and a failure summary.
- **Why:** A CLI printed "Dry run: no changes were applied." even when items failed.

### 9. Try every loopback address

- **Rule:** When connecting to `localhost`, try each resolved loopback address (`::1` and `127.0.0.1`) until one connects. Do not pin the first IPv4 result.
- **Check:** A test with a server listening only on IPv6 loopback connects.
- **Why:** A client that preferred IPv4 could not reach a server that listened only on `::1`.

### 10. Parse every input shape the user named

- **Rule:** When adding a parser or recognizer, list the input shapes in the request (single and multiple questions, intermediate and final messages) and add one test per shape before implementing.
- **Check:** The test list matches the request wording.
- **Why:** A choice recognizer handled only a single question in the last message and had to be extended twice.

## Done checklist

- [ ] No notification handler awaits a request on its own connection; the read loop survives handler exceptions.
- [ ] Ordered streams use one consumer and have an order test.
- [ ] Post-send cleanup removes only the snapshot.
- [ ] Unknown enum values fail.
- [ ] Uniqueness keys include every distinguishing field.
- [ ] Omitted, null, and value round-trip distinctly.
- [ ] Paths use `System.IO.Path`.
- [ ] Messages match exit codes.
- [ ] Loopback connections try IPv6 and IPv4.
- [ ] Each requested input shape has a test.
