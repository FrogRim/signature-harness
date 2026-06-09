---
name: parallel-hypothesis
description: Run independent agents or attempts as comparable hypothesis experiments. Use when parallel work tests different strategies, plans, fixes, or research paths.
---

# Parallel Hypothesis

Parallelism is useful when each lane tests a distinct hypothesis and returns comparable evidence.

## Inputs

- global goal and active slice
- accepted Seed
- competing hypotheses
- evaluation criteria
- budget and boundaries

## Method

1. Define one hypothesis per lane.
2. Assign each lane a bounded task and evidence format.
3. Score each run using the same criteria.
4. Extract reusable wins and anti-patterns.
5. Create improvement candidates for anything that should persist.
6. Let the leader own promotion.

## Output

```md
# Parallel Hypothesis - <goal>

## Runs
- id:
  hypothesis:
  evidence:
  progress_score:
  stuck_signals:
  uncertainty_rate:
  recommendation: promote | keep-candidate | prune | rerun

## Best Evidence
<which hypothesis worked and why>

## Candidates
- <candidate ids or summaries>
```

Worker results are evidence. They are not active memory updates.
