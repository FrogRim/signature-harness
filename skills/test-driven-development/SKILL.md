---
name: test-driven-development
description: This skill should be used when implementing a feature or fix. It follows the RED-GREEN-REFACTOR cycle so behavior is pinned by tests before code is written.
---
# Test-Driven Development

## RED -> GREEN -> REFACTOR
1. **RED** - write a test that captures the desired behavior and watch it fail.
2. **GREEN** - write the minimum code to make it pass.
3. **REFACTOR** - clean up with the test still green.

## Per stack (adjust to the project)
- Python: `pytest`
- C++: your test runner (e.g. ctest / GoogleTest)
- Web: your runner (e.g. vitest / jest)

Do not write production code that has no failing test driving it. Test the behavior the spec requires, not implementation details.
