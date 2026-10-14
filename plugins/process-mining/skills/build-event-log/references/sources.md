# Where each system keeps its history

Each section names the table or endpoint that records changes, the three
columns to map, and what that source gets wrong. Read only the section for
the source in hand. Use whatever access the session already has - a
connector, an authenticated CLI, or an export the user provides - and never
ask the user for credentials.

Every recipe ends at the same CSV: `case:concept:name`, `concept:name`,
`time:timestamp`, timestamps in ISO 8601 UTC. Write it with the `csv` module,
not string joins - activity names contain commas.

## Salesforce

| Process | Object | Case | Activity | Timestamp |
|---|---|---|---|---|
| Deal stages | `OpportunityHistory` | `OpportunityId` | `StageName` | `CreatedDate` |
| Case status | `CaseHistory`, `Field = 'Status'` | `CaseId` | `NewValue` | `CreatedDate` |
| Lead status | `LeadHistory`, `Field = 'Status'` | `LeadId` | `NewValue` | `CreatedDate` |
| Any tracked field | `OpportunityFieldHistory`, `<Object>__History` | `<Object>Id` / `ParentId` | `NewValue` | `CreatedDate` |

`OpportunityHistory` is always on. Every `*History` field table is empty
unless Field History Tracking was enabled for that field, and it records only
changes made after that. Count before extracting:

```sql
SELECT COUNT() FROM CaseHistory WHERE Field = 'Status'
```

Zero means tracking is off - say so and stop; the fix is in Setup (Object
Manager, Fields & Relationships, Set History Tracking), and it only helps
from now on.

- Field history tables carry a `Field = 'created'` row per record. Keep it as
  the case's first event (activity `Created`), or every case starts at its
  first status change and the opening step disappears.
- `CreatedDate` comes back as `2026-04-29T15:35:29.000+0000`; `check_log.py`
  reads that form, but write `+00:00` in the CSV for other tools.
- Retention is 18 months in the UI and 24 through the API unless the org
  bought Field Audit Trail. Cases opened before the window look like they
  skip their first steps; say so rather than reading it as a finding.
- Sandboxes and demo orgs often load every history row in one batch - every
  row shares one `CreatedDate`. That is the check script's first FAIL.

## Jira

- `GET /rest/api/3/search/jql?jql=<JQL>&fields=created` lists the issues
  (paginate with `nextPageToken`).
- `GET /rest/api/3/issue/{key}/changelog` returns the history, paginated with
  `startAt`, `maxResults` and `isLast`. For many issues,
  `POST /rest/api/3/changelog/bulkfetch` with `issueIdsOrKeys` and
  `fieldIds: ["status"]` is far fewer calls.

Each changelog entry has `created` and an `items` list; keep items where
`field == "status"`.

| Case | Activity | Timestamp |
|---|---|---|
| Issue key | `toString` (the status entered) | entry `created` |

Add the issue's own `created` as a first `Created` event - the changelog
holds changes, and creation is not one.

## Linear

GraphQL, one query per page of issues:

```graphql
{ issues(first: 50, filter: { team: { key: { eq: "ENG" } } }) {
    nodes { identifier createdAt
      history(first: 100) { nodes { createdAt toState { name } } } }
    pageInfo { hasNextPage endCursor } } }
```

| Case | Activity | Timestamp |
|---|---|---|
| `identifier` | `toState.name` | history `createdAt` |

History nodes record every kind of change; keep only nodes with a non-null
`toState`, and add the issue's `createdAt` as `Created`.

## GitHub pull requests

```bash
gh pr list -R OWNER/REPO --state all --limit 500 --json number,createdAt
gh api repos/OWNER/REPO/issues/NUMBER/timeline --paginate
```

The timeline is a mixed bag, and the timestamp field differs by event:

| Event | Activity | Timestamp field |
|---|---|---|
| (PR itself) | `Opened` | `createdAt` from `gh pr list` |
| `ready_for_review` | `Ready for review` | `created_at` |
| `review_requested` | `Review requested` | `created_at` |
| `reviewed` | `Review: <state>` (`approved`, `changes_requested`, `commented`) | `submitted_at` |
| `committed` | `Commit pushed` | `committer.date` |
| `merged` / `closed` / `reopened` | `Merged` / `Closed` / `Reopened` | `created_at` |

```python
# WRONG - reviewed and committed events have no created_at; they silently
# drop out, and every PR looks approved without review
when = event["created_at"]

# CORRECT
when = (event.get("created_at") or event.get("submitted_at")
        or (event.get("committer") or {}).get("date"))
```

Skip `labeled`, `mentioned`, `cross-referenced`, `head_ref_deleted` and the
like unless the question is about them - they are noise in a review process.
A merged PR also gets a `closed` event at the same instant; drop the `closed`
when a `merged` exists, or every merged PR ends in a tie.

## Claude Code sessions

Each session is a JSONL file under `~/.claude/projects/<project-dir>/`. One
JSON object per line, with `type`, `timestamp`, `sessionId` and
`isSidechain`.

| Line | Activity | Keep when |
|---|---|---|
| `type == "user"` with string `message.content` | `User prompt` | the prompt was typed (`origin.kind == "human"` where present) |
| `type == "assistant"`, each `tool_use` block in `message.content` | the block's `name` | always |

- Skip `isSidechain: true` lines; they are sub-agent runs with their own
  shape.
- MCP tools are named `mcp__<server>__<tool>`, and the server part is often a
  UUID. Collapse those to `MCP:<server>` or `MCP:connector`, or every
  connector call is its own activity.
- A whole session as the case gives near-unique paths (38 variants in 40
  sessions on one real machine). Use one prompt-to-reply turn as the case -
  `<sessionId>-<turn number>`, incremented at each `User prompt` - when the
  question is how the agent works rather than how long sessions run.

## Spreadsheets and CSV exports

Decide which of two shapes it is before writing anything:

| Shape | Looks like | Do |
|---|---|---|
| Long | one row per change - an id, a status, a date | Map the three columns; done |
| Wide | one row per item, one column per stage date (`Submitted`, `Approved`, ...) | Melt - one event per non-empty date cell, activity = column header |

```python
# WRONG - a blank cell becomes an event with an empty timestamp
for stage in stage_columns:
    rows.append((item_id, stage, record[stage]))

# CORRECT - a blank means the stage was never reached
for stage in stage_columns:
    if record[stage].strip():
        rows.append((item_id, stage, record[stage]))
```

A sheet with one status column and one "last updated" column is current
state, not history - it has one row per item and cannot be mined. Ask
whether the source system keeps a history or audit table, or whether past
copies of the sheet exist.
