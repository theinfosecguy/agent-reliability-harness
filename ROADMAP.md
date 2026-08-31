# Roadmap

The current repository is a runnable proof asset, not a stable production
library. All inputs, state, faults, traces, latency, cost, and outcomes are
synthetic.

## Current proof

- Versioned JSON case pack with smoke and full suites.
- Ten cases covering nominal behavior, 429, 5xx, timeout, malformed output,
  ambiguous commit, duplicate event, interruption/resume, stale state, and
  authoritative argument construction.
- Five repeated trials per case against unreliable and fixed implementations.
- Eight assertions per trial plus JSON and Markdown reports.
- Dependency-free Python runtime and 18 unit tests.

## Proposed v0.1 public release

- Publish a documented case and normalized trace specification.
- Stabilize a generic callable adapter before framework-specific adapters.
- Add at least 50 versioned cases across two reference agents.
- Add at least eight reusable deterministic failure profiles.
- Add trace redaction rules and tests for common credentials and personal data.
- Add JSON, Markdown, and JUnit-compatible output.
- Add copyable pull-request smoke and scheduled-suite CI examples.
- Publish raw artifacts and cross-environment reproduction instructions.

## Deliberate non-goals

- Hosted telemetry or a proprietary control plane.
- A new agent orchestration framework.
- Model training or fine-tuning.
- A claim that passing a bounded suite proves general correctness or uptime.
- Required submission of traces to any external service.
