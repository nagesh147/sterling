"""
Delta Exchange India — complete fee calculation engine.

All formulas sourced from official Delta Exchange API docs.
Key rule: fill.commission is always the AUTHORITATIVE net fee.
Positive = you paid. Negative = you earned (maker rebate).
GST is NOT in the API — applied as a post-processing step here.
"""
from dataclasses import dataclass, field
from typing import Optional

# ── Default rates (from product API; these are the standard tiers) ────────────
DEFAULT_TAKER_RATE = 0.0005   # 0.05% — market orders / aggressive limits
DEFAULT_MAKER_RATE = 0.0002   # 0.02% — resting limit orders (can be 0 or negative)
GST_RATE           = 0.18     # 18% GST on exchange commission (India statutory)
                               # NOT exposed by API — applied externally here.

FILL_TYPES = frozenset({"normal", "liquidation", "adl", "settlement", "otc"})


@dataclass
class FeeBreakdown:
    """
    Complete fee breakdown for one fill or a pre-trade estimate.
    All amounts in the settling asset (usually USD/USDC/INR).
    """
    notional_usd:        float   # size × contract_value × price  (vanilla)
    gross_commission:    float   # before any VIP/DETO/TFC reduction
    vip_discount:        float   # VIP tier reduction
    deto_discount:       float   # DETO token discount (commission_deto_in_settling_asset)
    tfc_used:            float   # Trading Fee Credit offset
    net_commission:      float   # AUTHORITATIVE — equals fill.commission from API
    liquidation_fee:     float   # separate penalty (liquidation fills only)
    gst_amount:          float   # net_commission × GST_RATE (not in API)
    total_with_gst:      float   # net_commission + gst_amount
    total_cost:          float   # net_commission + liquidation_fee − tfc_used
    effective_rate:      float   # net_commission / notional (0 for adl)
    fill_type:           str     # "normal"/"liquidation"/"adl"/"settlement"/"otc"
    role:                str     # "taker" / "maker"
    settling_asset:      str     # "USD" / "USDC" / etc.

    @property
    def is_adl(self) -> bool:
        return self.fill_type == "adl"

    @property
    def is_liquidation(self) -> bool:
        return self.fill_type == "liquidation"

    @property
    def is_rebate(self) -> bool:
        return self.net_commission < 0

    def to_dict(self) -> dict:
        return {
            "notional_usd":     round(self.notional_usd, 4),
            "gross_commission": round(self.gross_commission, 6),
            "vip_discount":     round(self.vip_discount, 6),
            "deto_discount":    round(self.deto_discount, 6),
            "tfc_used":         round(self.tfc_used, 6),
            "net_commission":   round(self.net_commission, 6),
            "liquidation_fee":  round(self.liquidation_fee, 6),
            "gst_amount":       round(self.gst_amount, 6),
            "total_with_gst":   round(self.total_with_gst, 6),
            "total_cost":       round(self.total_cost, 6),
            "effective_rate":   round(self.effective_rate, 8),
            "fill_type":        self.fill_type,
            "role":             self.role,
            "settling_asset":   self.settling_asset,
            "is_rebate":        self.is_rebate,
        }


# ── Notional calculation ───────────────────────────────────────────────────────

def compute_notional(
    size:            float,
    contract_value:  float,
    fill_price:      float,
    notional_type:   str = "vanilla",
) -> float:
    """
    Vanilla:  notional = size × contract_value × fill_price
    Inverse:  notional = size × contract_value / fill_price
    Delta India contracts are predominantly vanilla.
    """
    if fill_price <= 0:
        return 0.0
    if notional_type == "inverse":
        return size * contract_value / fill_price
    return size * contract_value * fill_price


# ── Pre-trade estimate ─────────────────────────────────────────────────────────

def compute_estimated_fee(
    size:            float,
    fill_price:      float,
    contract_value:  float  = 0.001,
    notional_type:   str    = "vanilla",
    is_taker:        bool   = True,
    taker_rate:      float  = DEFAULT_TAKER_RATE,
    maker_rate:      float  = DEFAULT_MAKER_RATE,
    vip_discount:    float  = 0.0,    # fraction, e.g. 0.10 = 10% VIP discount
    gst_rate:        float  = GST_RATE,
    settling_asset:  str    = "USD",
) -> FeeBreakdown:
    """
    Pre-trade fee estimate.  Does not know about DETO or TFC at this stage.
    vip_discount: from GET /v2/users/trading_preferences → vip_discount_factor.
    """
    notional   = compute_notional(size, contract_value, fill_price, notional_type)
    base_rate  = taker_rate if is_taker else maker_rate
    gross      = notional * base_rate
    vip_disc   = gross * max(0.0, min(vip_discount, 1.0))
    net        = gross - vip_disc
    gst        = net * gst_rate if net > 0 else 0.0
    eff_rate   = (net / notional) if notional > 0 else 0.0

    return FeeBreakdown(
        notional_usd     = notional,
        gross_commission = gross,
        vip_discount     = vip_disc,
        deto_discount    = 0.0,
        tfc_used         = 0.0,
        net_commission   = net,
        liquidation_fee  = 0.0,
        gst_amount       = gst,
        total_with_gst   = net + gst,
        total_cost       = net,
        effective_rate   = eff_rate,
        fill_type        = "normal",
        role             = "taker" if is_taker else "maker",
        settling_asset   = settling_asset,
    )


# ── Decode raw fill from GET /v2/fills ─────────────────────────────────────────

def decode_fill_fee(
    fill_raw:        dict,
    contract_value:  float = 0.001,
    notional_type:   str   = "vanilla",
    gst_rate:        float = GST_RATE,
) -> FeeBreakdown:
    """
    Decode a raw fill dict from GET /v2/fills into a complete FeeBreakdown.

    fill.commission is AUTHORITATIVE (positive = paid, negative = rebate).
    Liquidation fee is SEPARATE from commission and lives in meta_data.
    ADL fills carry no commission.
    """
    fill_type = str(fill_raw.get("fill_type") or "normal").lower()
    if fill_type not in FILL_TYPES:
        fill_type = "normal"

    role      = str(fill_raw.get("role") or "taker").lower()
    price     = float(fill_raw.get("price") or 0.0)
    size      = float(fill_raw.get("size")  or 0.0)
    settling  = str(fill_raw.get("settling_asset_symbol") or "USD")
    meta      = fill_raw.get("meta_data") or {}

    notional = compute_notional(size, contract_value, price, notional_type)

    # ADL: no fee by spec
    if fill_type == "adl":
        return FeeBreakdown(
            notional_usd=notional, gross_commission=0.0, vip_discount=0.0,
            deto_discount=0.0, tfc_used=0.0, net_commission=0.0,
            liquidation_fee=0.0, gst_amount=0.0, total_with_gst=0.0,
            total_cost=0.0, effective_rate=0.0,
            fill_type="adl", role=role, settling_asset=settling,
        )

    # Authoritative net fee from API
    net_commission = float(fill_raw.get("commission") or 0.0)

    # meta_data breakdown
    eff_rate      = float(meta.get("effective_commission_rate") or 0.0)
    deto_disc     = float(meta.get("commission_deto_in_settling_asset") or 0.0)
    tfc_comm      = float(meta.get("tfc_used_for_commission") or 0.0)
    tfc_liq       = float(meta.get("tfc_used_for_liquidation_fee") or 0.0)
    liq_fee       = float(meta.get("total_liquidation_fee_in_settling_asset") or 0.0)
    total_settled = float(meta.get("total_commission_in_settling_asset") or net_commission)

    # Reconstruct gross: total settled + DETO discount + TFC offset on commission
    gross   = total_settled + deto_disc + tfc_comm
    # VIP discount = residual after DETO and TFC are accounted for
    vip_disc = max(0.0, gross - total_settled - deto_disc)

    total_tfc  = tfc_comm + tfc_liq
    total_cost = net_commission + liq_fee - total_tfc

    # GST applies only to positive (paid) commissions — not rebates
    gst = (net_commission * gst_rate) if net_commission > 0 else 0.0

    # Effective rate: use meta_data if available; fallback to net/notional
    if eff_rate == 0.0 and notional > 0:
        eff_rate = net_commission / notional

    return FeeBreakdown(
        notional_usd     = notional,
        gross_commission = gross,
        vip_discount     = vip_disc,
        deto_discount    = deto_disc,
        tfc_used         = total_tfc,
        net_commission   = net_commission,
        liquidation_fee  = liq_fee,
        gst_amount       = gst,
        total_with_gst   = net_commission + gst,
        total_cost       = total_cost,
        effective_rate   = eff_rate,
        fill_type        = fill_type,
        role             = role,
        settling_asset   = settling,
    )


# ── Fee-aware fill summary ─────────────────────────────────────────────────────

@dataclass
class FillSummary:
    total_fills:          int
    normal_fills:         int
    liquidation_fills:    int
    adl_fills:            int
    settlement_fills:     int
    otc_fills:            int
    taker_fills:          int
    maker_fills:          int
    total_notional:       float
    total_gross_commission: float
    total_vip_discount:   float
    total_deto_discount:  float
    total_tfc_used:       float
    total_net_commission: float
    total_liquidation_fee: float
    total_gst:            float
    total_cost_with_gst:  float
    total_rebates:        float  # sum of negative commissions (maker rebates)
    avg_effective_rate:   float


def summarise_fills(breakdowns: list) -> FillSummary:
    """Aggregate a list of FeeBreakdown objects into a FillSummary."""
    if not breakdowns:
        return FillSummary(*([0] * 8), *([0.0] * 11))

    def _count(attr, val):
        return sum(1 for b in breakdowns if getattr(b, attr) == val)

    total_net   = sum(b.net_commission for b in breakdowns)
    total_notional = sum(b.notional_usd for b in breakdowns)
    rebates     = sum(-b.net_commission for b in breakdowns if b.net_commission < 0)
    rates       = [b.effective_rate for b in breakdowns if b.effective_rate > 0]

    return FillSummary(
        total_fills           = len(breakdowns),
        normal_fills          = _count("fill_type", "normal"),
        liquidation_fills     = _count("fill_type", "liquidation"),
        adl_fills             = _count("fill_type", "adl"),
        settlement_fills      = _count("fill_type", "settlement"),
        otc_fills             = _count("fill_type", "otc"),
        taker_fills           = _count("role", "taker"),
        maker_fills           = _count("role", "maker"),
        total_notional        = round(total_notional, 4),
        total_gross_commission= round(sum(b.gross_commission for b in breakdowns), 6),
        total_vip_discount    = round(sum(b.vip_discount for b in breakdowns), 6),
        total_deto_discount   = round(sum(b.deto_discount for b in breakdowns), 6),
        total_tfc_used        = round(sum(b.tfc_used for b in breakdowns), 6),
        total_net_commission  = round(total_net, 6),
        total_liquidation_fee = round(sum(b.liquidation_fee for b in breakdowns), 6),
        total_gst             = round(sum(b.gst_amount for b in breakdowns), 6),
        total_cost_with_gst   = round(sum(b.total_with_gst for b in breakdowns), 6),
        total_rebates         = round(rebates, 6),
        avg_effective_rate    = round(sum(rates) / len(rates), 8) if rates else 0.0,
    )
