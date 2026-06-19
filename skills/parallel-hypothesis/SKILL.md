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

Parallel fan-out is default-deny. Use serial execution unless the dispatch gate
below passes.

## Dispatch Gate

Fan-out is allowed only when all conditions are true:

- lanes test independent hypotheses or operate on independent write targets
- each lane has a bounded deliverable and evidence format
- every lane can be scored by the same evaluation criteria
- a leader owns synthesis, conflict handling, and the final completion decision
- expected coordination cost is lower than the expected quality or throughput gain
- the dynamic workflow cost gate is already satisfied

Do not fan out when requirements are still ambiguous, lanes would edit the same
surface without isolation, no evaluator exists, or synthesis would be mostly
subjective. If conflict resolution becomes the main work, treat that as failed
decomposition and return to active-slice narrowing instead of merging noise.

## Inputs

- global goal and active slice
- accepted Seed
- competing hypotheses
- evaluation criteria
- budget and boundaries
- independence evidence
- dynamic workflow cost gate result

## Method

1. Check the dispatch gate. If it fails, return `serial_required` with the reason.
2. Define one hypothesis per lane.
3. Assign each lane a bounded task and evidence format.
4. Score each run using the same criteria.
5. Extract reusable wins and anti-patterns.
6. Create improvement candidates for anything that should persist.
7. Write or update the dynamic workflow evidence contract.
8. Let the leader own promotion.

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

## Dispatch Gate
- fan_out_allowed: yes | no
- independence_evidence:
- cost_gate:
- serial_fallback:

## Candidates
- <candidate ids or summaries>

## Evidence Contract
- dynamic_workflow_evidence_path:
- validation_command: `py scripts/sh_runtime.py validate-workflow-evidence --evidence <path>`
- completion_allowed:
- incomplete_record_ids:
```

Worker results are evidence. They are not active memory updates.
