---
name: red-team
description: Internal Signature Harness adversarial-review module. Invoked by goal-loop or orchestration routing, not directly by general user requests.
---

# Red Team

Be adversarial, not hostile. The goal is to protect truth, scope, safety, and completion quality.

## Inputs

- goal schema or user request
- plan, implementation, or completion claim
- available evidence
- user-fit profile

## Attack Surfaces

Check for:

- sycophancy: accepting the user's premise too easily
- optimism bias: assuming success without proof
- hidden assumptions
- missing non-goals
- vague or unverifiable success criteria
- weak tests or missing regression coverage
- scope drift
- Seed drift or unreviewed Seed mutation
- unsafe, destructive, or irreversible branches
- evidence that does not prove the claim
- ignored alternatives that would materially reduce risk
- no-progress disguised as persistence
- retry requests after stagnation without a new evidence-backed reason

## Method

1. Restate the claim being tested.
2. Identify the strongest reason the claim may be false.
3. Check the evidence, not the confidence.
4. Separate blocking issues from warnings.
5. For no-progress or retry requests, decide whether the next route should be active-slice shrink, `evolution-loop`, `unstuck`, abort, or one approved retry exception.
6. Produce a verdict:
   - `PASS` - no blocking issue
   - `WARN` - proceed only with stated residual risk
   - `BLOCK` - do not execute or complete until fixed

## Output

```md
# Red Team - <goal>

Verdict: PASS | WARN | BLOCK

## Claim Tested
<plan or completion claim>

## Findings
- [severity] <issue> - evidence/gap:

## Sycophancy / Optimism Check
- <where the agent over-agreed, over-promised, or under-challenged>

## Seed / Drift Check
- <whether the active Seed still matches the claim>

## Required Fixes
- <only for BLOCK>

## Routing Pressure
- no_progress: yes | no
- retry_exception_approved: yes | no
- recommended_route: continue | narrow-active-slice | evolution-loop | unstuck | abort | retry-once

## Residual Risks
- <only for WARN/PASS when relevant>
```

Do not nitpick style. Raise only issues that can change execution, correctness, safety, or completion.
