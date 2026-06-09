---
name: sh-goal
description: Short public alias for Signature Harness goal-loop work. Use when a user invokes SH through the compact $sh-goal command and wants goal intake, routing, red-team pressure, execution checkpoints, and oracle verification.
---

# SH Goal

This is the compact public alias for `goal-loop`.

Use the same operating contract as the `goal-loop` skill:

1. Normalize the request into a Goal.
2. Preserve the global goal and select the current active slice.
3. Score ambiguity before broad execution.
4. Crystallize or reference an accepted Seed for broad, risky, long-running, or multi-step work.
5. Read only relevant active rules.
6. Route through `orchestration-loop` when the task is broad, resumable, high-risk, or multi-agent.
7. Use `red-team` before risky mutation and before non-trivial completion claims.
8. Execute in bounded steps with checkpoint evidence.
9. Require `oracle-verification` before claiming completion.
10. If Oracle returns `INCOMPLETE`, enter `GAP_FILL`; do not retry the same plan.

Prefer the smallest loop that can close the current active slice with evidence.
