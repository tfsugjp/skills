# GraphQL snippets: PR review threads

The REST API exposes review *comments* but has no concept of review *threads* —
and critically, no way to mark a thread "resolved". Many rulesets require
`required_review_thread_resolution: true` before a PR can merge, which silently
manifests as `mergeStateStatus: BLOCKED` even though every status check is green.
GraphQL is the only way to see and clear this.

## 1. List review threads and their resolved state

```bash
gh api graphql -f query='
query {
  repository(owner: "OWNER", name: "REPO") {
    pullRequest(number: PR_NUMBER) {
      reviewThreads(first: 50) {
        nodes {
          id
          isResolved
          comments(first: 1) {
            nodes { path body }
          }
        }
      }
    }
  }
}' --jq '.data.repository.pullRequest.reviewThreads.nodes[]
         | {id, isResolved, path: .comments.nodes[0].path, snippet: (.comments.nodes[0].body[:80])}'
```

Each thread's `id` looks like `PRRT_kwDOSGxp-M6Hmu6O` — opaque, GraphQL-specific,
and different from the REST API's numeric comment IDs. Collect the IDs of every
thread where `isResolved` is `false`.

## 2. Resolve a thread

```bash
gh api graphql -f query='
mutation {
  resolveReviewThread(input: {threadId: "THREAD_ID"}) {
    thread { id isResolved }
  }
}' --jq '.data.resolveReviewThread.thread'
```

Loop this over every unresolved thread ID gathered in step 1. After resolving
all of them, re-check `gh pr view <PR#> --json mergeStateStatus` — it should
flip from `BLOCKED` to `CLEAN` within a few seconds (no need to wait on CI again,
since the checks were already green).

## 3. Confirm what's actually blocking the merge (before assuming it's threads)

```bash
gh api repos/OWNER/REPO/branches/DEFAULT_BRANCH/protection 2>&1   # classic branch protection (404 if none)
gh api repos/OWNER/REPO/rulesets --jq '.[] | {id, name, target}'
gh api repos/OWNER/REPO/rulesets/RULESET_ID --jq '.rules[] | {type, parameters}'
```

Look for a `pull_request` rule with `"required_review_thread_resolution": true`,
or a `required_status_checks` rule naming a check that hasn't reported yet. Don't
assume — read the actual rule parameters, since `BLOCKED` can stem from several
different rule types (required reviewers, required checks, thread resolution,
linear-history requirements, etc.) and the fix differs for each.

## 4. Replying to a specific review comment (to leave evidence before resolving)

If you've verified a reviewer's claim is wrong and want to leave a documented
rebuttal before resolving the thread, reply via REST (this part *does* have a
REST endpoint):

```bash
gh api repos/OWNER/REPO/pulls/comments/COMMENT_ID/replies \
  --method POST \
  --raw-field body="Verified via <method>: <evidence>. No change needed — the
original inline comment in the file was already stale before this PR."
```

Then resolve the thread via the mutation in step 2. This leaves a clean audit
trail for any human who reads the PR later: the claim, the rebuttal with
evidence, and the resolution — all in one place.
