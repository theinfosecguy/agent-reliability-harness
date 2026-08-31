# SAMPLE/DEMO — AI Agent Reliability Scorecard

> All prompts, orders, faults, traces, costs, and outcomes are synthetic demonstration data. They are not production measurements.

Suite: `full` · Case pack: `1.0.0` · Cases: 10 · Repeated trials per case: 5

## Before / after

| Implementation | Assertion score | Fully passing trials | Completion rate | Simulated latency | Simulated cost |
|---|---:|---:|---:|---:|---:|
| Before: unreliable demo | 48.75% (195/400) | 10.00% (5/50) | 50.00% | 2918 ms | $0.009000 |
| After: fixed demo | 100.00% (400/400) | 100.00% (50/50) | 100.00% | 4133 ms | $0.012800 |

Improvement: **+51.25 percentage points** in assertion score and **+90.00 points** in fully passing trials.

## Release gate

Status: **PASS**

| Check | Minimum | Actual | Result |
|---|---:|---:|---:|
| Assertion score | 100.00% | 100.00% | PASS |
| Fully passing trials | 100.00% | 100.00% | PASS |

## Case results

| Case | Injected fault | Before score | After score |
|---|---|---:|---:|
| `happy_refund` | none | 100.00% | 100.00% |
| `retry_rate_limit_429` | 429 | 25.00% | 100.00% |
| `duplicate_event` | duplicate_event | 62.50% | 100.00% |
| `retry_server_5xx` | 5xx | 25.00% | 100.00% |
| `retry_timeout` | timeout | 25.00% | 100.00% |
| `malformed_tool_result` | malformed_result | 25.00% | 100.00% |
| `ambiguous_5xx_after_commit` | 5xx_after_commit | 25.00% | 100.00% |
| `interrupted_then_resumed` | interrupted_resumed_run | 62.50% | 100.00% |
| `stale_order_state` | stale_state | 62.50% | 100.00% |
| `authoritative_arguments` | none | 75.00% | 100.00% |

## Assertions

Each trial independently checks tool choice, tool order, semantic arguments, final state, retry recovery, mutation idempotency, duplicate/resume handling, and trace completeness.

The JSON scorecard contains every per-trial assertion, deterministic seed, final state, error, and trace event. Latency and cost values are simulated demo telemetry, not production benchmarks.
