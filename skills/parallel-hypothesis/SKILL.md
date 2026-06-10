---
name: parallel-hypothesis
description: Internal Signature Harness parallel-evidence module. Invoked by goal-loop or orchestration routing, not directly by general user requests.
---

# Parallel Hypothesis

Parallelism is useful when each lane tests a distinct hypothesis and returns comparable evidence.

Use this skill as a dynamic workflow lane only when the selected pattern is
`fan-out-and-synthesize`, `tournament`, or `generate-and-filter`. If the task
does not need comparable independent lanes, do not fan out just to spend more
tokens.

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
6. Write or update the dynamic workflow evidence contract.
7. Let the leader own promotion.

## Output

```md
# Parallel Hypothesis - <goal>

## Runs
- id:
  hypothesis:
  dynamic_workflow_pattern:
  evidence:
  progress_score:
  stuck_signals:
  uncertainty_rate:
  recommendation: promote | keep-candidate | prune | rerun

## Best Evidence
<which hypothesis worked and why>

## Candidates
- <candidate ids or summaries>

## Evidence Contract
- dynamic_workflow_evidence_path:
- validation_command: `py scripts/sh_runtime.py validate-workflow-evidence --evidence <path>`
- completion_allowed:
- incomplete_record_ids:
```

Worker results are evidence. They are not active memory updates.
