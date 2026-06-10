---
name: active-slice
description: Internal Signature Harness module. Invoked by goal-loop or orchestration routing, not directly by general user requests.
---

# Active Slice

Large goals need a current slice. Do not shrink the user's global objective just to make the current step look complete.

## Inputs

- normalized Goal
- user-fit profile
- known roadmap
- constraints and non-goals
- available evidence

## Method

1. Identify the global goal.
2. Choose the smallest executable slice that can produce evidence.
3. Define a completion signal for the slice.
4. Mark roadmap items as `planned`, `active`, `complete`, or `blocked`.
5. Carry global context forward without claiming planned items are active capability.

## Output

```md
# Active Slice - <goal>

## Global Goal
<full objective>

## Active Slice
- id:
- objective:
- completion_signal:
- boundaries:

## Roadmap
- <slice id> - planned | active | complete | blocked

## Rationale
<why this is the right current slice>
```

Completion of the active slice is not completion of the global goal unless the roadmap says no work remains.
