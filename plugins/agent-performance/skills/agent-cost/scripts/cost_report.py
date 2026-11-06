#!/usr/bin/env python3
"""What do models, projects, skills and tools cost in Claude Code? Standard library only.

    python3 cost_report.py [--source transcripts|telemetry] [--since YYYY-MM-DD]
                           [--until YYYY-MM-DD] [--project TEXT] [--what-if MODEL]
                           [--top N] [--json FILE]

Sources:
  transcripts  ~/.claude/projects/**/*.jsonl - token usage per model call, priced
               with PRICES below. Includes subagent transcripts.
  telemetry    ~/otel/claude/logs*.jsonl - claude_code.api_request events, which
               carry Claude Code's own cost_usd and skill.name.

Costs are API list-price equivalents. On a Claude subscription this is what the
work would cost through the API, not the bill.

Attribution, stated once because every number depends on it:
  project  transcripts - the working directory; telemetry - the git repository
  skill    a call belongs to a skill if that skill was invoked earlier in the same
           turn; telemetry tags it directly with skill.name
  tool     a call's cost is split evenly across the tools it requested - the cost
           of deciding to use the tool, not of re-reading its output later

Only token counts, model names, tool names, skill names and project names are
read into the report. Prompts, responses, commands and account fields are not.

Exit codes: 0 report produced, 1 totals did not reconcile, 2 no data or bad input.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# $ per million tokens: input, output, 5-minute cache write, 1-hour cache write,
# cache read. From the claude-api skill (cached 2026-10-06). Fast mode is 2x.
PRICES = {
    "claude-fable-5-1": (10.0, 50.0, 12.50, 20.0, 0.25),
    "claude-mythos-5-1": (10.0, 50.0, 12.50, 20.0, 0.25),
    "claude-fable-5": (10.0, 50.0, 12.50, 20.0, 1.00),
    "claude-opus-5-5": (4.0, 20.0, 5.00, 8.0, 0.20),
    "claude-opus-5": (5.0, 25.0, 6.25, 10.0, 0.50),
    "claude-opus-4-8": (5.0, 25.0, 6.25, 10.0, 0.50),
    "claude-opus-4-7": (5.0, 25.0, 6.25, 10.0, 0.50),
    "claude-opus-4-6": (5.0, 25.0, 6.25, 10.0, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0, 2.50, 4.0, 0.20),
    "claude-sonnet-5": (2.0, 10.0, 2.50, 4.0, 0.20),
    "claude-sonnet-4-6": (3.0, 15.0, 3.75, 6.0, 0.30),
    "claude-haiku-5-5": (0.10, 0.50, 0.125, 0.20, 0.01),
    "claude-haiku-4-5": (1.0, 5.0, 1.25, 2.0, 0.10),
}
# Rate card used once the whole prompt, cached or not, passes the threshold.
LONG_PROMPT = {"claude-haiku-5-5": (100_000, (0.50, 2.50, 0.625, 1.00, 0.05))}
WEB_SEARCH_FEE = 0.01  # per search; appears in cost_usd but not in token counts
BUILTIN_COMMANDS = {"model", "compact", "clear", "reload-skills", "list-agents", "auto-mode-setup",
                    "config", "help", "cost", "context", "resume", "init", "memory", "agents"}
UUID = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
NOT_A_PROMPT = ("<local-command-stdout", "<local-command-stderr", "<local-command-caveat")


def normalize_model(model: str | None) -> str:
    return re.sub(r"-\d{8}$", "", model or "")


def prompt_tokens(u: dict) -> int:
    return ((u.get("input_tokens", 0) or 0) + (u.get("cache_read_input_tokens", 0) or 0)
            + (u.get("cache_creation_input_tokens", 0) or 0))


def rates_for(model: str | None, u: dict) -> tuple | None:
    name = normalize_model(model)
    long_prompt = LONG_PROMPT.get(name)
    if long_prompt and prompt_tokens(u) > long_prompt[0]:
        return long_prompt[1]
    return PRICES.get(name)


def write_split(u: dict) -> tuple[int, int]:
    """(5-minute, 1-hour) cache write tokens. Records with no split are all 5-minute."""
    cc = u.get("cache_creation") or {}
    w1h = cc.get("ephemeral_1h_input_tokens", 0) or 0
    w5m = cc.get("ephemeral_5m_input_tokens")
    if w5m is None:
        w5m = (u.get("cache_creation_input_tokens", 0) or 0) - w1h
    return w5m, w1h


def breakdown(model: str | None, u: dict, speed: str | None) -> dict[str, float] | None:
    """Dollars by token type, or None when the model has no known price."""
    p = rates_for(model, u)
    if p is None:
        return None
    f = 2 if speed == "fast" else 1
    w5m, w1h = write_split(u)
    parts = {
        "fresh input": (u.get("input_tokens", 0) or 0) * p[0] * f / 1e6,
        "output (incl. thinking)": (u.get("output_tokens", 0) or 0) * p[1] * f / 1e6,
        "cache writes, 5 minute": w5m * p[2] * f / 1e6,
        "cache writes, 1 hour": w1h * p[3] * f / 1e6,
        "cache reads": (u.get("cache_read_input_tokens", 0) or 0) * p[4] * f / 1e6,
    }
    searches = (u.get("server_tool_use") or {}).get("web_search_requests", 0) or 0
    if searches:
        parts["web search fees"] = searches * WEB_SEARCH_FEE
    return parts


def cost_of(model: str | None, u: dict, speed: str | None) -> float | None:
    parts = breakdown(model, u, speed)
    return None if parts is None else sum(parts.values())


def mcp_label(server: str) -> str:
    return "MCP:" + ("connector" if UUID.match(server) else re.sub(r"^Claude[_ ]", "", server))


def tool_label(name: str) -> str:
    return mcp_label(name.split("__")[1]) if name.startswith("mcp__") else name


def telemetry_tool_label(a: dict) -> str:
    """Telemetry names every MCP call mcp_tool; the server is in tool_parameters."""
    name = a.get("tool_name", "?")
    if name != "mcp_tool":
        return tool_label(name)
    try:
        server = json.loads(a.get("tool_parameters") or "{}").get("mcp_server_name")
    except (json.JSONDecodeError, AttributeError):
        server = None
    return mcp_label(server) if server else "MCP:(unknown)"


def project_label(cwd: str) -> str:
    if not cwd:
        return "(unknown)"
    if "/scratchpad" in cwd or "/private/tmp" in cwd or "Application Support" in cwd:
        return "(scratch / app workspaces)"
    parts = Path(cwd).parts
    return "/".join(parts[-2:]) if len(parts) > 3 else cwd


def starts_turn(e: dict, content) -> bool:
    """True for a person's prompt: not tool results, notifications, or injected text."""
    if e.get("isMeta") or e.get("isCompactSummary"):
        return False
    if (e.get("origin") or {}).get("kind", "human") != "human":
        return False
    if isinstance(content, str):
        return not content.lstrip().startswith(NOT_A_PROMPT)
    if isinstance(content, list):
        types = {b.get("type") for b in content if isinstance(b, dict)}
        return "tool_result" not in types and bool(types & {"text", "image"})
    return False


def prompt_text(content) -> str:
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")


# ---- loaders: both yield the same call records ------------------------------------------
def from_transcripts(root: Path) -> list[dict]:
    responses: dict[tuple, dict] = {}
    for f in sorted(root.glob("**/*.jsonl")):
        subagent = "subagents" in f.parts
        turn, skill, cwd = (f"agent:{f.stem}" if subagent else 0), None, ""
        with open(f, errors="ignore") as handle:
            for line in handle:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cwd = e.get("cwd") or cwd
                m = e.get("message") or {}
                content = m.get("content")
                if e.get("type") == "user":
                    if not subagent and not e.get("isSidechain") and starts_turn(e, content):
                        turn += 1
                        cmd = re.search(r"<command-name>/?([^<\s]+)</command-name>", prompt_text(content))
                        skill = cmd.group(1) if cmd and cmd.group(1) not in BUILTIN_COMMANDS else None
                    continue
                if e.get("type") != "assistant" or not m.get("usage") or m.get("model") == "<synthetic>":
                    continue
                # One API response is written as one line per content block, each
                # repeating the full usage: key by response, never by line. The key
                # is global because a resumed session can copy lines into a new file.
                key = (m.get("id"), e.get("requestId"))
                rec = responses.get(key)
                if rec is None:
                    rec = responses[key] = {
                        "session": e.get("sessionId"), "project": project_label(cwd),
                        "turn": f'{e.get("sessionId")}:{turn}', "model": normalize_model(m.get("model")),
                        "speed": m["usage"].get("speed"), "usage": m["usage"], "tools": [],
                        "skill": skill, "ts": e.get("timestamp") or "",
                        "subagent": subagent or bool(e.get("isSidechain")),
                    }
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_use":
                            rec["tools"].append(tool_label(b.get("name", "?")))
                            if b.get("name") == "Skill":
                                skill = (b.get("input") or {}).get("skill") or skill
    calls = list(responses.values())
    for rec in calls:
        rec["cost"] = cost_of(rec["model"], rec["usage"], rec["speed"])
    return calls


def read_log_rows(root: Path) -> list[dict]:
    rows = []
    for f in sorted(root.glob("logs*.jsonl")):
        with open(f, errors="ignore") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue  # a batch still being written
                # The local receiver wraps each batch in {"received", "payload"};
                # an OpenTelemetry Collector file exporter writes the batch itself.
                for rl in record.get("payload", record).get("resourceLogs", []):
                    for sl in rl.get("scopeLogs", []):
                        for r in sl.get("logRecords", []):
                            rows.append({x["key"]: next(iter(x["value"].values()), None) for x in r.get("attributes", [])})
    return rows


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def telemetry_usage(a: dict) -> dict:
    usage = {"input_tokens": int(a.get("input_tokens") or 0), "output_tokens": int(a.get("output_tokens") or 0),
             "cache_read_input_tokens": int(a.get("cache_read_tokens") or 0),
             "cache_creation_input_tokens": int(a.get("cache_creation_tokens") or 0)}
    writes = usage["cache_creation_input_tokens"]
    if a.get("cache_creation_1h_tokens") is not None or a.get("cache_creation_5m_tokens") is not None:
        usage["cache_creation"] = {"ephemeral_1h_input_tokens": int(a.get("cache_creation_1h_tokens") or 0),
                                   "ephemeral_5m_input_tokens": int(a.get("cache_creation_5m_tokens") or 0)}
    elif writes and rates_for(a.get("model"), usage):
        # Older Claude Code versions report cache writes as one total, but 1-hour
        # writes cost 1.6x a 5-minute write. cost_usd pins the split: one unknown,
        # one equation.
        lo = cost_of(a.get("model"), {**usage, "cache_creation": {"ephemeral_5m_input_tokens": writes, "ephemeral_1h_input_tokens": 0}}, a.get("speed"))
        hi = cost_of(a.get("model"), {**usage, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": writes}}, a.get("speed"))
        share = min(1.0, max(0.0, (float(a.get("cost_usd") or 0) - lo) / (hi - lo))) if hi > lo else 0.0
        w1h = round(writes * share)
        usage["cache_creation"] = {"ephemeral_1h_input_tokens": w1h, "ephemeral_5m_input_tokens": writes - w1h}
    return usage


def from_telemetry(root: Path) -> list[dict]:
    rows = read_log_rows(root)
    repo_by_session = {}
    for a in rows:
        if a.get("vcs.repository.name"):
            repo_by_session.setdefault(a.get("session.id"), a["vcs.repository.name"])
    calls: dict[tuple, dict] = {}
    for a in rows:
        if a.get("event.name") != "api_request":
            continue
        request = a.get("request_id") or a.get("client_request_id") or a.get("event.sequence")
        usage = telemetry_usage(a)
        calls[(a.get("session.id"), request)] = {
            "session": a.get("session.id"), "request": a.get("request_id"),
            "project": repo_by_session.get(a.get("session.id"), "(no repository)"),
            "turn": f'{a.get("session.id")}:{a.get("prompt.id")}', "model": normalize_model(a.get("model")),
            "speed": a.get("speed"), "usage": usage, "tools": [], "prompt": a.get("prompt.id"),
            "skill": a.get("skill.name") if a.get("skill.name") not in (None, "", "custom", "third-party") else None,
            "ts": a.get("event.timestamp") or "", "cost": float(a.get("cost_usd") or 0),
            "cost_check": cost_of(a.get("model"), usage, a.get("speed")),
            "subagent": bool(a.get("agent_id")), "_at": parse_ts(a.get("event.timestamp")),
        }
    # A tool_result does not always name the API response that requested it. Fall
    # back to the turn's last response before the tool started running.
    by_request = {c["request"]: c for c in calls.values() if c["request"]}
    by_turn = defaultdict(list)
    for c in calls.values():
        by_turn[c["turn"]].append(c)
    for cs in by_turn.values():
        cs.sort(key=lambda c: c["ts"])
    for a in rows:
        if a.get("event.name") != "tool_result":
            continue
        owner = by_request.get(a.get("request_id"))
        if owner is None:
            cs = by_turn.get(f'{a.get("session.id")}:{a.get("prompt.id")}', [])
            at = parse_ts(a.get("event.timestamp"))
            if at is not None:
                started = at - timedelta(milliseconds=float(a.get("duration_ms") or 0))
                before = [c for c in cs if c["_at"] is not None and c["_at"] <= started]
                owner = before[-1] if before else None
            owner = owner or (cs[-1] if cs else None)
        if owner is not None:
            owner["tools"].append(telemetry_tool_label(a))
    for c in calls.values():
        del c["_at"]
    return list(calls.values())


# ---- the report ----------------------------------------------------------------------------
def table(title: str, groups: dict[str, list[dict]], total: float, n: int, unit: str = "calls") -> list[dict]:
    rows = []
    for k, cs in groups.items():
        cost = sum(c.get("_share", c["cost"]) for c in cs)
        rows.append({"key": k, "cost": cost, unit: len(cs), "turns": len({c["turn"] for c in cs})})
    rows.sort(key=lambda r: -r["cost"])
    print(f"\n{title}")
    print(f"  {'':34s} {'cost':>9s} {'share':>6s} {unit:>6s} {'turns':>6s} {'$/turn':>8s}")
    for r in rows[:n]:
        print(f"  {str(r['key'])[:34]:34s} {r['cost']:9.2f} {r['cost'] / total:6.1%} {r[unit]:6d} {r['turns']:6d} {r['cost'] / max(r['turns'], 1):8.2f}")
    if len(rows) > n:
        rest = sum(r["cost"] for r in rows[n:])
        print(f"  {f'... {len(rows) - n} more':34s} {rest:9.2f} {rest / total:6.1%}")
    return rows


def group(calls: list[dict], key) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    for c in calls:
        groups[key(c)].append(c)
    return groups


def concentration(calls: list[dict]) -> dict:
    """How much of the cost sits in the costliest tenth of turns, and what they look like."""
    turns = group(calls, lambda c: c["turn"])
    ranked = sorted(turns.values(), key=lambda cs: -sum(c["cost"] for c in cs))
    n_top = max(1, math.ceil(len(ranked) / 10))
    top, rest = ranked[:n_top], ranked[n_top:]
    context = lambda ts: statistics.mean(prompt_tokens(c["usage"]) for cs in ts for c in cs) if ts else 0
    size = lambda ts: statistics.median(len(cs) for cs in ts) if ts else 0
    return {"turns": len(ranked), "top_turns": n_top,
            "top_share": sum(c["cost"] for cs in top for c in cs) / (sum(c["cost"] for c in calls) or 1e-9),
            "top_median_calls": size(top), "rest_median_calls": size(rest),
            "top_mean_context": context(top), "rest_mean_context": context(rest)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Claude Code cost by model, project, skill and tool, at API list prices.")
    ap.add_argument("--source", choices=["transcripts", "telemetry"], default="transcripts")
    ap.add_argument("--since", help="first UTC date to include, YYYY-MM-DD")
    ap.add_argument("--until", help="last UTC date to include, YYYY-MM-DD")
    ap.add_argument("--project", help="only projects whose label contains this text")
    ap.add_argument("--what-if", dest="what_if", metavar="MODEL", help="reprice every call at this model's rates")
    ap.add_argument("--top", type=int, default=10, help="rows per table (default 10)")
    ap.add_argument("--json", metavar="FILE", help="also write the tables as JSON")
    ap.add_argument("--transcripts-dir", default="~/.claude/projects")
    ap.add_argument("--telemetry-dir", default="~/otel/claude")
    args = ap.parse_args()

    for label, value in (("--since", args.since), ("--until", args.until)):
        if value and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            print(f"{label} must look like 2026-10-15, got {value!r}", file=sys.stderr)
            return 2
    if args.what_if and args.what_if not in PRICES:
        print(f"--what-if: no price for {args.what_if!r}. Known models: {', '.join(sorted(PRICES))}", file=sys.stderr)
        return 2

    if args.source == "transcripts":
        calls = from_transcripts(Path(os.path.expanduser(args.transcripts_dir)))
    else:
        calls = from_telemetry(Path(os.path.expanduser(args.telemetry_dir)))
    calls = [c for c in calls if (not args.since or c["ts"][:10] >= args.since)
             and (not args.until or c["ts"][:10] <= args.until)
             and (not args.project or args.project.lower() in c["project"].lower())]
    priced = [c for c in calls if c["cost"] is not None]
    unpriced = [c for c in calls if c["cost"] is None]
    if not priced:
        where = args.transcripts_dir if args.source == "transcripts" else args.telemetry_dir
        print(f"No model calls found in {where} for these filters.", file=sys.stderr)
        return 2
    total = sum(c["cost"] for c in priced) or 1e-9

    turns = defaultdict(float)
    for c in priced:
        turns[c["turn"]] += c["cost"]
    tok = lambda k: sum(c["usage"].get(k, 0) or 0 for c in priced)
    cache_read, fresh = tok("cache_read_input_tokens"), tok("input_tokens") + tok("cache_creation_input_tokens")
    days = sorted(c["ts"][:10] for c in priced if c["ts"])

    print(f"SOURCE: {args.source}  |  {days[0] if days else '?'} to {days[-1] if days else '?'}  |  {len(priced)} model calls, "
          f"{len(turns)} turns, {len({c['session'] for c in priced})} sessions  |  ${total:,.2f} at API list prices")
    print(f"  per turn: median ${statistics.median(turns.values()):.2f}, p90 ${sorted(turns.values())[int(0.9 * (len(turns) - 1))]:.2f}, "
          f"max ${max(turns.values()):.2f}  |  input served from cache: {cache_read / max(cache_read + fresh, 1):.0%}")
    if unpriced:
        names = sorted({str(c["model"]) for c in unpriced})
        print(f"  NOT PRICED, so missing from every total: {len(unpriced)} calls on {names}. "
              "Add Claude models to PRICES; local models have no list price.")
    if len(turns) < 30:
        print(f"  SMALL SAMPLE: {len(turns)} turns. Treat shares as a description of these turns, not a trend.")
    out = {"source": args.source, "first_day": days[0] if days else None, "last_day": days[-1] if days else None,
           "total": total, "calls": len(priced), "turns": len(turns), "unpriced_calls": len(unpriced)}

    # What kind of token the money goes to - the lever differs for each.
    parts = defaultdict(float)
    for c in priced:
        for k, v in (breakdown(c["model"], c["usage"], c["speed"]) or {}).items():
            parts[k] += v
    gap = total - sum(parts.values())
    if abs(gap) >= 0.005:
        parts["not in token counts (fees, unpriced)"] += gap
    print("\nWHERE THE MONEY GOES (by token type)")
    for k, v in sorted(parts.items(), key=lambda kv: -kv[1]):
        print(f"  {k:34s} {v:9.2f} {v / total:6.1%}")
    out["token_type"] = dict(parts)

    conc = concentration(priced)
    print(f"\nCONCENTRATION: the costliest {conc['top_turns']} of {conc['turns']} turns are {conc['top_share']:.0%} of cost")
    print(f"  median model calls per turn: {conc['top_median_calls']:.0f} in those turns, {conc['rest_median_calls']:.0f} in the rest")
    print(f"  mean context per call:       {conc['top_mean_context'] / 1000:.0f}K tokens in those turns, {conc['rest_mean_context'] / 1000:.0f}K in the rest")
    out["concentration"] = conc

    by_subagent = sum(c["cost"] for c in priced if c.get("subagent"))
    print(f"\nSUBAGENTS: ${by_subagent:,.2f} ({by_subagent / total:.1%}) of the total ran inside subagents")
    out["subagent_cost"] = by_subagent

    out["model"] = table("BY MODEL", group(priced, lambda c: c["model"] or "?"), total, args.top)
    out["project"] = table("BY PROJECT", group(priced, lambda c: c["project"]), total, args.top)
    out["skill"] = table("BY SKILL (calls after the skill was invoked, same turn)", group(priced, lambda c: c["skill"] or "(no skill)"), total, args.top)
    tool_groups = defaultdict(list)
    for c in priced:
        names = c["tools"] or ["(no tool - answer or thinking)"]
        for t in names:
            tool_groups[t].append({**c, "_share": c["cost"] / len(names)})
    out["tool"] = table("BY TOOL (call cost split across the tools it requested)", tool_groups, total, args.top, unit="uses")

    if args.what_if:
        repriced = sum(cost_of(args.what_if, c["usage"], c["speed"]) for c in priced)
        print(f"\nWHAT IF every call ran on {args.what_if}: ${repriced:,.2f} ({(repriced - total) / total:+.0%}), "
              "assuming the same tokens and the same work")
        out["what_if"] = {"model": args.what_if, "total": repriced}

    if args.source == "telemetry":
        checks = [(c["cost"], c["cost_check"]) for c in priced if c.get("cost_check") is not None]
        if checks:
            a, b = sum(x for x, _ in checks), sum(y for _, y in checks)
            print(f"\nPRICE CHECK: Claude Code's cost_usd ${a:.4f} vs this script's table ${b:.4f} over {len(checks)} calls ({(b - a) / a:+.1%})")
            out["price_check"] = {"cost_usd": a, "table": b}

    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1))

    # Every view must add back up to the headline, or a table is silently wrong.
    bad = [name for name in ("model", "project", "skill", "tool")
           if abs(sum(r["cost"] for r in out[name]) - total) > 0.01]
    if bad:
        print(f"\nDOES NOT RECONCILE: {', '.join(bad)} do not sum to ${total:,.2f}", file=sys.stderr)
        return 1
    print(f"\nRECONCILED: model, project, skill and tool tables each sum to ${total:,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
