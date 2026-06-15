---
name: m365-message-center-new-unread
description: 'Retrieve newly created, unread Microsoft 365 Message Center announcements for a specified period. Use when asked to find new M365 Message Center posts, exclude updates to older announcements, filter unread service announcements, or report recent Microsoft 365 changes through Microsoft Graph PowerShell.'
---

# Microsoft 365 Message Center New Unread

Retrieve unread Message Center announcements whose `lastModifiedDateTime` is within a
specified period, while excluding posts that Microsoft identifies as updates to older
announcements.

## Prerequisites

- Use PowerShell 7 or later.
- Install `Microsoft.Graph.Authentication` and
  `Microsoft.Graph.Devices.ServiceAnnouncement`.
- Connect with a delegated work or school account and the
  `ServiceMessage.Read.All` scope:

```powershell
Connect-MgGraph -Scopes 'ServiceMessage.Read.All' -ContextScope Process
```

Do not use app-only authentication. Microsoft Graph returns `viewPoint` as `null` for
application permissions, so unread status cannot be determined.

## Workflow

1. Ask the user for both the start and end timestamps if either is missing.
2. Interpret the period as start-inclusive and end-exclusive.
3. Connect to Microsoft Graph with delegated `ServiceMessage.Read.All` permission.
4. Run the bundled script:

```powershell
./scripts/Get-M365MessageCenterNewUnread.ps1 `
  -StartDateTime '2026-06-01T00:00:00+09:00' `
  -EndDateTime '2026-06-08T00:00:00+09:00' `
  -Verbose
```

5. Present the returned announcements in descending `LastModifiedDateTime` order.

Use `-Verbose` when no objects are returned. It reports the number of messages retrieved,
within the requested period, unread, and remaining after each update exclusion rule. An
empty standard output with `New unread messages returned: 0` is a valid zero-result query.

The script retrieves every page with `Get-MgServiceAnnouncementMessage -All`. It keeps
only messages that meet all of these conditions:

- `lastModifiedDateTime` is within the requested period.
- `viewPoint.isRead` is explicitly `false`.
- `tags` does not contain `Updated message`.
- `title` does not begin with `(Updated)`.

Use `lastModifiedDateTime` as the date criterion. Do not substitute or compare
`startDateTime`.

## Output

Return objects containing:

- `Id`
- `Title`
- `LastModifiedDateTime`
- `Services`
- `Category`
- `Severity`
- `ActionRequiredByDateTime`

Keep this workflow read-only. Never call `markRead`, `markUnread`, archive, favorite, or
other Message Center mutation operations.

## Errors

- If `viewPoint` is `null`, stop and explain that delegated authentication is required.
- If the Graph modules are missing, identify the required modules without installing
  them unless the user approves installation.
- If the Graph session is missing or does not include `ServiceMessage.Read.All`, ask the
  user to reconnect with the required delegated scope.
- If the end timestamp is not later than the start timestamp, ask for a valid period.

## References

- [List serviceAnnouncement messages](https://learn.microsoft.com/en-us/graph/api/serviceannouncement-list-messages?view=graph-rest-1.0)
- [serviceUpdateMessage resource](https://learn.microsoft.com/en-us/graph/api/resources/serviceupdatemessage?view=graph-rest-1.0)
- [serviceUpdateMessageViewpoint resource](https://learn.microsoft.com/en-us/graph/api/resources/serviceupdatemessageviewpoint?view=graph-rest-1.0)
