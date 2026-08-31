# Deterministic AI Agent Reliability Harness

> **SAMPLE/DEMO ONLY.** Every prompt, order, failure, trace, latency, cost, and
> outcome in this repository is synthetic. The scorecards are not claims about
> a production system or a customer engagement.

This is a dependency-free proof asset for evaluating a tool-using AI agent as a
reproducible system rather than judging a few chat transcripts. It runs the same
versioned cases against two included implementations:

- `UnreliableAgent` is a deliberately incomplete happy-path baseline. It has no
  retries, response validation, idempotency, checkpointing, duplicate-event
  protection, or stale-state detection.
- `FixedAgent` is a resumable state machine with bounded retries, semantic
  result validation, stable idempotency keys, event deduplication, checkpoints,
  and optimistic-concurrency recovery.

The result is a real, reproducible before/after comparison. No network access,
API key, model call, customer record, or external service is used.

## One-command run

From this directory, run the complete suite and write JSON and Markdown reports:

```bash
python3 -m reliability_harness --suite full
```

The command runs 10 cases five times against both implementations (100 isolated
trials) and writes:

- `reports/sample_demo_full_scorecard.json` — detailed assertions, seeds, final
  state, errors, telemetry, and every trace event.
- `reports/sample_demo_full_scorecard.md` — compact stakeholder scorecard.

It exits non-zero if the fixed implementation does not score 100%.

For a quick local or CI check, use the three-case, two-trial smoke suite:

```bash
python3 -m reliability_harness --suite smoke
```

Override repetition explicitly with `--trials N`. The same case and trial always
use the same seed and simulated telemetry.

## Configure a release gate

The command can enforce explicit assertion and fully-passing-trial thresholds,
write those thresholds and results into both scorecards, and exit non-zero when
either check fails:

```bash
python3 -m reliability_harness --suite full \
  --min-assertion-score 100 \
  --min-trial-pass-rate 100
```

The public CI workflow runs that full gate on Python 3.10, 3.12, and 3.13 and
uploads the JSON and Markdown scorecards as a workflow artifact. A compatible
versioned case pack can be selected explicitly with `--casepack path/to/cases.json`.
The bundled runtime is intentionally specific to the synthetic refund workflow;
adapting another agent still requires the runtime and assertions described
below, rather than merely swapping JSON.

## What the harness verifies

Each trial independently scores eight properties:

1. expected tool choice with no unexpected tools;
2. first-success tool order;
3. semantic tool arguments from authoritative state;
4. expected final state and side-effect count;
5. bounded recovery from injected transient failures;
6. idempotency across ambiguous or repeated mutations;
7. duplicate-event suppression or checkpointed resume; and
8. complete, ordered trace telemetry with non-negative latency and cost fields.

The versioned case pack includes:

| Case | Injected condition | Primary behavior under test |
|---|---|---|
| `happy_refund` | none | nominal tool plan and state |
| `retry_rate_limit_429` | HTTP 429 | bounded retry |
| `duplicate_event` | same event twice | event deduplication |
| `retry_server_5xx` | pre-commit 5xx | bounded retry |
| `retry_timeout` | timeout | bounded retry |
| `malformed_tool_result` | missing response fields | semantic validation and retry |
| `ambiguous_5xx_after_commit` | mutation succeeds, response is 5xx | stable idempotency key |
| `interrupted_then_resumed` | interruption after committed mutation | checkpointed resume |
| `stale_order_state` | concurrent order update | version check, refresh, recompute |
| `authoritative_arguments` | caller requests an excessive amount | safe argument construction |

## Trace model

Every trace entry has a monotonically increasing sequence number plus
`latency_ms` and `cost_usd`. Tool-call entries also include tool name, attempt,
arguments, outcome, error code, and idempotency key. Orchestration events such as
retry, checkpoint resume, duplicate suppression, and synthetic concurrent update
use zero cost and explicitly simulated latency.

Costs and latency are deterministic fixture values so reports can be compared
byte-for-byte. A production adapter should replace them with measured telemetry.

## Run tests

```bash
python3 -m unittest discover -s tests -v
```

The tests cover case-pack integrity and failure-mode inventory, deterministic
replay, idempotent and non-idempotent mutation behavior, before/after scoring,
ambiguous commit recovery, interruption/resume, stale-state correction, trace
schema completeness, report serialization, and the CLI command.

## Reuse it for another agent

1. Add or version cases in `reliability_harness/casepacks/` using only synthetic
   fixtures. Keep expected tool sequence, semantic arguments, and final state
   explicit.
2. Adapt the local tools in `runtime.py`, preserving fault injection at the tool
   boundary and side effects in `SyntheticStore`.
3. Implement the same `run(request, runtime)` boundary used in `agents.py`.
4. Extend `_assertions` in `evaluator.py` with domain-specific invariants. Avoid
   replacing deterministic assertions with a subjective model grader when an
   exact check is possible.
5. Preserve the sample/demo label until real production traces and measurement
   methodology have been approved for reporting.

## Layout

```text
reliability_harness/
├── README.md
├── pyproject.toml
├── reliability_harness/
│   ├── __main__.py       # command-line runner
│   ├── agents.py         # unreliable and fixed implementations
│   ├── cases.py          # versioned case-pack loader and validation
│   ├── casepacks/v1.json # synthetic cases and expected behavior
│   ├── evaluator.py      # repeated trials and assertion scoring
│   ├── models.py         # case and trace data types
│   ├── reporting.py      # JSON and Markdown scorecards
│   └── runtime.py        # local tools, state, and fault injection
├── reports/
└── tests/
```

Python 3.10 or newer is required; the runtime itself uses only the standard
library.

## License

Apache-2.0. See `LICENSE`.
