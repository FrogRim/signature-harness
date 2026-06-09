---
description: Run the Signature Harness goal loop with routing, red-team pressure, and oracle verification.
argument-hint: <goal or problem>
---

You are orchestrating the **Signature Harness (SH)** goal loop for this request:

$ARGUMENTS

Run the goal loop. The goal is verified completion, not a hopeful status update.

1. **Normalize the goal.**
   - Identify objective, why, success criteria, constraints, non-goals, decision boundaries, verification, and stop condition.
   - Preserve the global goal and select the current active slice.
   - If the request is too vague to route safely, invoke the `deep-interview` skill first.

2. **Score ambiguity and lock a Seed.**
   - Estimate ambiguity across objective, constraints, success criteria, context, non-goals, and decision boundaries.
   - If ambiguity is materially high, clarify before execution.
   - Invoke `seed-crystallizer` for broad, multi-step, risky, or long-running work.
   - Restate the goal before accepting the Seed.

3. **Select the loop and control-plane route.**
   - Choose one: `clarify`, `research`, `build`, `debug`, `performance`, `cleanup`, or `review`.
   - State why this loop fits the goal.
   - For broad, long-running, resumable, high-risk, or multi-agent work, invoke `orchestration-loop` as the read-only control plane before execution.

4. **Read active rules.**
   - Invoke `rule-memory-read` for broad, repeated, or user-fit-sensitive work.
   - Read only relevant rules for the active slice, loop type, and current evidence.
   - Prefer deterministic/mechanical authority before LLM fallback.

5. **Pressure-test before mutation.**
   - Invoke the `red-team` skill for any Seed, plan, high-risk branch, or broad execution request.
   - A `BLOCK` verdict must be resolved before implementation or completion.

6. **Execute/checkpoint.**
   - Work in bounded steps.
   - Emit heartbeat/checkpoint state for non-trivial work: 60s tick, 180s missed, 300s hard-abort candidate unless the active Seed sets a stricter bound.
   - Read `.sh/orchestration/directives/<run_id>.json` before each tick when a runtime exists.
   - Preserve evidence for each meaningful completion claim.
   - Record trace events for decisions, evidence, checks, failures, and reroutes when the work is non-trivial.
   - Use subagents/team execution only when independent lanes materially improve throughput or quality.
   - Treat subagents as `parallel-hypothesis` runs when they test competing strategies.

7. **Verify through the oracle.**
   - Invoke `oracle-verification` before claiming the goal complete.
   - Run mechanical checks first, then semantic alignment/drift checks, then consensus only when uncertainty or risk justifies it.
   - If Oracle returns `COMPLETE`, stop execution and let orchestration write a close directive.
   - If Oracle returns `INCOMPLETE`, treat it as a verdict, not a state. Use its evidence gap report to dispatch a `GAP_FILL` slice instead of retrying.
   - If Oracle returns `BLOCKED`, park the run and require blocked rehydration through an allowlisted `resume_check` contract.

8. **Create candidates, then promote deliberately.**
   - Invoke `improvement-candidate` when traces show repeated failure, reusable success, fit friction, or rule gaps.
   - Invoke `promotion-gate` before any candidate updates active rules, user-fit defaults, or seed defaults.
   - Invoke `gap-closure` for accepted gaps or planned capabilities.

9. **Evolve or unstuck when needed.**
   - If verification fails because the Seed is wrong, invoke `evolution-loop`.
   - If progress is stagnant, invoke `unstuck` or `evolution-loop` rather than repeating the same approach.
   - Do not retry no-progress by default. Pause and run `red-team`; allow one retry only if red-team approves a clear, local, evidence-backed retry exception.

10. **Report outcome.**
   - Summarize final status, evidence, unresolved risks, and next goal if applicable.

Rules:

- Be critical, not flattering.
- Preserve the user's fit profile: high autonomy, direct progress, evidence-first verification, and questions only when they change execution.
- Do not let worker agents own the goal ledger or final completion decision.
