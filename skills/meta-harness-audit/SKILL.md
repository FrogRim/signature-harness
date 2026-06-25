---
name: meta-harness-audit
description: Use when explicitly asked to audit Signature Harness agents/skills/commands/manifests architecture, detect role drift or overlap, and produce an evidence-backed Architecture Candidate. Do not use for ordinary coding tasks.
---

# Meta-Harness Audit

Audit Signature Harness itself as a source-of-record harness. This skill adapts
the useful design-time audit idea from meta harness factories while preserving
SH's portable, candidate-first contract.

## Boundary

Read source-of-record surfaces:

- `agents/`
- `skills/`
- `commands/`
- `.claude-plugin/`
- `.codex-plugin/`
- `README.md`
- `AGENTS.md`
- relevant `templates/`, `schemas/`, and `scripts/`

Do not inspect host-local install outputs as the source of truth:

- `.claude/`
- `.codex/`
- user home skill folders

Do not create or apply scaffolds. This skill produces candidates only.

## Audit Questions

1. Which agents and skills have overlapping responsibilities?
2. Which roles exist as skills but not agents, or agents but not skills?
3. Which skills are too broad, stale, or no longer routed by the goal loop?
4. Which public/direct/internal tier claims in README or AGENTS drift from the actual descriptions?
5. Which architecture change would improve SH while preserving Codex/Claude portability?
6. Which changes would introduce Claude-only Agent Teams dependency or direct `.claude/*` drift?

## Method

1. Read the current repo-local source-of-record surfaces before judging.
2. Build a compact map:
   - agents
   - skills
   - commands
   - manifests
   - public/direct/internal tier claims
3. Identify overlaps, missing roles, stale surfaces, and host-specific coupling.
4. Reject any proposed change that directly targets `.claude/agents/`, `.claude/skills/`, `.codex/agents/`, or `.codex/skills/`.
5. Create an Architecture Candidate using `templates/ARCHITECTURE_CANDIDATE.md`.
6. Persist the machine-readable JSON sidecar when possible.
7. Validate with:

```powershell
py -3 scripts/sh_runtime.py validate-architecture-candidate --candidate <candidate.json> --root .
```

## Output

Return an Architecture Candidate summary with:

- evidence path and optional line number
- proposed add/merge/delete/update/split/prune/keep action
- Codex compatibility
- Claude compatibility
- Agent Teams dependency: `none` or `optional`
- verification commands
- residual risks

The candidate is not approved merely because it is plausible. It must still pass
Oracle/release gates before any source file changes are applied.
