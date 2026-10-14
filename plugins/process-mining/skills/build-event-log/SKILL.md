---
name: build-event-log
description: Turn data a user already has into an event log for process mining - a CSV of case, activity and timestamp rows that pmx reads with no flags - from Salesforce history, Jira or Linear changelogs, GitHub pull requests, Claude Code sessions, or a spreadsheet of status dates, then check it can be mined. Use when someone wants to see how their deals, tickets, orders or PRs actually flow but has no event log yet. Not for mining an existing log - that is pmx-process-mining.
compatibility: Requires python3 for the readiness check, and access to the source system - a connector, an authenticated CLI such as gh, or an export from the user.
allowed-tools: Bash(python3:*) Bash(gh:*) Read Write Glob
---

# Build an event log

Produces one CSV - one row per thing that happened, with the case it
happened to, what happened, and when - and proves it can be mined. Done
means `scripts/check_log.py` exits 0 on it and `pmx inspect` reads it with
no flags.

An event log is the input every process-mining tool needs, and almost nobody
has one: they have a CRM, a ticket tracker, or a spreadsheet. Building it is
most of the work, and every mistake here becomes a confident, wrong diagram
later.

## Before you start

Ask only what the conversation has not already answered, in one batch:

1. **Which process, in their words** - "how deals move", "how support tickets
   get resolved". This decides the case.
2. **Which system holds it** - Salesforce, Jira, Linear, GitHub, a
   spreadsheet. This decides the section of `references/sources.md` to read.

Do not ask about columns or file formats. If the user is new to process
mining, say in one sentence what the log will contain - "one row per status
change: which ticket, which status, and when" - so later questions make
sense to them.

## Step 1 - Choose the case

The case is the thing that moves through the process - not the person doing
the work, and not the record that happens to hold the data.

| Question | Case | Activity |
|---|---|---|
| How do deals progress? | Opportunity | Stage entered |
| How do support tickets get resolved? | Ticket / Case | Status entered |
| How does code get reviewed and merged? | Pull request | Opened, review, merged |
| How does an agent work through a request? | Session turn | Prompt or tool used |
| How do applications get approved? | Application | Stage reached |

Two ways to get it wrong, both silent:

- **Too fine** - one row per case, e.g. using the history row's own id. Every
  case has one event and there is no path. `check_log.py` FAILs it.
- **Too coarse** - an account spanning many deals, or an order spawning many
  shipments. No single case id is honest there; the log is object-centric.
  Say so and use `pmx ocel` (see `pmx-process-mining`) instead of forcing a
  case.

## Step 2 - Find the history, not the current state

Most tables hold where each record is *now*. Mining needs where it *was*,
and when it changed - a history, changelog, audit, or timeline source.

| System | History lives in | Read |
|---|---|---|
| Salesforce | `OpportunityHistory`, `<Object>History` field tables | `references/sources.md` - Salesforce |
| Jira | Issue changelog | `references/sources.md` - Jira |
| Linear | Issue history | `references/sources.md` - Linear |
| GitHub | Pull request timeline | `references/sources.md` - GitHub |
| Claude Code | Session JSONL transcripts | `references/sources.md` - Claude Code |
| Spreadsheet | Rows of changes, or one date column per stage | `references/sources.md` - Spreadsheets |
| Anything else | An audit, history, events or log table | Ask the user, or list tables with "history" or "audit" in the name |

Read the matching section before extracting - it names the exact table or
endpoint, the field to use as the activity, and that source's traps. Before
pulling everything, count events per case on a few records: a median of 1
means it is current state, and no amount of cleaning fixes that.

## Step 3 - Write the CSV

```csv
case:concept:name,concept:name,time:timestamp
SUP-1042,Created,2026-03-02T14:05:11+00:00
SUP-1042,In Progress,2026-03-02T16:40:02+00:00
SUP-1042,Done,2026-03-04T09:12:45+00:00
```

- **Use exactly these three column names.** They are the XES names, so pmx
  and pm4py read the file with no mapping flags. Extra columns (owner,
  amount) are allowed after them.
- **Activity is the step entered, short and stable** - the status or stage
  value, not "Status changed", not a sentence, never with ids or names in it.
  One distinct activity per real step.
- **Add a `Created` event** where the source records changes only - Jira,
  Linear, Salesforce field history. Otherwise every case starts at its first
  change and the opening step vanishes. Skip it where the source already
  records the starting state (`OpportunityHistory`), or every case opens
  with two events at one instant.
- **Timestamps in ISO 8601 with an offset, converted to UTC.** Keep the
  source's precision; never pad a bare date with a made-up time - a date-only
  log stays date-only and the check reports it.
- **Drop exact duplicate rows, and sort by case, then time.**
- Write it where the user will work with it (`./events.csv` unless they say
  otherwise), with Python's `csv` module - activity names contain commas.

## Step 4 - Check it can be mined

```bash
python3 <this skill's directory>/scripts/check_log.py events.csv
```

Pass `--case`, `--activity`, `--timestamp` only for a file that does not use
the three names above. It prints one summary line, then a PASS, or a WARN or
FAIL per problem with the number that decided it:

| Result | Meaning | Do |
|---|---|---|
| FAIL one shared timestamp | Rows were stamped at load time, not when things happened | Find a real event time; if none exists, stop - the data cannot be mined |
| FAIL duplicates (half the rows or more) | Every row exported twice | Deduplicate, re-run |
| FAIL single-event cases | Current state, or the case is too fine | Back to Step 1 or 2 |
| FAIL timestamps do not parse | Locale dates, free text | Convert to ISO 8601, re-run |
| WARN date only / ties | Same-day steps have no order | Proceed; tell the user the model guesses those orders |
| WARN mixed offsets | Sources disagree on time zones | Convert to UTC, re-run |
| WARN many activities | Ids or free text in the activity | Fix the activity value, re-run |

Exit 1 means at least one FAIL. Do not hand a FAILing log to pmx, and do not
report success with a FAIL in the transcript.

## Step 5 - Hand off to mining

```bash
pmx inspect events.csv
```

No flags. If that reads cleanly, continue with the `pmx-process-mining`
skill for the actual question.

## Step 6 - Report

Tell the user, in plain words:

- What one case is, and what one activity is, in their data.
- How many cases and events, over what time span.
- Every WARN, as what it means for the answer, not as a check name.
- What the log cannot show - history that starts when tracking was turned on,
  a retention window, activities the source never records.

## Gotchas

- **A history table can be empty without being broken.** Salesforce field
  history, and audit tables generally, record only after tracking was turned
  on. Count rows before building anything; zero is an answer to report, not a
  query to fix.
- **Demo and sandbox data is usually loaded in one batch.** Every row carries
  the same timestamp, the log parses fine, and pmx draws a model from nothing.
  This is why the check runs before mining, every time.
- **Two timestamp fields can mean different things.** A record's
  `LastModifiedDate` is not when it entered its current status. Use the
  timestamp on the history row itself.
- **Truncated history looks like a process finding.** Cases that began before
  the retention window or tracking start appear to skip their first steps.
  Name the window in the report so nobody reads it as behaviour.
