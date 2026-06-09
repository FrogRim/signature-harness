---
name: gap-closure
description: Record Signature Harness gaps with boundary, closure path, evidence source, and promotion or verification gate. Use when a capability is planned, incomplete, blocked, or intentionally out of scope.
---

# Gap Closure

A known gap is acceptable only when it is explicit and has a closure path.

## Inputs

- goal or active slice
- missing capability, evidence, or decision
- current boundary
- risk if ignored
- proposed closure path

## Method

1. State the gap plainly.
2. Define the current boundary.
3. Explain why the gap matters.
4. Attach a closure path.
5. Attach the evidence source and verification/promotion gate.
6. Report residual risk if the gap remains open.

## Output

```md
# Gap Closure - <gap>

## Gap
<what is missing>

## Current Boundary
<what is currently true>

## Why It Matters
<risk or impact>

## Closure Path
<how to close it>

## Evidence Source
<artifact, trace, test, source, or user decision>

## Gate
verification | promotion | user-decision | external-dependency

## Status
open | accepted-risk | closed | blocked
```

Do not hide gaps behind optimistic completion language.
