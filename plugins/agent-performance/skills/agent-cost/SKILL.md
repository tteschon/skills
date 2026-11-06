---
name: agent-cost
description: Report what Claude Code work costs at API list prices, broken down by model, project, skill, tool and token type, from session transcripts or OpenTelemetry logs, and name the changes most likely to reduce it. Use when someone asks what their agents cost, why usage is so high, which skill, tool or project is most expensive, or what switching model would save. Not for reducing spend in code that calls the Claude API - that is claude-api.
compatibility: Requires python3 (3.9 or later, standard library only) and Claude Code session transcripts under ~/.claude/projects. OpenTelemetry logs are optional.
allowed-tools: Bash(python3:*) Bash(ls:*) Read
---

# Agent cost

Produces a cost report for Claude Code work on this machine and the one or
two changes most likely to reduce it. Done means `scripts/cost_report.py`
(relative to this skill's directory) exits 0 and every figure you quote came
from its output.

The usual surprise is that output is a small part of the cost. Every model
call re-reads the whole conversation, so cost tracks how many calls a turn
makes multiplied by how much context each one carries.

## Before you start

Ask only if the request leaves it open and the answer changes the run: which
dates or which project. Otherwise report on everything. The script sees this
machine only, so if someone asks about a team, say that each person has to
run it and that the totals cover one machine.

## Step 1 - Choose the source

| Situation | Source | Why |
|---|---|---|
| Default, or any question about the past | `transcripts` | Goes back as far as transcripts are kept, with no setup |
| Telemetry exists and the dates fall inside it | `telemetry` | Claude Code's own `cost_usd`, and skills tagged directly rather than inferred |
| Checking that the numbers can be trusted | Both, same dates | They should agree within a few percent |

Check for telemetry with `ls ~/otel/claude/logs*.jsonl`. If it lives
elsewhere, pass `--telemetry-dir`. The local receiver's files and an
OpenTelemetry Collector file exporter's both load.

## Step 2 - Run it

```bash
python3 scripts/cost_report.py
python3 scripts/cost_report.py --source telemetry --since 2026-10-15
python3 scripts/cost_report.py --project my-repo --until 2026-10-31
python3 scripts/cost_report.py --what-if claude-opus-5-5
python3 scripts/cost_report.py --json cost.json
```

Dates are UTC and inclusive. `--project` matches any part of the label shown
under BY PROJECT. `--what-if` reprices the same tokens, so run it whenever one
older or larger model dominates BY MODEL.

## Step 3 - Verify

Do not report figures from a run that fails any line here.

| Output | Meaning | Do this |
|---|---|---|
| `RECONCILED` and exit 0 | Every table sums to the headline | Continue |
| `DOES NOT RECONCILE`, exit 1 | A table is wrong | Stop and tell the user. Do not quote the tables |
| `No model calls found`, exit 2 | Wrong directory or filters | Loosen the filters or fix the path |
| `NOT PRICED` on a Claude model | The total is understated | Add the model to `PRICES` from the claude-api skill, then rerun |
| `NOT PRICED` on a local model | It has no list price | Say so and continue |
| `PRICE CHECK` beyond about 1% | The `PRICES` table has gone stale, or heavy web search fees | Check the rates in the claude-api skill. Trust `cost_usd` |
| `SMALL SAMPLE` | Fewer than 30 turns | Describe these turns. Do not claim a trend |

## Step 4 - Find the lever

Start from the largest line of WHERE THE MONEY GOES, then look at
CONCENTRATION to see which turns carry it.

| The report shows | What it means | Change to suggest |
|---|---|---|
| Cache reads are the largest | Many calls, each re-reading a large context | `/clear` between unrelated tasks, `/compact` in long sessions, and subagents for reading-heavy work |
| 1-hour cache writes are high | Lots of new context, or a large session rewritten after sitting idle | Keep tool output short. Start a new session instead of returning to a large idle one |
| Output is the largest | Long answers or heavy thinking | Lower the effort level for routine work |
| A few turns hold most of the cost, with many more calls | Long autonomous runs | Split big tasks. Open the session behind the costliest project and see what the agent kept doing |
| Those turns also carry far more context per call | Context grew through the run | Compact sooner, or give the reading to a subagent |
| Bash or a browser tool leads BY TOOL | Frequent calls, and their output stays in context | Filter command output, and read pages as text rather than screenshots |
| An older model dominates BY MODEL | Possibly a default never revisited | Quote `--what-if`, and say quality has to hold on the new model |
| A skill has a high `$/turn` | It is used in expensive turns, which it may not have caused | Compare with `(no skill)`. Only then consider trimming what the skill loads |

Suggest one or two changes. Every extra one makes the before-and-after
comparison harder to read.

## Step 5 - Report

Tell the user, in this order:

1. The total, the dates, and the words "API list-price equivalent".
2. The two or three findings that matter, each with its figure.
3. One or two changes, tied to those findings.
4. Any caveat the script printed, such as `SMALL SAMPLE` or `NOT PRICED`.

Do not estimate savings from a change except with `--what-if`, which is the
only saving the data can support. Project names appear in the report, so
mention that before it is shared.

## Gotchas

- **This is not the bill.** On a Claude subscription, the figure is what the
  same work would cost through the API. Presenting it as money spent is the
  most common way to mislead someone with this report.
- **Never total usage with `grep` or `jq`.** One API response is written as
  up to one line per content block, each repeating the full usage, so summing
  lines overstates cost several times over without any error.

  ```bash
  # WRONG - counts every content block of every response
  cat ~/.claude/projects/*/*.jsonl | jq '.message.usage.output_tokens' | paste -sd+ | bc

  # CORRECT - counts each response once, and includes subagents
  python3 scripts/cost_report.py
  ```

- **Subagent transcripts are nested** under `<session>/subagents/`. A glob of
  `projects/*/*.jsonl` misses them. They count as their own turns in this
  report, so a subagent's cost does not inflate its parent turn.
- **BY TOOL measures the cost of deciding to use a tool**, not of reading its
  output on every later call. A tool's real cost is higher, and it is spread
  across the cache reads.
- **Telemetry has no working directory.** Its projects are git repository
  names, so work outside a repository shows as `(no repository)`, and the two
  sources label the same work differently. Compare projects within one source.
- **Telemetry attaches some tools by timing.** When a `tool_result` does not
  name its API response, it goes to the last response before the tool started.
  Treat that source's BY TOOL as approximate.
- **Transcripts miss background calls.** Prompt suggestions, session titles,
  summaries and compaction appear only in telemetry, so its total over the same
  dates runs a few percent higher. That gap is expected, and it means a
  transcript total is slightly low.
- **Compare periods on `$/turn` and shares, not totals.** Totals mostly follow
  how much work was done that week.
- **The logs hold more than this report reads.** Transcripts contain prompts,
  and telemetry can contain shell commands and account details. The script
  reads none of them. Do not paste raw lines into a chat or a document.
