---
name: rule-memory-read
description: Select only the active Signature Harness rules relevant to the current goal, active slice, loop type, evidence state, and user-fit profile. Use before broad planning or execution to avoid giant prompts and stale memory.
---

# Rule Memory Read

Read the rules that apply now. Do not inject the entire guidebook, all preferences, or every prior lesson into the active prompt.

## Rule Layers

- `control` - safe tool and authority boundaries
- `mode` - build, debug, review, research, cleanup, performance behavior
- `user-fit` - calibrated preferences and interaction defaults
- `domain` - project-specific facts and constraints
- `failure` - known anti-patterns and repeated mistakes
- `promotion` - rules promoted through evidence gates

## Inputs

- active slice
- accepted Seed
- loop type
- current evidence or trace summary
- user-fit profile
- known promoted rules

## Method

1. Identify current mode and active slice.
2. Select only rules that apply to the current state.
3. Prefer deterministic/mechanical authority before LLM fallback.
4. Include known failure rules only when they can change execution.
5. Return a compact rule pack for the plan/executor.

## Output

```md
# Rule Memory Read - <goal>

## Active Slice
<slice id/objective>

## Selected Rules
- [layer] <rule id> - <why it applies>

## Deterministic Authority
- <check/action the harness should do before LLM speculation>

## Fallback Boundary
<when the model may reason or ask>
```

If a useful rule is missing, create an `improvement-candidate`; do not invent active rule memory inline.
