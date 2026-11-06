# Testing the agent-performance plugin

Three things can break independently, so test them separately.

## 1. The script

```bash
python3 plugins/agent-performance/tests/test_cost_report.py
```

Covers the counting traps against small fixtures: repeated lines, resumed
sessions, subagents, what starts a turn, the Haiku 5.5 long-prompt rates, and
both telemetry formats. Run it with the system Python as well as a current one,
because the skill promises 3.9.

Then run the report on real data. Over the same dates, the two sources should
agree within a few percent:

```bash
S=plugins/agent-performance/skills/agent-cost/scripts/cost_report.py
python3 $S --since 2026-10-25 | head -1
python3 $S --source telemetry --since 2026-10-25 | head -1
```

## 2. Triggering

Start a fresh session for each prompt. Once a skill is active in a
conversation the test is worthless.

Should activate:

- What are my Claude Code sessions costing?
- Why am I burning through usage so fast?
- Which of my skills is the most expensive?
- How much would I save on Opus 5.5?

Should not activate:

- Make this script that calls the Claude API cheaper (claude-api)
- What does Opus 5.5 cost per million tokens? (claude-api)
- How do pull requests flow through this repo? (pmx-process-mining)

## 3. Behaviour

Run one activating prompt and check the answer:

- Says "API list-price equivalent", and does not call the figure a bill.
- Every figure quoted appears in the script's output.
- Suggests one or two changes tied to a finding, and no invented savings.
- Passes on any `SMALL SAMPLE` or `NOT PRICED` line.
