<!--
Template for a plan page: /<repo>/plan/<id>-<slug>
Write headings and prose in the language the existing wiki uses.
Before the pull request exists, write "Not yet created" in the PR row and update it after creation.
Remove this comment before publishing.
-->

# <Plan title>

| Item | Details |
| --- | --- |
| Work Item | #<id> |
| Repository | [<repo>](https://dev.azure.com/<org>/<project>/_git/<repo>) |
| Branch | <feature/<id>-<description>> |
| PR | [!<pr>](https://dev.azure.com/<org>/<project>/_git/<repo>/pullrequest/<pr>) |
| Status | <Planned, In progress, Completed, or the remaining open point> |

## Related Work Items

| ID | Type | Contents |
| --- | --- | --- |
| #<id> | <Feature> | <title> |
| #<child-id> | <Task> | <title> |

---

## 1. Purpose

<What this plan delivers and the requirements it satisfies.>

## 2. Current state

<Facts discovered before implementation and their impact.>

## 3. Design

<Approach, resources or components, and the alternatives that were rejected.>

## 4. Implementation steps

1. <step>

## 5. Acceptance criteria

- <criterion>

---

## Constraints found during implementation

| Constraint | Resolution |
| --- | --- |
| <constraint> | <resolution> |

<Point to the repository ADR and task records by path, for example `docs/adr/` and `docs/task.md`.>
