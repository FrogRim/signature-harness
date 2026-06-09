---
name: improvement-candidate
description: Convert trace-backed failures, wins, fit friction, or rule gaps into candidate updates. Use after oracle failures, repeated mistakes, successful reusable patterns, or user corrections. Candidates are not active rules until promotion.
---

# Improvement Candidate

The harness may learn from runs, but learning starts as a candidate.

## Inputs

- run trace or evidence summary
- active Goal, active slice, and Seed
- oracle verdict
- red-team findings
- user correction or fit friction
- current active rules

## Candidate Types

- `rule` - a new or changed operating rule
- `skill` - a reusable procedure
- `fit` - user preference or interaction default
- `seed-default` - a better default for future Seed generation
- `anti-pattern` - a repeated failure to avoid
- `gap` - a closure path for missing capability

## Method

1. Identify the trace-backed signal.
2. Reject vague reflection without evidence.
3. Decide whether the signal is a failure, reusable win, fit friction, or gap.
4. Create a candidate with evidence and scope.
5. Send the candidate to `promotion-gate` before it becomes active.

## Output

```md
# Improvement Candidate - <goal>

Status: candidate
Type: rule | skill | fit | seed-default | anti-pattern | gap

## Evidence
- <trace, command, user correction, oracle finding, or red-team finding>

## Proposed Change
<candidate update>

## Scope
- applies_when:
- does_not_apply_when:

## Promotion Requirements
- <test, replay, review, oracle, or user confirmation>
```

Never update active memory directly from a single confident explanation.
