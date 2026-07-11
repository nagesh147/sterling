# Workflows

## Feature
1. Branch: `feat/<short-name>`
2. Plan in Claude → approve
3. Implement (prefer fresh session after plan)
4. Tests for touched area
5. PR small; leave context headroom (don’t drive one chat forever)

## Bugfix
1. Branch: `fix/<short-name>`
2. Skills: investigate-bug / systematic-debugging (1–2)
3. code-review-graph for impact
4. Fix + verify
5. Small PR

## Architecture pass
1. TrueCourse (deterministic first)
2. Critical/High only unless doing a cleanup epic
3. code-review-graph before structural edits
