# Interpreting pmx output

Load this when deciding which miner to use, or when a discovered model needs
to be made readable.

## Reading an `inspect` profile

| What you see | What it means | What to do |
|---|---|---|
| `cases` ≈ `events` | One event per case -- no sequences | Nothing to mine; the case column is probably wrong |
| `variants` = 1 | Every case follows the same path | The model will be a straight line, which is correct |
| `variants` ≈ `cases` | Almost every case is unique | Expect a tangled model; plan on `--top-variants` |
| Many `end_activities` | Cases finish in many states | Often real (cancellations, rejections), sometimes truncated data |
| One `start_activity` | Clean, well-scoped log | Good sign |
| `variants` ≫ `distinct_activity_sets` | Variants are re-orderings of the same work | Concurrency, not complexity -- `--top-variants`, not `--noise-threshold` |
| `singleton_variants` is most of `variants` | A long tail of one-off paths | Safe to filter; they are ~none of the cases |
| median case duration ≪ mean | A few very long cases skew the process | Worth calling out; the mean is not the typical case |

Variant count is the single best predictor of model readability. Under ~20 and
the model is usually legible; in the hundreds it will not be without
filtering.

`inspect` reports the concentration directly -- `variants_for_50pct`,
`variants_for_80pct`, `variants_for_95pct` in JSON, and a one-line summary on
stderr in the table view. **Use `variants_for_80pct` as the starting value for
`--top-variants`.** It is the smallest model that still describes most of the
log.

`distinct_activity_sets` counts variants after collapsing re-orderings. When it
is far below `variants`, the log's apparent complexity is concurrent execution
of the same activities -- `receipt.xes` has 116 variants but only 50 activity
sets, and 89% of its cases use just six activities in 21 different orders. No
noise threshold removes that, because it is not noise.

The `first_event`/`last_event` span is worth checking against what the user
expects. A log that ends months before today is often an extract, and any
conclusion about "current" behaviour would be wrong.

## Choosing a miner

**`inductive`** (default) is the right answer unless you have a reason. It
guarantees a *sound* model -- no deadlocks, every task reachable, always able
to reach completion. Its `--noise-threshold` is the only principled complexity
control the CLI offers.

**`heuristics`** tolerates noise and infrequent behaviour by looking at how
often one activity follows another. Reach for it on messy real-world logs
where the inductive model is dominated by silent transitions. It does not
guarantee soundness, and it cannot produce BPMN here.

**`alpha`** is the original 2004 algorithm, kept for teaching and baselines.
It cannot handle loops of length one or two, silent transitions, or noise, and
it produces unsound models on most real logs. Do not recommend it for
analysis -- only when the user explicitly wants the classic result.

## Making a model readable

There are two knobs, and they are not equally useful.

**`--top-variants N` / `--min-coverage F` (reach for these first.)** These drop
rare variants from the log before mining. On pm4py's `receipt.xes` (1,434
cases, 116 variants):

```bash
pmx discover receipt.xes --top-variants 10 -o model.bpmn --notation bpmn -i model.png
```

| Filter | Transitions | Cases kept |
|---|---|---|
| none | 74 | 100% |
| `--noise-threshold 0.2` | 69 | 100% |
| `--top-variants 10` | 14 | 87.9% |
| `--top-variants 5` | 9 | 79.6% |

Start from `variants_for_80pct` in the `inspect` profile. `--min-coverage 0.8`
does the same thing expressed as a share of cases rather than a count.

**`--noise-threshold` (secondary.)** It filters infrequent behaviour inside the
inductive miner. The effect is real but erratic -- on `receipt.xes`, 74
transitions become 69 at 0.2, 42 at 0.3 and 57 at 0.4, so a higher threshold
does not reliably mean a smaller model -- and it cannot touch concurrency, so
on a log with a high `variants`-to-`distinct_activity_sets` ratio it will
disappoint. Values above ~0.5 discard so much that the model stops describing
the log.

For the heuristics miner the equivalent knob is `--dependency-threshold`:
raising it keeps only edges with stronger evidence, which also thins the
model.

**Always tell the user what produced a model** -- which filter, and what share
of cases survived. pmx prints this on stderr (`filtered to 10 of 116 variants
(1,260 of 1,434 cases, 87.9%)`); pass it on. A filtered model is a claim about
*frequent* behaviour, not about the process, and presenting one without that
caveat overstates it.

## What the output files are

**PNML** (`.pnml`) is a Petri net: places, transitions, arcs, plus an initial
and final marking. Transitions with no label are *silent* -- routing
constructs the miner added, not real activities. A model full of them usually
means the log has more concurrency than the notation shows comfortably.

**BPMN** (`.bpmn`) is the business-facing notation, and the one to hand to
someone who is not a process-mining specialist. It opens in Camunda Modeler,
bpmn.io, and Signavio.

Both are XML and safe to read directly if you need to count elements, but do
not try to reason about process semantics by reading the raw XML -- render it
or report the `inspect` variants instead.

## Honest limits

`discover` tells you what a model *looks like*. It does not tell you how well
that model fits the log -- that is conformance checking, which this CLI does
not do. Never describe a discovered model as "accurate", "validated", or
"87% conformant". The defensible statement is that the model was mined from
the log with a named algorithm at a named threshold.

## No shared path

When nearly every case takes its own route, a mined model is a "flower" -
any activity, in any order - and `--top-variants` cannot rescue it, because
each variant covers a single case. Drawing that model presents structure the
data does not have. Do not run `discover`; say plainly that the cases share
no common path, then test whether anything is ordered at all:

```bash
pmx dfg LOG --json | python3 -c '
import json, sys
from collections import Counter
edges = json.load(sys.stdin)["edges"]
total = sum(e["count"] for e in edges)
out, into = Counter(), Counter()
for e in edges:
    out[e["from"]] += e["count"]
    into[e["to"]] += e["count"]
for e in edges:
    e["lift"] = e["count"] * total / (out[e["from"]] * into[e["to"]])
common = [e for e in edges if e["count"] >= 20]
for e in sorted(common, key=lambda e: -e["lift"])[:10]:
    print(round(e["lift"], 1), e["from"], "->", e["to"], e["count"])
'
```

Lift is how many times more often B follows A than it would if the next
step were independent of the current one. Lifts near 1 across the board
mean the order is random - report that, with the most frequent activities
and start activities from `inspect`, as the finding. A lift of 2 or more on
a large count is a real follow-on worth naming even inside an unstructured
log.
