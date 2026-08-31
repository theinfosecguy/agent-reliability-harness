# Contributing

This repository is a synthetic demonstration of deterministic reliability
testing for tool-using agents. Contributions should preserve that boundary.

## Before opening a change

1. Do not add customer data, production traces, credentials, personal data, or
   confidential prompts. Use clearly synthetic fixtures.
2. Prefer exact state, tool, argument, order, latency, cost, and trace assertions
   when a deterministic check is possible.
3. Keep semantic or model-based graders optional and label their variability,
   model, prompt, and trial count.
4. Add or update tests for every new failure profile or assertion.
5. Do not present sample results as evidence about a production system.

## Local checks

```bash
python3 -m unittest discover -s tests -v
python3 -m reliability_harness --suite smoke
python3 -m reliability_harness --suite full
```

The fixed reference implementation must retain a 100% assertion score on the
included deterministic case pack. A change to that threshold requires an
explicit case-pack version change and an explanation in the changelog.

## Pull-request notes

Describe the failure mode, why the assertion is sound, the synthetic fixture,
and the before/after result. Include raw counts and trial counts, not only a
percentage. Call out any simulated measurement or nondeterministic component.

By contributing, you agree that your contribution is licensed under Apache-2.0.
