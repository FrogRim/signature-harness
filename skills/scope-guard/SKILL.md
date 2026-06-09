---
name: scope-guard
description: This skill should be used on every task to keep work inside the requested scope. It forces an explicit IN/OUT scope, blocks feature creep, and rejects vague requirements until clarified.
---
# Scope Guard

## Define scope first
Before acting, state plainly:
- **IN scope:** what was directly requested.
- **OUT of scope:** adjacent things you will not touch.

## Stay inside it
- Make only changes that are directly requested or clearly necessary.
- No unrequested refactors, no extra abstractions, no "while I'm here" additions, no helper files that were not asked for.
- A bug fix does not license cleaning up surrounding code.

## Reject vagueness
- If a requirement is ambiguous, ask before building. Do not fill the gap by inventing scope.
