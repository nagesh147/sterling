"""Curated stock registry for the Sterling Kite Engine scan.

Each entry maps a stock name (equity tradingsymbol) to its liquidity tier and
metadata. Only these stocks are exposed in the UI's quick-pick chip selector.
Users can still add arbitrary F&O stocks via the free-form input, or use "All
F&O" to scan the full universe.
"""
from __future__ import annotations

from typing import List, Literal

LiquidityLevel = Literal["Very High", "High", "Moderate", "Good", "Moderate-Good"]


class StockEntry:
    def __init__(
        self,
        name: str,
        label: str,
        liquidity: LiquidityLevel,
        volatility: str,
        indices: str,
        why: str,
    ) -> None:
        self.name = name
        self.label = label
        self.liquidity = liquidity
        self.volatility = volatility
        self.indices = indices
        self.why = why

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "liquidity": self.liquidity,
            "volatility": self.volatility,
            "indices": self.indices,
            "why": self.why,
        }


OPTIONAL_STOCKS: List[StockEntry] = [
    StockEntry("BAJAJFINSV", "Bajaj Finserv", "High", "High", "Finnifty, Nifty", "Strong financial holding company moves"),
    StockEntry("ADANIPORTS", "Adani Ports", "High", "High", "Nifty, Sensex", "Logistics/infra volatility"),
    StockEntry("JSWSTEEL", "JSW Steel", "Good", "Very High", "Nifty", "Metal sector swings"),
    StockEntry("TATASTEEL", "Tata Steel", "Good", "High", "Nifty, Sensex", "Commodity price sensitivity"),
    StockEntry("HINDALCO", "Hindalco", "Good", "High", "Nifty", "Metals & aluminium plays"),
    StockEntry("GRASIM", "Grasim", "Good", "Moderate-High", "Nifty", "Diversified (cement + textiles)"),
    StockEntry("ULTRACEMCO", "UltraTech Cement", "Good", "Moderate-High", "Nifty, Sensex", "Cement demand news"),
    StockEntry("EICHERMOT", "Eicher Motors", "Good", "High", "Nifty", "Auto (Royal Enfield) volatility"),
    StockEntry("MARUTI", "Maruti Suzuki", "Good", "Moderate-High", "Nifty", "Auto sector leader"),
    StockEntry("TITAN", "Titan", "Good", "Moderate-High", "Nifty, Sensex", "Consumer discretionary/jewellery"),
    StockEntry("ASIANPAINT", "Asian Paints", "Good", "Moderate-High", "Nifty, Sensex", "Paint/consumer cyclical"),
    StockEntry("NESTLEIND", "Nestlé India", "Good", "Moderate", "Nifty", "FMCG defensive with event spikes"),
    StockEntry("ITC", "ITC", "Good", "Moderate", "Nifty, Sensex", "Diversified FMCG + hotels"),
    StockEntry("HCLTECH", "HCL Tech", "Good", "Moderate-High", "Nifty, Sensex", "IT sector alternative to Infosys"),
    StockEntry("TECHM", "Tech Mahindra", "Good", "Moderate-High", "Nifty", "IT + telecom exposure"),
    StockEntry("WIPRO", "Wipro", "Good", "Moderate", "Nifty", "IT services"),
    StockEntry("NTPC", "NTPC", "Good", "Moderate-High", "Nifty, Sensex", "Power sector PSU"),
    StockEntry("POWERGRID", "Power Grid", "Good", "Moderate", "Nifty", "Power transmission stability + spikes"),
    StockEntry("COALINDIA", "Coal India", "Good", "Moderate-High", "Nifty", "Coal & energy plays"),
    StockEntry("ONGC", "ONGC", "Good", "High", "Nifty", "Oil & gas exploration"),
]

STOCK_REGISTRY: List[StockEntry] = [
    StockEntry("HDFCBANK", "HDFC Bank", "Very High", "Moderate", "Nifty, Bank Nifty, Finnifty", "Highest banking liquidity, tight spreads"),
    StockEntry("ICICIBANK", "ICICI Bank", "Very High", "Moderate-High", "All", "Excellent volume & movement"),
    StockEntry("SBIN", "SBI", "Very High", "High", "All", "Very high volume, news-sensitive"),
    StockEntry("RELIANCE", "Reliance", "Very High", "Moderate", "Nifty, Sensex", "Massive liquidity, stable premiums"),
    StockEntry("BHARTIARTL", "Bharti Airtel", "High", "High", "Nifty, Sensex", "Strong volatility on sector news"),
    StockEntry("AXISBANK", "Axis Bank", "High", "Moderate-High", "Bank Nifty, Finnifty", "Good banking exposure"),
    StockEntry("KOTAKBANK", "Kotak Mahindra", "High", "Moderate", "Bank Nifty, Finnifty", "Decent premiums"),
    StockEntry("INFY", "Infosys", "High", "Moderate-High", "Nifty, Sensex", "IT sector moves, good for events"),
    StockEntry("BAJFINANCE", "Bajaj Finance", "High", "Very High", "Finnifty, Nifty", "High volatility NBFC"),
    StockEntry("ADANIENT", "Adani Enterprises", "High", "Very High", "Nifty, Sensex", "Sharp moves, high premiums"),
    StockEntry("LT", "L&T", "High", "Moderate-High", "Nifty, Sensex", "Infrastructure plays, steady with spikes"),
    StockEntry("TCS", "TCS", "High", "Moderate", "Nifty, Sensex", "Stable IT giant"),
    StockEntry("INDUSINDBK", "IndusInd Bank", "Good", "High", "Bank Nifty", "Higher volatility among banks"),
    StockEntry("SHRIRAMFIN", "Shriram Finance", "Good", "High", "Finnifty", "Strong NBFC movement"),
    StockEntry("HDFCLIFE", "HDFC Life", "Good", "Moderate-High", "Finnifty, Nifty", "Insurance sector volatility"),
    StockEntry("JIOFIN", "Jio Financial", "Good", "High", "Finnifty, Nifty", "Newer but growing activity"),
    StockEntry("MARUTI", "Maruti Suzuki", "Good", "Moderate-High", "Nifty", "Auto sector swings"),
    StockEntry("SUNPHARMA", "Sun Pharma", "Good", "Moderate-High", "Nifty", "Pharma news-driven"),
    StockEntry("ULTRACEMCO", "UltraTech Cement", "Good", "Moderate", "Nifty, Sensex", "Cement/infra plays"),
]

# Back-compat: the flat list used by the old CURATED_STOCKS tuple.
ALL_STOCK_NAMES: List[str] = [e.name for e in STOCK_REGISTRY] + [e.name for e in OPTIONAL_STOCKS]
CURATED_STOCK_NAMES: List[str] = ALL_STOCK_NAMES  # back-compat alias

LIQUIDITY_ORDER = {"Very High": 0, "High": 1, "Good": 2}

STOCKS_BY_LIQUIDITY: dict[str, List[StockEntry]] = {}
for e in STOCK_REGISTRY:
    STOCKS_BY_LIQUIDITY.setdefault(e.liquidity, []).append(e)
