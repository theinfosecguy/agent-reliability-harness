# SAMPLE/DEMO — AI Agent Reliability Scorecard

> All prompts, orders, faults, traces, costs, and outcomes are synthetic demonstration data. They are not production measurements.

Suite: `smoke` · Case pack: `1.0.0` · Cases: 3 · Repeated trials per case: 2

## Before / after

| Implementation | Assertion score | Fully passing trials | Completion rate | Simulated latency | Simulated cost |
|---|---:|---:|---:|---:|---:|
| Before: unreliable demo | 62.50% (30/48) | 33.33% (2/6) | 66.67% | 444 ms | $0.001340 |
| After: fixed demo | 100.00% (48/48) | 100.00% (6/6) | 100.00% | 446 ms | $0.001340 |

Improvement: **+37.50 percentage points** in assertion score and **+66.67 points** in fully passing trials.

## Case results

| Case | Injected fault | Before score | After score |
|---|---|---:|---:|
| `happy_refund` | none | 100.00% | 100.00% |
| `retry_rate_limit_429` | 429 | 25.00% | 100.00% |
| `duplicate_event` | duplicate_event | 62.50% | 100.00% |

## Assertions

Each trial independently checks tool choice, tool order, semantic arguments, final state, retry recovery, mutation idempotency, duplicate/resume handling, and trace completeness.

The JSON scorecard contains every per-trial assertion, deterministic seed, final state, error, and trace event. Latency and cost values are simulated demo telemetry, not production benchmarks.
