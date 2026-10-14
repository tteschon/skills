#!/usr/bin/env python3
"""Check that an event log CSV can actually be mined, before anyone mines it.

A log can parse cleanly and still describe no process: every row stamped with
the same load time, one event per case, or two copies of every row. pmx and
pm4py will mine those without complaint and draw a model that is invented.
This reports each problem with the number that decided it.

Stdlib only. Exits 1 if any check FAILs, 0 otherwise (WARNs included).

Usage:
  python3 check_log.py events.csv
  python3 check_log.py events.csv --case session --activity tool --timestamp ts
"""

from __future__ import annotations

import argparse
import csv
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime

XES_CASE = "case:concept:name"
XES_ACTIVITY = "concept:name"
XES_TIMESTAMP = "time:timestamp"

results: list[tuple[str, str]] = []


def report(level: str, message: str) -> None:
    results.append((level, message))


# The forms real exports use that datetime.fromisoformat rejects before 3.11:
# a trailing Z (most APIs), +0000 with no colon (Salesforce), and fractional
# seconds that are not exactly 3 or 6 digits. macOS still ships 3.9.
_ZULU = re.compile(r"Z$")
_COMPACT_OFFSET = re.compile(r"([+-]\d{2})(\d{2})$")
_FRACTION = re.compile(r"\.(\d+)")


def parse(value: str) -> tuple[datetime | None, bool]:
    """Parse one timestamp. Returns (datetime or None, has_time_of_day)."""
    text = value.strip()
    if not text:
        return None, False
    has_time = len(text) > 10 and text[10] in "T "
    text = _ZULU.sub("+00:00", text)
    if has_time:
        text = _COMPACT_OFFSET.sub(r"\1:\2", text)
    text = _FRACTION.sub(lambda m: "." + m.group(1)[:6].ljust(6, "0"), text)
    try:
        return datetime.fromisoformat(text), has_time
    except ValueError:
        return None, has_time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("log")
    parser.add_argument("--case", default=XES_CASE)
    parser.add_argument("--activity", default=XES_ACTIVITY)
    parser.add_argument("--timestamp", default=XES_TIMESTAMP)
    parser.add_argument("--separator", default=",")
    args = parser.parse_args()

    with open(args.log, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=args.separator)
        columns = reader.fieldnames or []
        missing = [
            c for c in (args.case, args.activity, args.timestamp) if c not in columns
        ]
        if missing:
            print(f"FAIL  missing column(s) {missing}; the file has {columns}")
            return 1
        rows = [(r[args.case], r[args.activity], r[args.timestamp]) for r in reader]

    if not rows:
        print("FAIL  the log has no rows")
        return 1

    # --- timestamps ---------------------------------------------------------
    parsed: list[datetime] = []
    unparseable: list[str] = []
    date_only = 0
    aware = naive = 0
    offsets: Counter[str] = Counter()
    for _, _, raw in rows:
        moment, has_time = parse(raw)
        if moment is None:
            unparseable.append(raw)
            continue
        parsed.append(moment)
        if not has_time:
            # A bare date has no offset by nature; it is reported as
            # date-only below, not counted again as a naive timestamp.
            date_only += 1
            continue
        if moment.tzinfo is None:
            naive += 1
        else:
            aware += 1
            offsets[str(moment.utcoffset())] += 1

    if unparseable:
        sample = ", ".join(repr(v) for v in unparseable[:3])
        report(
            "FAIL",
            f"{len(unparseable)} of {len(rows)} timestamps do not parse as "
            f"ISO 8601 (e.g. {sample}); rewrite them as YYYY-MM-DDTHH:MM:SS+00:00",
        )
    if parsed and len({p.replace(tzinfo=None) for p in parsed}) == 1:
        report(
            "FAIL",
            f"all {len(rows)} rows share one timestamp ({rows[0][2]}) - this is "
            "a load or import time, not when anything happened, so no order "
            "exists to mine",
        )
    if date_only:
        report(
            "WARN",
            f"{date_only} of {len(rows)} timestamps carry a date but no time - "
            "steps on the same day have no order, and the model will guess",
        )
    if aware and naive:
        report(
            "WARN",
            f"{aware} timestamps carry a UTC offset and {naive} do not - "
            "mixed sources; normalise everything to UTC",
        )
    elif len(offsets) > 2:
        report(
            "WARN",
            f"{len(offsets)} different UTC offsets ({', '.join(offsets)}) - more "
            "than one zone's DST pair; check the sources agree, or convert to UTC",
        )

    # --- structure ----------------------------------------------------------
    duplicates = sum(n - 1 for n in Counter(rows).values() if n > 1)
    if duplicates:
        level = "FAIL" if duplicates * 2 >= len(rows) else "WARN"
        report(
            level,
            f"{duplicates} of {len(rows)} rows are exact duplicates of another "
            "(same case, activity and timestamp) - drop them, or every count "
            "and path doubles",
        )

    by_case: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for case, activity, raw in rows:
        by_case[case].append((activity, raw))
    sizes = [len(events) for events in by_case.values()]
    single = sum(1 for n in sizes if n == 1)
    share = single / len(sizes)
    if share > 0.5:
        report(
            "FAIL",
            f"{single} of {len(sizes)} cases ({share:.0%}) have a single event - "
            "there is no path to mine; the case id is probably too fine "
            "(one row = one case), or only the current state was exported",
        )
    elif share > 0.2:
        report(
            "WARN",
            f"{single} of {len(sizes)} cases ({share:.0%}) have a single event",
        )

    multi = [events for events in by_case.values() if len(events) > 1]
    if multi:
        frozen = sum(1 for events in multi if len({t for _, t in events}) == 1)
        if frozen == len(multi):
            report(
                "FAIL",
                "every multi-event case has all its events at one instant - "
                "within a case nothing has an order",
            )
        tied = sum(
            n
            for events in multi
            for n in Counter(t for _, t in events).values()
            if n > 1
        )
        if tied and tied < len(rows) and tied / len(rows) > 0.1:
            report(
                "WARN",
                f"{tied} events ({tied / len(rows):.0%}) share a timestamp with "
                "another event in the same case - their order is arbitrary",
            )

    activities = Counter(activity for _, activity, _ in rows)
    if len(activities) > 0.5 * len(rows) and len(rows) > 20:
        report(
            "WARN",
            f"{len(activities)} distinct activities in {len(rows)} rows - "
            "activity names probably carry ids, dates or free text; use the "
            "status or step name only",
        )

    # --- summary ------------------------------------------------------------
    # Offset-aware and naive datetimes cannot be compared, so no span exists.
    if aware and naive:
        span = "? (mixed offset-aware and naive timestamps)"
    elif parsed:
        span = f"{min(parsed).isoformat()} to {max(parsed).isoformat()}"
    else:
        span = "?"
    print(
        f"{len(rows)} events, {len(sizes)} cases, {len(activities)} activities; "
        f"median {statistics.median(sizes):g} events per case; {span}"
    )
    for level, message in results:
        print(f"{level}  {message}")
    if not results:
        print("PASS  no problems found - ready for `pmx inspect`")
    return 1 if any(level == "FAIL" for level, _ in results) else 0


if __name__ == "__main__":
    sys.exit(main())
