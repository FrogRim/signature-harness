---
name: evolution-loop
description: Internal Signature Harness recovery module. Invoked by goal-loop or orchestration routing, not directly by general user requests.
---

# Evolution Loop

Use evolution when the current Seed is no longer the best contract for the goal.

## Inputs

- current Goal
- active Seed
- oracle verdict
- drift scores
- red-team findings
- execution evidence
- improvement candidates
- promotion decisions
- user-fit profile

## Triggers

- oracle returns `INCOMPLETE` because the Seed is wrong or too weak, not merely because proof is missing
- `GAP_FILL` failed repeatedly and red-team/oracle show the current Seed cannot guide proof acquisition
- goal, constraint, ontology, or evidence drift is high
- repeated verification failures share the same root cause
- red-team repeatedly finds the same hidden assumption
- implementation keeps oscillating between approaches
- promotion gate rejects or blocks the same candidate class repeatedly

## Method

1. Identify whether the failure is missing proof, execution failure, or Seed failure.
2. If only proof is missing and the Seed remains valid, route to `GAP_FILL` instead of evolution.
3. If execution failure remains inside a valid Seed, return a narrowed active slice rather than ordinary retry.
4. If rule memory is missing or stale, create an `improvement-candidate`.
5. If Seed failure, reflect on what changed.
6. Propose a new Seed generation with explicit deltas.
7. Preserve lineage: old Seed is `superseded`, new Seed is `draft` until accepted.
8. Route the new Seed through `red-team` before execution.

## Output

```md
# Evolution - <goal>

Decision: gap-fill | narrow-active-slice | create-new-seed | clarify | unstuck

## Failure Signal
- <oracle/red-team/evidence finding>

## Drift
- goal_drift:
- constraint_drift:
- ontology_drift:
- evidence_gap:

## Seed Delta
- <old> -> <new>

## Next Generation
<new Seed draft or reason not created>

## Candidate / Promotion
- candidate:
- promotion_gate:
```

Do not silently mutate an accepted Seed. Create a new generation.
