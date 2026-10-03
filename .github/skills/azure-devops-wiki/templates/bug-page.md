<!--
Template for a bug fix plan page: /<repo>/bug/<id>-<slug>
Write headings and prose in the language the existing wiki uses.
Before the pull request exists, write "Not yet created" in the PR row and update it after creation.
Write "None" in the Related feature row when the Bug has no related Feature-equivalent item.
Remove this comment before publishing.
-->

# <Bug title>

| Item | Details |
| --- | --- |
| Work Item | #<id> |
| Related feature | #<feature-id> |
| Repository | [<repo>](https://dev.azure.com/<org>/<project>/_git/<repo>) |
| Branch | <bugfix/<id>-<description>> |
| PR | [!<pr>](https://dev.azure.com/<org>/<project>/_git/<repo>/pullrequest/<pr>) |
| Status | <Investigating, Fix planned, Fixed, Verified> |

## Symptoms

<What failed, where, and the observed error output in a fenced code block.>

## Root cause

<Why it failed, with the evidence that confirms the cause.>

## Fix approach

<The fix and why it is correct. Show configuration or code fragments; give both Bash and
PowerShell 7 variants for shell commands.>

## Fix steps

1. <step>

## Acceptance criteria

- <criterion>

## Verification and tracking

<How the fix was reproduced and verified, what was not verified, the fix commit, and the PR.>
