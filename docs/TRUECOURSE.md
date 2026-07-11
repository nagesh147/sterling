# TrueCourse rule policy (Sterling)

Noise and intentional-pattern rules are **disabled per-repo** in
`.truecourse/config.json` so the dashboard surfaces correctness/security
work, not style volume.

## Still enabled (examples)
- security/* (secrets, injection, etc.)
- bugs with real runtime impact (undefined-name, bare-except, raise-without-from, …)
- architecture unused-import / duplicate-import when enabled

## Disabled intentionally (high volume / structural)
- import-outside-top-level — FastAPI lazy imports avoid circular deps
- getattr-with-constant — optional `app.state` attributes
- cyclomatic/cognitive/god-module/long-method — tracked via architecture strangler, not auto-fix
- docstring / missing-type-hints / no-explicit-any — gradual typing debt
- JSX inline-object/function props — React perf nits, bulk rewrite risky
- try-except-pass / suppressible-exception — many best-effort paths; prefer log.debug when changing

Re-enable a rule: `truecourse rules enable <ruleKey>` then re-analyze.
