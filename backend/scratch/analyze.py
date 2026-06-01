import pandas as pd

df = pd.read_csv('deriv_fut_opt_results.csv')
valid = df[df['fut_trades'] >= 30]

# More realistic constraints
realistic = valid[(valid['opt_dte'] >= 7) & (valid['opt_alloc'] <= 0.10) & (valid['opt_spread'] >= 0.03)]

safe = realistic[(realistic['opt_pf'] > 1.2) & (realistic['fut_pf'] > 1.2)]
best_safe = safe.sort_values('opt_end_capital', ascending=False).head(1)

if len(best_safe) > 0:
    r = best_safe.iloc[0]
    print(f"Absolute Best Realistic/Balanced Config:")
    print(f"Asset: {r.symbol}, Timeframe: {r.tf}, Strategy: {r.strategy}, Profile: {r.profile}")
    print(f"Options Setup: DTE {r.opt_dte}, Premium Alloc {r.opt_alloc*100}%, Assumed Spread {r.opt_spread*100}%")
    print(f"Futures Setup: Fee {r.fut_fee*100}%")
    print(f"Options Metrics: WinRate {r.opt_win_rate*100:.1f}%, PF {r.opt_pf:.2f}, End Cap ${r.opt_end_capital:.0f}, Ret {r.opt_net_return*100:.1f}%")
    print(f"Futures Metrics: WinRate {r.fut_win_rate*100:.1f}%, PF {r.fut_pf:.2f}, End Cap ${r.fut_end_capital:.0f}, Ret {r.fut_net_return*100:.1f}%")

print("\n--- Top 3 Options Strategies Overall (Realistic Constraints) ---")
best_opt = realistic.sort_values('opt_end_capital', ascending=False).head(3)
for i, r in best_opt.iterrows():
    print(f"{r.symbol} {r.tf} {r.strategy} {r.profile} | DTE:{r.opt_dte} Spread:{r.opt_spread} Alloc:{r.opt_alloc} | PF:{r.opt_pf:.2f} End:${r.opt_end_capital:.0f}")

print("\n--- Top 3 Futures Strategies Overall (Any Config) ---")
best_fut = valid.sort_values('fut_end_capital', ascending=False).head(3)
for i, r in best_fut.iterrows():
    print(f"{r.symbol} {r.tf} {r.strategy} {r.profile} | Fee:{r.fut_fee} | PF:{r.fut_pf:.2f} End:${r.fut_end_capital:.0f}")

