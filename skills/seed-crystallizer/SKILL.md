---
name: seed-crystallizer
description: Internal Signature Harness module. Invoked by goal-loop or orchestration routing, not directly by general user requests.
---

# Seed Crystallizer

Turn a Goal into a stable Seed. A Seed is the execution contract used by planners, executors, red-team review, oracle verification, and evolution.

## Inputs

- normalized goal
- user-fit profile
- known constraints and non-goals
- decision boundaries
- verification expectations
- ambiguity score

## Ambiguity Gate

Score ambiguity from `0.0` to `1.0`:

- objective clarity
- constraint clarity
- measurable success criteria
- context/codebase clarity
- non-goals and decision boundaries
- verification path clarity

Rules:

- `0.00-0.20`: Seed may be accepted.
- `0.21-0.40`: accept only for small reversible work; otherwise clarify.
- `>0.40`: do not execute; clarify or inspect missing context.

## Seed Schema

```yaml
seed_id: ""
goal_id: ""
generation: 1
objective: ""
constraints: []
acceptance_criteria: []
non_goals: []
ontology:
  entities: []
  relationships: []
evaluation_plan:
  mechanical: []
  semantic: []
  consensus_trigger: ""
exit_conditions: []
seed_hash: ""
status: draft | accepted | superseded
```

## Method

1. Re-read the Goal and user-fit profile.
2. Score ambiguity.
3. Fill the Seed schema without inventing missing scope.
4. Restate the goal and Seed boundaries.
5. If the Seed is safe to accept, mark `status: accepted`.
6. If not, return the smallest clarification or context lookup needed.

## Output

```md
# Seed - <goal>

Status: draft | accepted | blocked
Ambiguity Score: 0.0-1.0

## Restated Goal
<one clear paragraph>

## Seed YAML
<seed yaml block>

## Blocking Ambiguity
- <only when status is blocked>
```

Do not treat a conversational prompt as a Seed for broad work.
