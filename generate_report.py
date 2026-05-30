import asyncio
import httpx
import pandas as pd

symbols = ['BTCUSD', 'ETHUSD', 'SOLUSD']
timeframes = ['1m', '5m', '15m', '30m', '1h', '4h']
strategies = [
    {'id': 'mean_reversion', 'name': 'Sterling: Mean Reversion (RSI)'},
    {'id': 'ma_crossover', 'name': 'Sterling: MA Crossover (9/21)'},
    {'id': 'breakout', 'name': 'Sterling: 20-Period Breakout'},
    {'id': 'price_action', 'name': 'Sterling: Price Action (Engulfing)'},
    {'id': 'smc', 'name': 'Sterling: Smart Money Concepts (FVG)'},
    {'id': 'supertrend', 'name': 'Community: SuperTrend Scalp'},
    {'id': 'bollinger', 'name': 'Community: Bollinger Bands Breakout'},
    {'id': 'ict', 'name': 'Community: ICT Silver Bullet'},
    {'id': 'supply_demand', 'name': 'Community: 1H Supply/Demand'}
]
profiles = ['Intraday', 'Scalping', 'Aggressive']

async def fetch(client, sym, tf, strat, prof):
    try:
        resp = await client.post('http://127.0.0.1:8000/api/v1/vectorized/run', json={
            "symbol": sym,
            "timeframe": tf,
            "strategy": strat['id'],
            "profile": prof,
            "starting_capital": 500.0
        }, timeout=30.0)
        data = resp.json()
        if "metrics" in data:
            return {
                "symbol": sym,
                "tf": tf,
                "strategy": strat['name'],
                "profile": prof,
                "win_rate": data["metrics"]["Win Rate"],
                "profit_factor": data["metrics"]["PF"],
                "expectancy": data["metrics"]["Sharpe"], # using sharpe as expectancy proxy
                "net_return": data["metrics"]["End Capital"] - 500.0,
                "end_capital": data["metrics"]["End Capital"]
            }
    except Exception as e:
        pass
    return None

async def main():
    async with httpx.AsyncClient() as client:
        tasks = []
        for sym in symbols:
            for tf in timeframes:
                for strat in strategies:
                    for prof in profiles:
                        tasks.append(fetch(client, sym, tf, strat, prof))
        
        results = await asyncio.gather(*tasks)
        
        valid_results = [r for r in results if r]
        
        if not valid_results:
            print("No valid results. Is the backend running?")
            return
            
        df = pd.DataFrame(valid_results)
        
        # Sort by Net Return to find the best
        df = df.sort_values(by="net_return", ascending=False).head(20)
        
        print(f"{'Strategy Configuration':<55} | {'Profile':<12} | {'Win Rate':<10} | {'Profit Fac':<10} | {'Expectancy':<10} | {'Net Return':<15} | {'End Capital':<15}")
        print("-" * 140)
        for _, row in df.iterrows():
            config = f"{row['strategy']} ({row['symbol']} {row['tf']})"
            print(f"{config:<55} | {row['profile']:<12} | {row['win_rate']*100:>8.2f}% | {row['profit_factor']:>10.2f} | {row['expectancy']:>10.2f} | ${row['net_return']:>13.2f} | ${row['end_capital']:>13.2f}")

if __name__ == '__main__':
    asyncio.run(main())
