---
name: github-issue-artifacts
description: 'Create or update GitHub Issue Artifacts when an issue needs a long supporting record or richer material such as a plan, research, design, root-cause analysis, external links, or an interactive visualization. Keep the issue body concise, link the artifact, and verify both writes.'
---

# GitHub Issue Artifacts

Use Issue Artifacts for detailed records that would make an issue body long or that benefit from being maintained and versioned as a separate document. Do not invent a word-count threshold. Plans, research, designs, root-cause analyses, prototypes, and visualizations commonly belong in artifacts. Keep the issue body focused on a concise summary, acceptance criteria, and any parent/child checklist; add a link to the supporting artifact.

## Choose and prepare the artifact

- Follow the repository's issue template and existing issue structure. Preserve required fields and keep acceptance criteria in the issue body, where progress can be reviewed and checked.
- Use the plan type for an implementation plan, generic for Markdown research or other detailed documents, link (an http(s) URL) for a named external resource, and embedded_html only for an intentional interactive visualization. Treat HTML as active content: use it only when appropriate and explain that its preview renders user-provided code.
- Before editing an issue with detailed content, inspect its current body and list its attached artifacts. Read the current version of any artifact that may be updated. Edit an existing artifact when it is the same continuing record, preserving its version history; otherwise create a clearly named artifact.
- For a new issue, create it with the concise summary and acceptance criteria first, then create the artifact and update the issue body with the artifact link. For an existing issue, create or update the artifact and add or maintain its link in the body.

## Write and verify

Issue Artifacts and `gh issue artifact` are in preview and may change. Confirm that `gh issue artifact --help` works before writing; run `gh <command> --help` for flags if they differ from below.

```bash
gh issue artifact list <issue> --json number,name,type,url
gh issue artifact create <issue> --name "<name>" --type <generic|plan|embedded_html> --body-file <file>
gh issue artifact create <issue> <https-url>
gh issue artifact view <issue> <artifact-number> --json body,type,versions
gh issue artifact edit <issue> <artifact-number> --body-file <file>
```

A file argument takes its artifact name from the file (`<file>#<name>` overrides it); `.html` files become `embedded_html`, and `plan` currently behaves like `generic`. Pass `--body-file` as a UTF-8 file.

After creating or editing an artifact, list and view it. Verify the issue, name, type, and full content against the intended document. Read the issue body back and verify the summary, acceptance criteria, and artifact link. Treat a failed or mismatched read-back as incomplete; check the persisted state before retrying an ambiguous write.

If `gh issue artifact` is unavailable, permissions are insufficient (artifact creation requires issue write permission), or verification fails, do not silently drop the detail and do not stuff it into the issue body or a comment. Keep the concise issue intact, publish the detail through the Wiki workflow when a plan is approved, report the artifact work as incomplete with the limitation, and ask the user where the detail should go.

## Boundaries

- Creating an artifact does not authorize creating, closing, or changing the state of an issue. Follow the caller's authorization for each issue mutation.
- When working from an approved implementation plan, continue the repository's required Wiki publication workflow; an Issue Artifact supplements that publication.
- For PR acceptance checks, the issue body's checklist remains canonical. Use artifacts as supporting context, then verify each criterion against implementation and test evidence using [github-pull-request](../github-pull-request/SKILL.md).

[github-plan-issues](../github-plan-issues/SKILL.md) hands detailed records to this skill.
