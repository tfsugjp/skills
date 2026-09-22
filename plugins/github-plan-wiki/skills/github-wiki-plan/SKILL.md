---
name: github-wiki-plan
description: 'Publish an approved feature/refactor/perf plan to a GitHub wiki in English and Japanese, maintain category tables and last-updated dates in both Home pages, and verify every Home wiki link resolves. Use for approved wiki plans, Home index updates, and the handoff from github-plan-issues. Bug fixes, patches, and CI/CD-only changes do not trigger plan publishing by default.'
---

# GitHub Wiki Plan

Publish an approved plan to the repository's GitHub wiki as a bilingual page pair, and keep the `Home` index current. The Git path and the public wiki URL are different namespaces. Never derive a public link from the Git directory.

Only run this for `feature`/`refactor`/`perf` work — bug fixes, patches, and CI/CD-only changes don't get wiki pages.

## Phase 0 — Confirm the wiki exists and is initialized

```bash
gh repo view <owner>/<repo> --json hasWikiEnabled
git ls-remote https://github.com/<owner>/<repo>.wiki.git
```

- `hasWikiEnabled: false` → stop. Ask the user to enable the wiki in repository settings.
- `hasWikiEnabled: true` but `ls-remote` returns **`Repository not found`** → the wiki feature is on but **uninitialized**. GitHub does not materialize a wiki's git repo (nor expose any API to create one) until a first page is saved through the web UI — there is no way to `git init`/push your way around this.
  **Ask the user for explicit permission to create the Home page**, and if they agree, have them open `https://github.com/<owner>/<repo>/wiki/_new` and save an initial `Home` page. Do not proceed until that exists — a subsequent `ls-remote` should now succeed.
- `ls-remote` succeeds → proceed to Phase 1.

## Phase 1 — Clone and lay out paths

```bash
git clone https://github.com/<owner>/<repo>.wiki.git <scratch-dir>/wiki
```

GitHub preserves subdirectories in the wiki Git repository but publishes every page at a route derived from the file's basename. Keep these two namespaces separate:

| Content | Git path | Public URL |
|---|---|---|
| Plan (English) | `plan/<yyyy-MM-dd>/<slug>.md` | `https://github.com/<owner>/<repo>/wiki/<slug>` |
| Plan (Japanese) | `plan/<yyyy-MM-dd>/<slug>_ja.md` | `https://github.com/<owner>/<repo>/wiki/<slug>_ja` |
| Index (English) | `Home.md` | `https://github.com/<owner>/<repo>/wiki/Home` |
| Index (Japanese) | `Home_ja.md` | `https://github.com/<owner>/<repo>/wiki/Home_ja` |

- `<yyyy-MM-dd>` in the Git path is the plan's original approval date. Do not move a page merely because its Home `Date` changes.
- `<slug>` is lowercase, hyphen-separated, derived from the plan title.
- **Use the complete canonical public URL for every wiki-internal link.** A page stored as `plan/2026-07-19/approval-mode-picker.md` is linked as `https://github.com/<owner>/<repo>/wiki/approval-mode-picker`. A `/wiki/plan/2026-07-19/...` URL or `.md` suffix produces a 404.
- Before creating a page, search the entire wiki checkout for `<slug>.md` and `<slug>_ja.md`. For a new plan, any match is a collision. For an update, only the intended pair at the exact target paths may match. Choose a different globally unique slug instead of relying on the date directory to disambiguate it.
- The Japanese page is a translation of the same document, not a separate one — keep headings and tables in 1:1 correspondence with the English page.

## Phase 2 — Write the plan page

Start from [templates/plan-page.md](templates/plan-page.md). Include:

- Title, with a language-switch link at the top: "日本語" targets the canonical `<slug>_ja` public URL on the English page, and "English" targets the canonical `<slug>` public URL on the Japanese page
- Links to the tracking issue(s) — parent issue and its sub-issues (issue links are allowed; this is the one exception to the placeholder rule below)
- Background, design, implementation phases, verification approach — drawn from the approved plan
- **Placeholder any URL, IP address, email address, or GUID**, per the team's documentation rules — with two exceptions: same-repo issue links, and public, unauthenticated website URLs that were actually referenced while designing the plan (e.g. a reference implementation or upstream doc the plan is modeled on). Anything else — internal/authenticated endpoints, private hosts, credentials-adjacent URLs — gets a placeholder.

## Phase 3 — Update the Home index

Maintain the wiki's existing information structure:

- One introductory paragraph, plus a canonical language-switch link to the other Home page.
- Content grouped under **H2 headings by subject area**, each with a 4-column table. Use categories that fit this wiki's content, such as setup or identity when applicable; do not impose a fixed category list:

```markdown
## Slash Commands & Composer

| Plan | Date | Tracking | 日本語 |
|---|---|---|---|
| [Plan title](https://github.com/<owner>/<repo>/wiki/<slug>) | 2026-07-19 | [Issue title](https://github.com/<owner>/<repo>/issues/<n>) | [日本語](https://github.com/<owner>/<repo>/wiki/<slug>_ja) |
```

**Read both existing Home pages first** — do not copy group names from [templates/home.md](templates/home.md) mechanically. Steps:

1. Find the group that best fits the new plan's subject area and append a row to its table.
2. If no existing group fits, create a new `## ` section — and tell the user you did, since it changes the page's structure.
3. **Update `Home_ja.md` with the same row**, translated (column headers in Japanese; the "日本語" column becomes an "English" column pointing back at the non-`_ja` page). Never update only one language.
4. Audit the existing rows in both Home pages. Replace any nested Git-path, `.md`, relative, or stale wiki-page target with the canonical public URL for the page that actually exists. Preserve issue links and intentional `—` cells for unavailable translations.
5. `Date` means the plan pair's latest content update, not its approval date or the Home edit date. For each row, use the later Git commit date of the English and Japanese plan pages, expressed as `yyyy-MM-dd` in Asia/Tokyo. If either page has an uncommitted content change, use today's Asia/Tokyo date. Update both Home rows together; for an index-only link repair, derive dates from plan history without advancing them to today.

Use [templates/home.md](templates/home.md) / [templates/home_ja.md](templates/home_ja.md) only as a starting skeleton for a wiki that has no `Home` page yet (Phase 0's uninitialized case) — an existing Home always wins over the template.

## Phase 4 — Validate, commit, and push

Run [scripts/validate_wiki.py](scripts/validate_wiki.py) against the prepared wiki checkout before publishing. It checks all Home wiki links against the wiki's page files, route collisions, category tables, and paired Home dates. Pass newly edited plan pages with `--page` to check their language links too. Resolve every reported error. Then review the file list and Home diff. Pushing publishes immediately; use existing user authorization if it covers publication, otherwise obtain approval.

```bash
python <path-to-this-skill>/scripts/validate_wiki.py <scratch-dir>/wiki <owner>/<repo> --page plan/<date>/<slug>.md --page plan/<date>/<slug>_ja.md
```

```bash
git -C <scratch-dir>/wiki add plan/<date>/<slug>.md plan/<date>/<slug>_ja.md Home.md Home_ja.md
git -C <scratch-dir>/wiki commit -m "add: plan <slug>"
git -C <scratch-dir>/wiki push origin HEAD
```

After pushing, verify the public pages. Local route validation cannot prove GitHub has published them:

1. Open `https://github.com/<owner>/<repo>/wiki/<slug>` and `https://github.com/<owner>/<repo>/wiki/<slug>_ja`; confirm neither is a 404.
2. Open `Home` and `Home_ja` and follow **every** plan and language-column link; confirm none returns 404. Repair existing broken rows as part of a Home update, not only the newly added row.
3. Follow the language-switch link on each changed plan page and confirm it lands on the other language.
4. Confirm the dates in both Home rows match the latest plan-page content update.

## Pitfalls

- An uninitialized wiki cannot be cloned or pushed to, no matter what — `hasWikiEnabled: true` only means the feature is turned on, not that content exists. There is no API-based way to create the first page.
- Wiki-internal links use the public URL with the file basename and omit both the Git directory and `.md` suffix. Reusing `plan/<date>/<slug>` as a public link produces a 404.
- The wiki's public page namespace and page list/sidebar are flat regardless of the Git repository's `plan/<date>/` subdirectories. Basenames must therefore be globally unique, and `Home.md` is the only real grouped navigation. Skipping the Home update leaves the new page effectively unreachable.
- The wiki is a separate git repository from the main one — no branch protection, no PR review; a push is instantly live.
- The `_ja` suffix is a naming convention this team uses, not a GitHub feature — cross-links between language pairs must be added by hand in both directions.

## Reference

- [templates/plan-page.md](templates/plan-page.md) — starter structure for a new plan page.
- [templates/home.md](templates/home.md), [templates/home_ja.md](templates/home_ja.md) — starter skeleton, English/Japanese, for a wiki with no existing Home page.
- [scripts/validate_wiki.py](scripts/validate_wiki.py) — local Home/page URL and Date preflight.
