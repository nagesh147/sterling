export const OPENING_VOLUME_LEADERS_CSS = `
@keyframes ovl-spin { to { transform: rotate(360deg); } }
@keyframes ovl-card-in { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
.ovl-root { min-height:100%; background:var(--k-surface-2); color:var(--k-text); font-family:var(--k-font, Inter, system-ui, sans-serif); }
.ovl-shell { width:100%; max-width:1500px; margin:0 auto; padding:18px clamp(12px,2vw,26px) 34px; box-sizing:border-box; }
.ovl-header { display:flex; align-items:flex-start; justify-content:space-between; gap:18px; margin-bottom:14px; }
.ovl-eyebrow { margin:0 0 5px; color:var(--k-brand); font-size:9px; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }
.ovl-title { margin:0; font-size:22px; line-height:1.1; letter-spacing:-.025em; font-weight:750; }
.ovl-subtitle { max-width:720px; margin:7px 0 0; color:var(--k-ink-5); font-size:11px; line-height:1.55; }
.ovl-advisory { display:inline-flex; align-items:center; gap:6px; flex-shrink:0; padding:6px 9px; border:1px solid color-mix(in srgb,var(--k-amber) 35%,var(--k-border)); border-radius:6px; color:var(--k-amber); background:color-mix(in srgb,var(--k-amber) 7%,var(--k-bg)); font-size:9px; font-weight:750; letter-spacing:.06em; text-transform:uppercase; }
.ovl-advisory i { width:6px; height:6px; border-radius:50%; background:currentColor; }
.ovl-panel { border:1px solid var(--k-border); border-radius:9px; background:var(--k-bg); box-shadow:0 1px 2px rgba(0,0,0,.025); }
.ovl-toolbar { display:flex; align-items:end; flex-wrap:wrap; gap:12px; padding:13px 14px; }
.ovl-control { display:grid; gap:5px; }
.ovl-control > span, .ovl-filter-label { color:var(--k-ink-6); font-size:8.5px; font-weight:750; letter-spacing:.08em; text-transform:uppercase; }
.ovl-segment { display:inline-flex; align-items:center; padding:2px; border:1px solid var(--k-border); border-radius:6px; background:var(--k-surface-2); }
.ovl-segment button { height:27px; padding:0 10px; border:0; border-radius:4px; color:var(--k-ink-4); background:transparent; cursor:pointer; font-family:inherit; font-size:10.5px; font-weight:600; line-height:1; }
.ovl-segment button[data-on="true"] { color:var(--k-brand-deep); background:var(--k-bg); box-shadow:0 1px 3px rgba(0,0,0,.08); }
.ovl-select,.ovl-input { height:32px; box-sizing:border-box; border:1px solid var(--k-border); border-radius:6px; outline:none; background:var(--k-bg); color:var(--k-text); font-family:inherit; font-size:11px; font-weight:500; line-height:1; }
.ovl-select { min-width:94px; padding:0 28px 0 9px; }
.ovl-input { min-width:210px; padding:0 10px; }
.ovl-input:focus,.ovl-select:focus { border-color:var(--k-border-brand); box-shadow:0 0 0 2px color-mix(in srgb,var(--k-brand) 12%,transparent); }
.ovl-check { height:32px; display:inline-flex; align-items:center; gap:7px; color:var(--k-ink-3); font-size:10.5px; cursor:pointer; }
.ovl-check input { accent-color:var(--k-brand); }
.ovl-scan { height:32px; margin-left:auto; padding:0 14px; display:inline-flex; align-items:center; justify-content:center; gap:7px; border:1px solid var(--k-brand); border-radius:6px; background:var(--k-brand); color:var(--k-on-accent); cursor:pointer; font-family:inherit; font-size:10.5px; font-weight:700; line-height:1; box-shadow:0 2px 6px color-mix(in srgb,var(--k-brand) 20%,transparent); }
.ovl-scan:hover:not(:disabled) { filter:brightness(.96); transform:translateY(-1px); }
.ovl-scan:disabled { opacity:.55; cursor:wait; }
.ovl-spinner { width:11px; height:11px; border:2px solid currentColor; border-right-color:transparent; border-radius:50%; animation:ovl-spin .75s linear infinite; }
.ovl-scope-input { padding:0 14px 13px; }
.ovl-secondary-controls { display:flex; align-items:end; flex-wrap:wrap; gap:12px; border-top:1px solid var(--k-border); padding-top:11px; }
.ovl-secondary-controls > small { align-self:center; color:var(--k-faint); font-size:8.5px; }
.ovl-form-error { margin:0 14px 12px; padding:8px 10px; border:1px solid color-mix(in srgb,var(--k-red) 25%,var(--k-border)); border-radius:6px; color:var(--k-red); background:color-mix(in srgb,var(--k-red) 5%,var(--k-bg)); font-size:10.5px; }
.ovl-contract { margin-top:8px; display:flex; align-items:center; gap:8px; flex-wrap:wrap; color:var(--k-ink-6); font-size:9.5px; }
.ovl-contract strong { color:var(--k-ink-3); font-weight:650; }
.ovl-contract span+span::before { content:'·'; margin-right:8px; color:var(--k-faint); }
.ovl-stats { margin-top:12px; display:grid; grid-template-columns:repeat(5,minmax(95px,1fr)); overflow:hidden; }
.ovl-stat { min-width:0; padding:11px 13px; border-right:1px solid var(--k-border); }
.ovl-stat:last-child { border-right:0; }
.ovl-stat span { display:block; color:var(--k-ink-6); font-size:8.5px; font-weight:750; letter-spacing:.07em; text-transform:uppercase; }
.ovl-stat strong { display:block; margin-top:4px; font-size:16px; line-height:1; font-variant-numeric:tabular-nums; }
.ovl-stat small { display:block; margin-top:5px; overflow:hidden; color:var(--k-faint); font-size:9px; text-overflow:ellipsis; white-space:nowrap; }
.ovl-progress { margin-top:12px; padding:24px; display:grid; place-items:center; gap:9px; text-align:center; }
.ovl-progress .ovl-spinner { width:18px; height:18px; color:var(--k-brand); }
.ovl-progress strong { font-size:12px; }
.ovl-progress p { max-width:500px; margin:0; color:var(--k-ink-6); font-size:10px; line-height:1.5; }
.ovl-error { margin-top:12px; padding:13px 14px; border-color:color-mix(in srgb,var(--k-red) 28%,var(--k-border)); color:var(--k-red); font-size:11px; line-height:1.45; }
.ovl-empty { margin-top:12px; padding:34px 20px; text-align:center; }
.ovl-empty-icon { width:40px; height:40px; margin:0 auto 11px; display:grid; place-items:center; border-radius:50%; color:var(--k-brand); background:color-mix(in srgb,var(--k-brand) 8%,transparent); }
.ovl-empty h2 { margin:0; font-size:13px; }
.ovl-empty p { max-width:570px; margin:7px auto 0; color:var(--k-ink-6); font-size:10.5px; line-height:1.55; }
.ovl-results { margin-top:14px; }
.ovl-results-head { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:10px; }
.ovl-results-head h2 { margin:0; font-size:13px; letter-spacing:-.01em; }
.ovl-results-head small { color:var(--k-faint); font-size:9.5px; }
.ovl-results-head .ovl-input { min-width:150px; width:180px; height:29px; margin-left:auto; }
.ovl-filter-pills { display:inline-flex; gap:4px; }
.ovl-filter-pills button { height:25px; padding:0 8px; border:1px solid var(--k-border); border-radius:5px; background:var(--k-bg); color:var(--k-ink-5); cursor:pointer; font-family:inherit; font-size:9px; font-weight:650; line-height:1; }
.ovl-filter-pills button[data-on="true"] { border-color:color-mix(in srgb,var(--k-brand) 45%,var(--k-border)); color:var(--k-brand-deep); background:color-mix(in srgb,var(--k-brand) 7%,var(--k-bg)); }
.ovl-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(min(300px,100%),1fr)); gap:9px; }
.ovl-card { position:relative; overflow:hidden; animation:ovl-card-in .18s ease both; }
.ovl-card::before { content:''; position:absolute; inset:0 auto 0 0; width:3px; background:var(--ovl-side); }
.ovl-card[data-direction="UP"] { --ovl-side:var(--k-green); }
.ovl-card[data-direction="DOWN"] { --ovl-side:var(--k-red); }
.ovl-card[data-direction="NEUTRAL"] { --ovl-side:var(--k-faint); }
.ovl-card-top { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:10px; padding:12px 13px 9px 15px; }
.ovl-rank { margin-right:6px; color:var(--k-faint); font-size:9px; font-variant-numeric:tabular-nums; }
.ovl-symbol { margin:0; overflow:hidden; font-size:14px; font-weight:760; letter-spacing:.01em; text-overflow:ellipsis; white-space:nowrap; }
.ovl-direction { display:inline-flex; align-items:center; gap:4px; margin-top:5px; color:var(--ovl-side); font-size:9px; font-weight:800; letter-spacing:.06em; }
.ovl-rvol { text-align:right; }
.ovl-rvol strong { display:block; color:var(--ovl-side); font-size:20px; line-height:1; font-variant-numeric:tabular-nums; }
.ovl-rvol span { display:block; margin-top:4px; color:var(--k-faint); font-size:8px; font-weight:750; letter-spacing:.08em; }
.ovl-badges { min-height:21px; padding:0 13px 8px 15px; display:flex; flex-wrap:wrap; gap:5px; }
.ovl-badge { display:inline-flex; align-items:center; min-height:18px; padding:0 6px; border:1px solid var(--k-border); border-radius:4px; color:var(--k-ink-5); background:var(--k-surface-2); font-size:8px; font-weight:750; letter-spacing:.045em; text-transform:uppercase; }
.ovl-badge[data-tier="explosive"] { color:#b93822; border-color:color-mix(in srgb,#ef6a4b 32%,var(--k-border)); background:color-mix(in srgb,#ef6a4b 8%,var(--k-bg)); }
.ovl-badge[data-tier="strong"] { color:#9b6711; border-color:color-mix(in srgb,var(--k-amber) 32%,var(--k-border)); background:color-mix(in srgb,var(--k-amber) 8%,var(--k-bg)); }
.ovl-badge[data-tier="spurt"] { color:var(--k-blue); border-color:color-mix(in srgb,var(--k-blue) 30%,var(--k-border)); background:color-mix(in srgb,var(--k-blue) 7%,var(--k-bg)); }
.ovl-badge[data-tier="watch"] { color:var(--k-purple); border-color:color-mix(in srgb,var(--k-purple) 30%,var(--k-border)); background:color-mix(in srgb,var(--k-purple) 7%,var(--k-bg)); }
.ovl-badge[data-combo="true"] { color:var(--k-green); border-color:color-mix(in srgb,var(--k-green) 32%,var(--k-border)); background:color-mix(in srgb,var(--k-green) 7%,var(--k-bg)); }
.ovl-badge[data-gate="blocked"],.ovl-badge[data-warning="true"] { color:var(--k-red); border-color:color-mix(in srgb,var(--k-red) 30%,var(--k-border)); background:color-mix(in srgb,var(--k-red) 6%,var(--k-bg)); }
.ovl-badge[data-gate="caution"] { color:var(--k-amber); border-color:color-mix(in srgb,var(--k-amber) 32%,var(--k-border)); background:color-mix(in srgb,var(--k-amber) 7%,var(--k-bg)); }
.ovl-badge[data-gate="passes_known_gates"] { color:var(--k-green); border-color:color-mix(in srgb,var(--k-green) 32%,var(--k-border)); background:color-mix(in srgb,var(--k-green) 7%,var(--k-bg)); }
.ovl-tape { display:grid; grid-template-columns:repeat(3,1fr); border-top:1px solid var(--k-border); border-bottom:1px solid var(--k-border); background:var(--k-surface-2); }
.ovl-tape div { min-width:0; padding:8px 9px; border-right:1px solid var(--k-border); }
.ovl-tape div:last-child { border-right:0; }
.ovl-tape span { display:block; color:var(--k-faint); font-size:7.5px; font-weight:750; letter-spacing:.06em; text-transform:uppercase; }
.ovl-tape strong { display:block; margin-top:3px; overflow:hidden; font-size:10.5px; font-weight:650; font-variant-numeric:tabular-nums; text-overflow:ellipsis; white-space:nowrap; }
.ovl-tape strong[data-tone="up"] { color:var(--k-green); }
.ovl-tape strong[data-tone="down"] { color:var(--k-red); }
.ovl-evidence { padding:9px 13px 10px 15px; display:grid; gap:7px; }
.ovl-event { display:grid; grid-template-columns:58px minmax(0,1fr); align-items:start; gap:7px; font-size:9.5px; line-height:1.4; }
.ovl-event > span { color:var(--k-faint); font-size:8px; font-weight:750; letter-spacing:.06em; text-transform:uppercase; }
.ovl-event strong { color:var(--k-ink-3); font-weight:600; }
.ovl-event em { color:var(--k-faint); font-style:normal; }
.ovl-card-foot { min-height:29px; padding:7px 12px 7px 15px; display:flex; align-items:center; flex-wrap:wrap; gap:6px; border-top:1px solid var(--k-border); }
.ovl-state { display:inline-flex; align-items:center; gap:5px; color:var(--k-ink-5); font-size:8.5px; font-weight:700; text-transform:capitalize; }
.ovl-state i { width:6px; height:6px; border-radius:50%; background:var(--k-faint); }
.ovl-state[data-state="pass"] { color:var(--k-green); }
.ovl-state[data-state="pass"] i { background:var(--k-green); }
.ovl-state[data-state="fail"] { color:var(--k-red); }
.ovl-state[data-state="fail"] i { background:var(--k-red); }
.ovl-quality { margin-left:auto; color:var(--k-ink-6); font-size:8.5px; text-transform:capitalize; }
.ovl-chart { height:23px; padding:0 7px; border:1px solid var(--k-border); border-radius:4px; background:transparent; color:var(--k-ink-4); cursor:pointer; font-family:inherit; font-size:8.5px; font-weight:650; line-height:1; }
.ovl-chart:hover { color:var(--k-brand); border-color:var(--k-border-brand); }
.ovl-details { border-top:1px solid var(--k-border); }
.ovl-details summary { padding:7px 12px 7px 15px; color:var(--k-ink-6); cursor:pointer; font-size:8.5px; font-weight:650; list-style:none; }
.ovl-details summary::-webkit-details-marker { display:none; }
.ovl-details summary::after { content:'+'; float:right; }
.ovl-details[open] summary::after { content:'−'; }
.ovl-detail-grid { padding:0 12px 10px 15px; display:grid; grid-template-columns:repeat(3,1fr); gap:7px; }
.ovl-detail-grid div { min-width:0; }
.ovl-detail-grid span { display:block; color:var(--k-faint); font-size:7.5px; text-transform:uppercase; }
.ovl-detail-grid strong { display:block; margin-top:2px; overflow:hidden; color:var(--k-ink-3); font-size:9px; font-weight:600; font-variant-numeric:tabular-nums; text-overflow:ellipsis; white-space:nowrap; }
.ovl-reason { grid-column:1/-1; padding:6px 7px; border-radius:4px; color:var(--k-ink-5); background:var(--k-surface-2); font-size:8.5px; line-height:1.4; }
.ovl-breadth { margin-top:9px; padding:10px 13px; display:grid; grid-template-columns:120px minmax(220px,1fr) auto; align-items:center; gap:14px; border-left:3px solid var(--k-faint); }
.ovl-breadth[data-mood="bullish"] { border-left-color:var(--k-green); }
.ovl-breadth[data-mood="bearish"] { border-left-color:var(--k-red); }
.ovl-breadth span { display:block; color:var(--k-faint); font-size:7.5px; font-weight:750; text-transform:uppercase; }
.ovl-breadth strong { display:block; margin-top:2px; font-size:12px; }
.ovl-breadth p,.ovl-breadth small { margin:0; color:var(--k-ink-6); font-size:9px; line-height:1.45; }
.ovl-breadth small { color:var(--k-faint); text-align:right; }
.ovl-gates { padding:0 12px 8px 15px; display:grid; gap:4px; }
.ovl-gates p { margin:0; padding:5px 7px; border-radius:4px; font-size:8.5px; line-height:1.35; }
.ovl-gates p[data-kind="block"] { color:var(--k-red); background:color-mix(in srgb,var(--k-red) 6%,var(--k-bg)); }
.ovl-gates p[data-kind="caution"] { color:var(--k-amber); background:color-mix(in srgb,var(--k-amber) 7%,var(--k-bg)); }
.ovl-plan { margin:0 12px 10px 15px; padding:9px; border:1px solid var(--k-border); border-radius:6px; background:var(--k-surface-2); }
.ovl-plan-head { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:8px; font-size:9px; }
.ovl-plan-head span { color:var(--k-ink-6); }
.ovl-plan .ovl-detail-grid { padding:0; }
.ovl-plan > p { margin:8px 0 0; color:var(--k-ink-6); font-size:8px; line-height:1.45; }
.ovl-option { margin-top:9px; padding-top:8px; display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; border-top:1px solid var(--k-border); }
.ovl-option span,.ovl-option small { display:block; color:var(--k-faint); font-size:7.5px; }
.ovl-option strong { display:block; margin:2px 0; font-size:9px; }
.ovl-option > p { grid-column:1/-1; margin:0; color:var(--k-amber); font-size:8px; }
.ovl-private { margin:0; padding:0 12px 10px 15px; color:var(--k-faint); font-size:8px; line-height:1.45; }
.ovl-failures { margin-top:12px; }
.ovl-failures summary { padding:10px 12px; cursor:pointer; color:var(--k-ink-5); font-size:10px; font-weight:650; }
.ovl-failure-list { max-height:190px; overflow:auto; border-top:1px solid var(--k-border); }
.ovl-failure { padding:7px 12px; display:grid; grid-template-columns:100px 1fr; gap:10px; border-bottom:1px solid var(--k-border); color:var(--k-ink-6); font-size:9px; }
.ovl-failure:last-child { border-bottom:0; }
.ovl-failure strong { color:var(--k-ink-3); }
@media (max-width:760px) {
  .ovl-shell { padding-top:13px; }
  .ovl-header { display:block; }
  .ovl-advisory { margin-top:10px; }
  .ovl-toolbar { align-items:stretch; }
  .ovl-control { flex:1 1 120px; }
  .ovl-input { min-width:0; width:100%; }
  .ovl-scan { width:100%; margin-left:0; }
  .ovl-stats { grid-template-columns:repeat(2,1fr); }
  .ovl-stat { border-bottom:1px solid var(--k-border); }
  .ovl-stat:nth-child(2n) { border-right:0; }
  .ovl-stat:last-child { grid-column:1/-1; border-bottom:0; }
  .ovl-results-head .ovl-input { width:100%; margin-left:0; }
  .ovl-breadth { grid-template-columns:1fr; gap:5px; }
  .ovl-breadth small { text-align:left; }
  .ovl-option { grid-template-columns:1fr; }
}
@media (prefers-reduced-motion:reduce) { .ovl-spinner,.ovl-card { animation:none; } }
`;
