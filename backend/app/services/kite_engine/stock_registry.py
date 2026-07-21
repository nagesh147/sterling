"""Curated high-liquidity stock registry for the Sterling Kite Engine scan.

Only Very High and High liquidity names are eligible for production scanning.
Lower-liquidity names remain in ``OPTIONAL_STOCKS`` as reference metadata but are
not exposed through the production scan universe.
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

HIGH_LIQUIDITY_STOCKS: List[StockEntry] = [
    entry for entry in STOCK_REGISTRY + OPTIONAL_STOCKS
    if entry.liquidity in ("Very High", "High")
]
HIGH_LIQUIDITY_STOCK_NAMES: List[str] = list(dict.fromkeys(entry.name for entry in HIGH_LIQUIDITY_STOCKS))

# Back-compatible aliases now intentionally point to the production-safe universe.
ALL_STOCK_NAMES: List[str] = HIGH_LIQUIDITY_STOCK_NAMES
CURATED_STOCK_NAMES: List[str] = HIGH_LIQUIDITY_STOCK_NAMES

LIQUIDITY_ORDER = {"Very High": 0, "High": 1, "Good": 2}
STOCKS_BY_LIQUIDITY: dict[str, List[StockEntry]] = {}
for entry in HIGH_LIQUIDITY_STOCKS:
    STOCKS_BY_LIQUIDITY.setdefault(entry.liquidity, []).append(entry)
