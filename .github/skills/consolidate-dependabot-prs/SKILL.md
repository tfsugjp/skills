---
name: consolidate-dependabot-prs
description: Consolidates multiple open Dependabot pull requests in a GitHub (github.com or GitHub Enterprise) repository into a single PR backed by one English tracking issue, then iterates on reviewer/Copilot feedback until the PR is clean and mergeable. Use this whenever someone wants to merge/combine/consolidate/clean up a pile of Dependabot PRs, reduce dependency-bump noise, or says things like "dependabotのPRをまとめて" or "combine these dependency update PRs into one". Always drafts a plan and gets explicit confirmation before creating issues, opening PRs, or closing anything — these are hard-to-reverse, collaborator-visible actions.
---

# Consolidate Dependabot PRs

## When to use this

Trigger whenever someone wants to fold several open Dependabot PRs into one: "dependabotのPRをまとめて one PR にして", "consolidate the Dependabot PRs and open an issue for it", "too much Dependabot noise, combine them", "clean up this backlog of dependency bump PRs", etc.

## Why this workflow exists

Dependabot opens one PR per dependency bump. A repo that's gone a few weeks without attention can easily accumulate 5-10+ of these. Reviewing and merging them one at a time is tedious, and — worse — several of them often touch the *same line or file* (e.g. three separate PRs each bumping a sibling package of the same vendor in one `.csproj`), so merging them in sequence turns into a conflict-resolution slog. Folding them into a single PR backed by one tracking issue turns N review cycles into one, while still preserving a paper trail of what was bumped and why.

## The workflow — six phases, always in this order

### Phase 0 — Detect, then propose a plan and WAIT for confirmation

1. Confirm the remote is GitHub-flavored (`git remote -v` — github.com or a GitHub Enterprise host). This skill leans on the `gh` CLI and GitHub's REST/GraphQL APIs; if the remote is GitLab, Bitbucket, etc., stop and say so.
2. List the open Dependabot PRs:
   ```
   gh pr list --repo <owner>/<repo> --state open --author app/dependabot \
     --json number,title,headRefName,baseRefName,body,url
   ```
3. **Fewer than 2 PRs found → stop and say so.** There's nothing to consolidate; closing a single Dependabot PR to reopen an equivalent one would be pure churn.
4. **Two or more found → draft a plan and show it before touching anything**, covering:
   - The PRs you found (numbers + titles), so the user can sanity-check the list
   - The issue you intend to open (draft title + a one-line description of what the body will contain)
   - The consolidated PR you intend to open (draft title + the branch name you'll create it from)
   - The fact that every listed PR will get a comment and then be closed

   This confirmation step is not ceremony — creating an issue, opening a PR, and closing N other PRs are all visible to every collaborator on the repo and annoying to cleanly undo. **Wait for an actual reply in the conversation before Phase 1** — even if the original request already described this exact workflow in detail, "please consolidate the Dependabot PRs" is a request to *do the job*, not pre-authorization for the specific list of artifacts you're about to create with specific names and numbers neither of you had in front of you yet. If the user has clearly pre-approved this kind of run (e.g. "yes, go all the way through, don't stop to ask"), a brief "found 7 PRs, opening issue X / PR Y, will close #a #b #c — proceeding" is enough to keep them in the loop without blocking on it; otherwise, stop and ask.

### Phase 1 — Open the tracking issue, in English

```
gh issue create --repo <owner>/<repo> \
  --title "chore: consolidate Dependabot dependency updates (<month/year>)" \
  --body "..."
```

Write the body so a future maintainer can scan it in ten seconds:
- A one-paragraph summary of why this consolidation exists
- A table of the *actual* dependency/version changes — derive this from each PR's diff (Phase 2, step 2), not from titles, which can be stale or incomplete
- A bulleted list of the original Dependabot PR numbers with a one-line description each, so anyone can trace which original PR contributed which change

Keep the issue in English even if the conversation with the user is in another language — Dependabot's own PRs and most dependency ecosystems are English-first, and an English issue stays legible to the broadest set of collaborators and tooling.

### Phase 2 — Build the consolidated branch by editing to the target state directly

1. Branch from the default branch:
   ```
   git fetch origin && git checkout -b chore/consolidate-dependabot-<date> origin/<default-branch>
   ```
2. **Read each Dependabot PR's actual diff — never trust the title alone:**
   ```
   gh pr diff <PR#> --repo <owner>/<repo>
   ```
   The diff is ground truth for exact version strings, pinned commit SHAs, and file locations. Titles get out of sync with reality more often than you'd expect (we once found a PR titled "bump from 6.0.0 to 6.0.1" whose target file had a comment claiming a totally different prior version — the comment was simply wrong, and only the diff + an independent check against the dependency's actual release tags revealed the truth).
3. **Before editing anything, group the PRs by which file *and* which package/action they touch.** When two-plus PRs edit overlapping lines (three PRs each bumping a different sibling of the same vendor package, say), cherry-picking them in sequence produces a cascade of merge conflicts — each branch was written against a "current main" that the others have since changed. Skip that entirely: open each affected file once, and edit every line straight to its final target version, covering the union of everything any overlapping PR wanted. One clean diff, zero conflict chain.
4. Commit with a message enumerating every bump (grouped by ecosystem — NuGet/npm/pip/Actions/etc. reads cleaner than a flat list) and ending with `Closes #<issue-number>`. Push and set upstream.

### Phase 3 — Open the consolidated PR

```
gh pr create --repo <owner>/<repo> \
  --title "chore: consolidate Dependabot dependency updates (<month/year>)" \
  --body "..."
```

The description should *merge the substance* of every original PR's description — not just point at them. Include:
- `Closes #<issue-number>` so the tracking issue auto-closes on merge
- A table of every package/action bumped, old → new (keep this consistent with the issue's table — same source data)
- A "Supersedes" section naming every original Dependabot PR by number with a one-line description, so a reviewer can audit that nothing was dropped

### Phase 4 — Close the originals, pointing at the new PR

Only after the consolidated PR exists (if PR creation fails partway, you don't want orphaned closures pointing at nothing):

```
gh pr close <N> --repo <owner>/<repo> \
  --comment "Superseded by consolidated PR #<new-PR#> which includes this change. See also issue #<issue-number>."
```

Do this for every PR collected in Phase 0.

### Phase 5 — Iterate until the new PR is actually mergeable

This is the phase that takes patience. Loop until **both** are true:
- `gh pr checks <PR#> --repo <owner>/<repo>` — every required check passes
- `gh pr view <PR#> --repo <owner>/<repo> --json mergeable,mergeStateStatus` — shows `mergeable: MERGEABLE` and `mergeStateStatus: CLEAN`

Inside the loop:

1. **Read reviewer feedback** (Copilot or human): `gh api repos/<owner>/<repo>/pulls/<PR#>/reviews` and `.../comments`. Each comment carries a `commit_id` / `original_commit_id` — match it against your latest pushed SHA so you're not re-litigating issues you already fixed on an earlier commit.
2. **Verify before you "fix."** Automated reviewers can be confidently wrong — e.g. trusting a stale inline comment in the code over the actual state of the world. Before changing anything in response to a claim about a version, hash, or behavior, independently check it (e.g. `gh api repos/<dep-owner>/<dep-repo>/tags` to see what a commit SHA is *actually* tagged as). If your check shows the reviewer is mistaken, reply to their comment with your evidence and move on to resolving the thread (step 4) — don't introduce an incorrect change just to silence a wrong comment. If the reviewer is right, edit, commit, push.
3. **Re-request review after every fix-push** — reviews are tied to specific commits, and most bots won't automatically re-review on push:
   ```
   gh api repos/<owner>/<repo>/pulls/<PR#>/requested_reviewers --method POST \
     -f "reviewers[]=<reviewer-bot-login>"
   ```
   (Find the right login from the existing review's `user.login`, e.g. `copilot-pull-request-reviewer[bot]`.)
4. **If `mergeStateStatus` is stuck on `BLOCKED` despite all-green checks**, look for a ruleset requiring review-thread resolution before assuming something's broken with CI:
   ```
   gh api repos/<owner>/<repo>/rulesets/<id>   # look for required_review_thread_resolution: true
   ```
   The REST API cannot resolve review threads — use GraphQL. See `references/graphql-snippets.md` for ready-to-run queries that list open threads and resolve them via `resolveReviewThread`.
5. **Conflicts**: if the default branch moves and `mergeable` flips to `CONFLICTING`, merge/rebase the default branch into your consolidation branch, resolve, push — and loop back to step 1, since a new push means a new review cycle.

Stop when checks are green, `mergeStateStatus: CLEAN`, and the latest review (against your latest commit) raises nothing actionable. Report the final PR URL plus a short log of every fix you made — that trail is genuinely useful to whoever clicks the merge button.

## Pitfalls worth knowing about up front

- **Run `gh` with `--repo owner/name` or from inside the repo directory.** From elsewhere it fails with "could not determine current branch" — `--repo` is the more robust choice for non-interactive runs.
- **Don't cherry-pick overlapping Dependabot branches.** Tempting, but it produces a cascade of merge conflicts. Reading the target state and editing files directly is faster and yields a cleaner diff and history.
- **`mergeStateStatus: BLOCKED` with all checks green is very often an unresolved-review-thread issue**, not a CI problem — go check the rulesets before you spend time re-running pipelines.
- **Close the originals only after the new PR exists** — this way a failed PR-creation attempt can simply be retried without having burned the source PRs you'd point at.
- **A reviewer being wrong is a normal outcome, not an edge case.** Verify claims about versions/hashes/behavior against ground truth before changing code to satisfy them.

## Reference

- `references/graphql-snippets.md` — ready-to-run GraphQL for listing and resolving PR review threads (no REST equivalent exists for this)
