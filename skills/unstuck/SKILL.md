---
name: unstuck
description: Internal Signature Harness stagnation-recovery module. Invoked by goal-loop or orchestration routing, not directly by general user requests.
---

# Unstuck

Use lateral thinking when continuing the same plan is unlikely to improve the result.

## Personas

- `hacker` - make the smallest thing work first
- `researcher` - identify missing facts or references
- `simplifier` - cut scope back to the smallest useful version
- `architect` - restructure the approach
- `contrarian` - challenge whether this is the right problem

## Inputs

- current Goal
- active Seed
- current approach
- failed attempts
- oracle/red-team findings
- user-fit profile

## Method

1. State the stuck point in one paragraph.
2. State the current approach and why it is not working.
3. Run one or more personas mentally or through subagents when available.
4. Synthesize options into a concrete recommendation.
5. Return to `evolution-loop`, `goal-loop`, or clarification.

## Output

```md
# Unstuck - <goal>

## Stuck Point
<what is repeating or blocked>

## Persona Findings
- hacker:
- researcher:
- simplifier:
- architect:
- contrarian:

## Recommendation
<continue | evolve | clarify | stop>

## Next Action
<smallest concrete step>
```

Do not use unstuck as generic brainstorming. Use it when the loop is actually stagnant or assumption-heavy.
