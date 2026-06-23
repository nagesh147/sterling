# Visual Regression & Baseline "Bot" Notes

## Updating snapshots (baseline "bot" workflow)
- Local: `npm run e2e:update-snapshots` (or `npx playwright test --update-snapshots`)
- Review diffs in report.
- For CI "bot": use PR label `update-snapshots` or manually dispatch workflow that runs with -u and pushes (or just commit the updated pngs from local run).
- Webkit uses looser thresholds (see playwright.config.ts per-project expect for webkit).

## Why webkit overrides
- Fonts, subpixel rendering, animation timing differ on webkit/Safari.
- Higher maxDiffPixels / threshold for webkit project only.
- Timeouts increased to avoid flakes.

## Red count / ratchet e2e coverage
See bars-risk-unified.spec.ts and hybrid-picker for UI bars + exit labels.
Backend: test_common_trailing.py + kite engine tests simulate progressive red 0->1->2->3 + ratchet + paper_store integration + monitor flows (update red via paper_store, exit decision).

Run full:
- pytest ...test_common_trailing...
- npx playwright test --project=webkit

This is "yet another round" of coverage for monitor red-count flows + paper_store + webkit quirks + baseline tooling.
