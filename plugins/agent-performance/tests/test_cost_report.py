"""Checks the counting traps in agent-cost's cost_report.py against small fixtures.

    python3 plugins/agent-performance/tests/test_cost_report.py

Every expected dollar figure is worked out by hand from the published rates.
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "skills/agent-cost/scripts/cost_report.py"
spec = importlib.util.spec_from_file_location("cost_report", SCRIPT)
cr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)


def prompt(text, **extra):
    return {"type": "user", "message": {"content": text}, "origin": {"kind": "human"},
            "sessionId": "s", "cwd": "/Users/x/code/app", **extra}


def response(rid, model="claude-opus-5-5", tools=(), ts="2026-11-01T00:00:00.000Z", **usage):
    usage = {"input_tokens": 0, "output_tokens": 0, **usage}
    content = [{"type": "tool_use", "name": t, "input": {}} for t in tools]
    return {"type": "assistant", "requestId": f"req-{rid}", "sessionId": "s", "timestamp": ts,
            "cwd": "/Users/x/code/app", "message": {"id": f"msg-{rid}", "model": model, "usage": usage, "content": content}}


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records))


class Pricing(unittest.TestCase):
    def test_token_types_use_their_own_rates(self):
        u = {"input_tokens": 1_000_000, "output_tokens": 1_000_000, "cache_read_input_tokens": 1_000_000,
             "cache_creation_input_tokens": 2_000_000,
             "cache_creation": {"ephemeral_5m_input_tokens": 1_000_000, "ephemeral_1h_input_tokens": 1_000_000}}
        # 4 input + 20 output + 5 five-minute + 8 one-hour + 0.20 read
        self.assertAlmostEqual(cr.cost_of("claude-opus-5-5", u, None), 37.20)

    def test_fast_mode_doubles(self):
        u = {"output_tokens": 1_000_000}
        self.assertAlmostEqual(cr.cost_of("claude-opus-5-5", u, "fast"), 40.0)

    def test_date_suffix_is_ignored(self):
        self.assertAlmostEqual(cr.cost_of("claude-haiku-4-5-20251001", {"input_tokens": 1_000_000}, None), 1.0)

    def test_unknown_model_is_unpriced_not_free(self):
        self.assertIsNone(cr.cost_of("local-model", {"input_tokens": 5}, None))

    def test_haiku_5_5_long_prompt_uses_the_higher_card_for_every_token(self):
        # 150K prompt: the cached part counts toward the threshold.
        u = {"input_tokens": 50_000, "cache_read_input_tokens": 100_000, "output_tokens": 1_000}
        # 50K * 0.50 + 100K * 0.05 + 1K * 2.50, per million
        self.assertAlmostEqual(cr.cost_of("claude-haiku-5-5", u, None), 0.0325)

    def test_haiku_5_5_short_prompt(self):
        # Matches a real cost_usd: 71215 input, 737 output = 0.00749.
        u = {"input_tokens": 71_215, "output_tokens": 737}
        self.assertAlmostEqual(cr.cost_of("claude-haiku-5-5", u, None), 0.00749)

    def test_web_search_fee(self):
        u = {"server_tool_use": {"web_search_requests": 2}}
        self.assertAlmostEqual(cr.cost_of("claude-opus-5-5", u, None), 0.02)


class Transcripts(unittest.TestCase):
    def load(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, records in files.items():
                write_jsonl(root / name, records)
            return cr.from_transcripts(root)

    def test_one_response_on_many_lines_counts_once(self):
        line = response(1, output_tokens=1_000_000)
        calls = self.load({"p/s.jsonl": [prompt("go"), line, line, line]})
        self.assertEqual(len(calls), 1)
        self.assertAlmostEqual(calls[0]["cost"], 20.0)

    def test_resumed_session_copying_lines_counts_once(self):
        line = response(1, output_tokens=1_000_000)
        calls = self.load({"p/a.jsonl": [prompt("go"), line], "p/b.jsonl": [prompt("go"), line]})
        self.assertEqual(len(calls), 1)

    def test_subagent_transcripts_are_included_as_their_own_turn(self):
        calls = self.load({"p/s.jsonl": [prompt("go"), response(1, output_tokens=10)],
                           "p/s/subagents/agent-1.jsonl": [prompt("task"), response(2, output_tokens=10)]})
        self.assertEqual(len(calls), 2)
        by_id = {c["subagent"]: c for c in calls}
        self.assertNotEqual(by_id[True]["turn"], by_id[False]["turn"])

    def test_prompt_with_an_image_starts_a_turn(self):
        image = prompt([{"type": "image"}, {"type": "text", "text": "look"}])
        calls = self.load({"p/s.jsonl": [prompt("one"), response(1), image, response(2)]})
        self.assertEqual(len({c["turn"] for c in calls}), 2)

    def test_tool_results_and_injected_text_do_not_start_a_turn(self):
        result = prompt([{"type": "tool_result", "content": "ok"}])
        meta = prompt("reminder", isMeta=True)
        stdout = prompt("<local-command-stdout>hi</local-command-stdout>")
        note = {**prompt("done"), "origin": {"kind": "task-notification"}}
        calls = self.load({"p/s.jsonl": [prompt("one"), response(1), result, response(2), meta, response(3),
                                         stdout, response(4), note, response(5)]})
        self.assertEqual(len({c["turn"] for c in calls}), 1)

    def test_skill_applies_for_the_rest_of_its_turn_only(self):
        skill_call = response(1, tools=["Skill"])
        skill_call["message"]["content"][0]["input"] = {"skill": "demo"}
        calls = self.load({"p/s.jsonl": [prompt("one"), skill_call, response(2), prompt("two"), response(3)]})
        skills = {c["message_id"]: c["skill"] for c in [{**c, "message_id": i} for i, c in enumerate(calls)]}
        self.assertEqual(skills, {0: None, 1: "demo", 2: None})

    def test_synthetic_messages_are_ignored(self):
        calls = self.load({"p/s.jsonl": [prompt("one"), response(1, model="<synthetic>")]})
        self.assertEqual(calls, [])


def log_batch(*attribute_sets):
    def value(v):
        return {"intValue": str(v)} if isinstance(v, int) else {"stringValue": str(v)}
    records = [{"attributes": [{"key": k, "value": value(v)} for k, v in attrs.items()]} for attrs in attribute_sets]
    return {"resourceLogs": [{"scopeLogs": [{"logRecords": records}]}]}


def api_request(rid, ts, cost=0.01, **extra):
    return {"event.name": "api_request", "session.id": "s", "prompt.id": "p", "request_id": rid, "model": "claude-opus-5-5",
            "event.timestamp": ts, "cost_usd": cost, "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0,
            "cache_creation_tokens": 0, **extra}


class Telemetry(unittest.TestCase):
    def load(self, *batches, wrap=True):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = [{"received": "now", "payload": b} if wrap else b for b in batches]
            write_jsonl(root / "logs-2026-11-01.jsonl", records)
            return cr.from_telemetry(root)

    def test_receiver_and_collector_formats_both_load(self):
        batch = log_batch(api_request("a", "2026-11-01T00:00:00.000Z"))
        self.assertEqual(len(self.load(batch, wrap=True)), 1)
        self.assertEqual(len(self.load(batch, wrap=False)), 1)

    def test_reported_write_split_is_used(self):
        calls = self.load(log_batch(api_request("a", "2026-11-01T00:00:00.000Z", cache_creation_tokens=100,
                                                cache_creation_1h_tokens=70, cache_creation_5m_tokens=30)))
        self.assertEqual(cr.write_split(calls[0]["usage"]), (30, 70))

    def test_write_split_is_recovered_from_cost_on_older_records(self):
        # 1M writes, all 1-hour on Opus 5.5 = $8; all 5-minute would be $5.
        calls = self.load(log_batch(api_request("a", "2026-11-01T00:00:00.000Z", cost=8.0, cache_creation_tokens=1_000_000)))
        self.assertEqual(cr.write_split(calls[0]["usage"]), (0, 1_000_000))

    def test_tool_goes_to_the_named_request(self):
        calls = self.load(log_batch(
            api_request("a", "2026-11-01T00:00:00.000Z"), api_request("b", "2026-11-01T00:00:10.000Z"),
            {"event.name": "tool_result", "session.id": "s", "prompt.id": "p", "request_id": "a", "tool_name": "Bash",
             "event.timestamp": "2026-11-01T00:00:20.000Z", "duration_ms": 1}))
        self.assertEqual({c["request"]: c["tools"] for c in calls}, {"a": ["Bash"], "b": []})

    def test_tool_without_a_request_id_goes_to_the_response_before_it_started(self):
        # Finished at 0:12 after running 5s, so it started at 0:07: requested by a, not b at 0:10.
        calls = self.load(log_batch(
            api_request("a", "2026-11-01T00:00:00.000Z"), api_request("b", "2026-11-01T00:00:10.000Z"),
            {"event.name": "tool_result", "session.id": "s", "prompt.id": "p", "tool_name": "Bash",
             "event.timestamp": "2026-11-01T00:00:12.000Z", "duration_ms": 5000}))
        self.assertEqual({c["request"]: c["tools"] for c in calls}, {"a": ["Bash"], "b": []})

    def test_mcp_tools_are_named_by_server_and_match_transcript_labels(self):
        calls = self.load(log_batch(
            api_request("a", "2026-11-01T00:00:00.000Z"),
            {"event.name": "tool_result", "session.id": "s", "prompt.id": "p", "request_id": "a", "tool_name": "mcp_tool",
             "tool_parameters": json.dumps({"mcp_server_name": "Claude Browser", "mcp_tool_name": "navigate"})}))
        self.assertEqual(calls[0]["tools"], ["MCP:Browser"])
        self.assertEqual(cr.tool_label("mcp__Claude_Browser__navigate"), "MCP:Browser")

    def test_session_repository_fills_calls_that_lack_it(self):
        calls = self.load(log_batch(
            api_request("a", "2026-11-01T00:00:00.000Z"),
            api_request("b", "2026-11-01T00:00:10.000Z", **{"vcs.repository.name": "app"})))
        self.assertEqual({c["project"] for c in calls}, {"app"})

    def test_account_fields_are_not_kept(self):
        calls = self.load(log_batch(api_request("a", "2026-11-01T00:00:00.000Z", **{"user.email": "a@example.com"})))
        self.assertNotIn("a@example.com", json.dumps(calls))


if __name__ == "__main__":
    unittest.main()
