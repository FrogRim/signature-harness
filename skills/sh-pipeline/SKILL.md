---
name: sh-pipeline
description: Deprecated Signature Harness compatibility wrapper. Prefer $sh-goal or /sh for all new work.
---

# Signature Harness Compatibility Wrapper

The old SH pipeline was:

```text
research -> spec -> plan -> implement -> review
```

Do not run that as a mandatory sequence. Treat it as one possible `build` loop shape inside the newer goal-loop runtime.

When this skill triggers:

1. Invoke or follow `goal-loop`.
2. Normalize the request into the SH goal schema.
3. Choose the smallest fitting loop.
4. Use the old five-stage sequence only if the goal truly needs research, spec approval, plan approval, implementation, and review as separate gates.
5. Always preserve the new gates:
   - red-team pressure before broad/high-risk execution
   - oracle verification before completion

If the user explicitly asks for the old fixed pipeline, explain that SH now treats it as a routed loop, then proceed with the routed goal contract.
