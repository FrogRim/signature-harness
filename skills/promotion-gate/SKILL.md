---
name: promotion-gate
description: Decide whether an improvement candidate may update active Signature Harness rules, fit profile, Seed defaults, or strategy memory. Use before any candidate becomes active.
---

# Promotion Gate

Promotion is the boundary between evidence and memory mutation.

## Inputs

- improvement candidate
- supporting evidence
- oracle verdict
- regression or scope checks
- user-fit profile
- active rules and Seed defaults

## Verdicts

- `PROMOTE` - update active memory with the candidate.
- `KEEP_CANDIDATE` - retain as evidence, but do not activate yet.
- `REJECT` - mark as not useful or unsafe.
- `BLOCKED` - needs missing evidence, user choice, or external validation.

## Method

1. Confirm the candidate has concrete evidence.
2. Check whether the candidate overgeneralizes from one run.
3. Check non-goals and safety boundaries.
4. Check whether the candidate would make future goals worse.
5. Decide the verdict and required next action.

## Output

```md
# Promotion Gate - <candidate>

Verdict: PROMOTE | KEEP_CANDIDATE | REJECT | BLOCKED

## Evidence Check
- <evidence> -> sufficient | weak | missing

## Scope Check
- applies_when:
- does_not_apply_when:

## Regression Risk
<risk or none>

## Active Update
<only for PROMOTE>

## Required Next Action
<none only when PROMOTE or REJECT is final>
```

Promotion must be explicit. Silent fit or rule mutation is a harness bug.
