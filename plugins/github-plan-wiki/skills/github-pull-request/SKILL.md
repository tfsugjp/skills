---
name: github-pull-request
description: 'Create GitHub pull requests or update their descriptions while following repository PR templates, reconciling issue acceptance criteria and artifacts, and requiring a closing keyword for every completed issue. Use for GitHub PR creation, PR body edits, and correcting missing or grouped issue-closing references. Does not implement code, merge PRs, or close issues manually.'
---

# GitHub Pull Request

Use the repository's existing GitHub tooling and authorization. Apply these requirements to CLI, connector, and browser writes alike. A request to draft a body permits local preparation only; do not publish until authorized.

## Inspect the repository and templates

- Resolve the target repository, default branch, intended base/head, existing PR (if any), and completed tracking issues. Read the actual issue type, labels, acceptance criteria, and implementation evidence before deciding which issues this PR completes. If the issue links to an artifact or its scope has a separate plan, research, design, or other detailed record, read the current Issue Artifacts before assessing the relevant criteria. Keep the issue body's acceptance checklist as the canonical place to record criterion completion; artifacts supply detail and context but do not replace that checklist.
- Read applicable repository instructions and contributing guidance. Inspect templates on the default branch: `PULL_REQUEST_TEMPLATE.*` in the root, `docs/`, and `.github/`, and template directories `PULL_REQUEST_TEMPLATE/` in those locations (case-insensitive). If none exist, check applicable inherited templates in the owner's public `.github` repository. An access failure does not prove templates are absent.
- Select the PR template matching the change. Preserve its sections, required fields, checklist wording, and title conventions; fill fields from evidence and leave unverified checks unchecked. CLI `--body-file` and connector bodies do not automatically apply templates: render the selected template into the submitted file yourself. For a body update, preserve existing useful content and completed template fields.
- If creating a tracking Issue is also authorized, use [github-plan-issues](../github-plan-issues/SKILL.md) and follow the repository's Issue template or form. Do not create extra issues merely to satisfy this skill.

## Reconcile acceptance criteria

For every issue the PR is intended to complete or advance, read its current body and identify the acceptance criteria and task-list checkboxes. Assess each criterion separately against concrete implementation and verification evidence from the PR. A PR reference, a statement that work is done, or an unchecked sibling criterion is not evidence by itself. If a criterion is ambiguous or its evidence is missing, leave it unchecked and identify the gap in the PR description or status report.

Before preparing a closing entry, decide whether the PR completes the issue as a whole. If it delivers only part of the issue, keep the issue reference-only and leave its remaining criteria open; do not use a closing keyword. Keep unfinished parent issues reference-only while any child or acceptance criterion remains incomplete. Use the per-issue closing rules below only for issues whose full scope is evidenced as complete.

When the request authorizes creating or updating the PR, updating the related Issue checklist is part of this workflow, performed only after the PR write succeeded, was read back, and the PR-to-Issue relationship described in the next paragraph was verified (a failed or unverified PR or link leaves every checklist untouched). The checked state reflects the evidence at PR time; if the PR is later closed unmerged, report the boxes that need reverting. Preserve the issue title, prose, headings, ordering, and unrelated checkboxes. Change only acceptance-criterion boxes whose completion is directly supported by the implementation and verification evidence; never check a box merely because a PR was opened or linked. Immediately before writing, re-read the issue body and compare it with the baseline you assessed; if it changed, re-assess against the fresh body. Because a re-read cannot close the gap before the write, use a conditional update when the interface supports one (for example an `updated_at`/ETag precondition); otherwise read the body back immediately after writing and, if it lacks a concurrent change that appeared between your fresh read and the write, report the possible overwrite and restore from the fresh body plus that change rather than leaving it. Submit the complete updated body through the available authorized GitHub interface, then read it back and verify that it equals the fresh body plus only the intended box changes. If the interface cannot safely preserve and update the body, do not overwrite it: leave the checklist unchanged and report which verified items still need an update. Do not close or reopen an Issue through this checklist update.

Right after PR creation or update, and before any checklist write, verify both sides of the relationship: the PR's linked issues/`closingIssuesReferences` for issues intended to close, and the Issue timeline or linked-PR view for related issues that remain open. A body mention alone is not proof of a relationship. Report completed criteria, unchecked or unverified criteria, and any missing link separately. The PR write and checklist update must each be read back; an ambiguous write is checked for its persisted result before retrying.

An artifact read as described in the first bullet is supporting context only; its claim alone does not prove a criterion. If required artifact content is unavailable or unreadable, leave dependent criteria unchecked and report the evidence gap. Use [github-issue-artifacts](../github-issue-artifacts/SKILL.md) for artifact discovery, creation, or updates.

## Closing entries: mandatory per completed issue

Put one standalone entry per issue in the template's related-issues section, or append a small related-issues section if it has none. Use plain text or an ordinary Markdown bullet, outside comments, quotes, and code:

- **Bug fixed by this PR:** `Fixed #10`, then `Fixed #11` on another line.
- **Other work completed by this PR:** `Close #20`, then `Close #21` on another line.
- **Mixed work:** select the keyword per issue: `Fixed #10` and `Close #20` on separate lines.
- **Different repository:** use `Fixed owner/repository#10` or `Close owner/repository#20`, with the full reference repeated for every issue.

Never use `Refs #10` as a substitute for a closing entry, or group issues behind a single keyword (`Close #10, #11`, `Fixed #10, #11`). Every completed issue must have its own `Fixed` or `Close` keyword immediately before its reference. Reference-only issues may appear elsewhere as `Refs #30`; never close unfinished work, a prerequisite, or a parent issue whose remaining sub-issues are incomplete. If the PR closes no issues, explicitly select reference-only validation below.

GitHub interprets PR-body closing keywords only when the PR targets the repository's default branch, and closes issues after merge. For another base, retain the entries but report that automatic closure is deferred until a qualifying PR reaches the default branch. Do not change the requested base or close issues manually to compensate.

## Validate before writing

Save the complete template-based body as a real UTF-8 file with actual newlines. Run [scripts/validate_closing_keywords.py](scripts/validate_closing_keywords.py) with **every intended closure target**, derived from the issues and work scope, not extracted from the drafted body. Repeat `--bug` or `--close` for each target; numeric targets belong to `--repo`, fully qualified targets belong to the specified repository. Fix errors before any write. The same preflight is mandatory for creation and body updates.

GitHub also closes issues from closing keywords in the messages of commits merged into the default branch, and these are not reflected in `closingIssuesReferences`. Save the full messages (headline and body) of every commit in the PR's `base..head` range to a UTF-8 file, for example with `git log --format='%B' '<base>..<head>'` or the PR's `commits` JSON, and pass it with `--commit-messages "$commits_file"`. Any commit-message closing keyword for an issue outside the intended closure set fails validation; reword the commit or rewrite its history only with authorization, otherwise report it.

```bash
set -e
python3 "<skill-dir>/scripts/validate_closing_keywords.py" "$body_file" \
  --repo '<owner>/<repo>' --bug 10 --bug 11 --close 20 --commit-messages "$commits_file"
# For a PR with no completed issues, use --reference-only instead of target flags.
gh pr create --repo '<owner>/<repo>' --base '<base>' --head '<head>' \
  --title '<template-compatible title>' --body-file "$body_file"
```

```powershell
python '<skill-dir>/scripts/validate_closing_keywords.py' $bodyFile `
  --repo '<owner>/<repo>' --bug 10 --bug 11 --close 20 --commit-messages $commitsFile
if ($LASTEXITCODE -ne 0) { throw 'PR closing keyword validation failed.' }
gh pr create --repo '<owner>/<repo>' --base '<base>' --head '<head>' `
  --title '<template-compatible title>' --body-file $bodyFile
if ($LASTEXITCODE -ne 0) { throw 'PR creation failed; inspect existing PRs before retrying.' }
```

In PowerShell, write with `[IO.File]::WriteAllText($bodyFile, $body, [Text.UTF8Encoding]::new($false))`. For updates, use `gh pr edit <number> --repo <owner>/<repo> --body-file <file>` or the equivalent connector operation. Preserve requested draft state and other PR metadata.

The validator intentionally accepts only standalone `Fixed`/`Close` entries, rejects missing, wrong-type, or unplanned closing entries, and excludes comments, code, and blockquotes; text indented under a list item is treated as visible unless it is indented four or more columns past the item's content. It does not establish issue completion, template compliance, or GitHub linkage; verify those separately.

## Read back and verify

After a successful write, read the PR's persisted `body`, `baseRefName`, and `headRefName` (for example, `gh pr view <number> --repo <owner>/<repo> --json body,baseRefName,headRefName,closingIssuesReferences`). Compare the body to the submitted file, normalizing CRLF to LF, and run the validator on the persisted body with the same target flags and the current commit messages (`commits` JSON field or `git log`), since commits may have been added after the write. Verify base/head and, when targeting the default branch, confirm every intended target appears in `closingIssuesReferences` or GitHub's linked-issue view. Missing linkage remains an incomplete result even if the text looks correct.

Correct a mismatch within the authorized PR body-edit scope and read back once more. If it persists, stop and report the discrepancy; do not loop or create another PR. A failed or ambiguous creation must first be checked for an already-created PR before retrying. Report the PR link, closure targets, and any non-default-base limitation. Creation does not prove the issues are already closed.

## Sources

- [GitHub: linking a pull request to an issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue)
- [GitHub: issue and pull request templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates)
