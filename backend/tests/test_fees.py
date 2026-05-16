"""
Tests for the Delta Exchange India fee calculation engine (app/services/fees.py).
Covers all examples from the official Delta Exchange fee documentation.
"""
import pytest
from app.services.fees import (
    compute_notional, compute_estimated_fee, decode_fill_fee,
    summarise_fills, FeeBreakdown, DEFAULT_TAKER_RATE, DEFAULT_MAKER_RATE, GST_RATE,
)


# ─── compute_notional ─────────────────────────────────────────────────────────

class TestComputeNotional:
    def test_vanilla_btcusd(self):
        # Doc example A: 10 contracts × 0.001 BTC × 90000 = 900 USD
        assert compute_notional(10, 0.001, 90000, "vanilla") == pytest.approx(900.0)

    def test_vanilla_small_contract(self):
        assert compute_notional(5, 0.01, 50000, "vanilla") == pytest.approx(2500.0)

    def test_inverse(self):
        # Inverse: 10 × 0.001 / 90000 ≈ 0.0000001111 BTC (paid in BTC)
        n = compute_notional(10, 0.001, 90000, "inverse")
        assert n == pytest.approx(10 * 0.001 / 90000, rel=1e-9)

    def test_zero_price_guard(self):
        assert compute_notional(10, 0.001, 0.0) == 0.0


# ─── compute_estimated_fee ────────────────────────────────────────────────────

class TestComputeEstimatedFee:
    def test_example_a_normal_taker(self):
        """Doc Example A: 10 × 0.001 × 90000 × 0.0005 = 0.45 USD"""
        fb = compute_estimated_fee(10, 90000, contract_value=0.001, is_taker=True)
        assert fb.notional_usd      == pytest.approx(900.0)
        assert fb.gross_commission  == pytest.approx(0.45)
        assert fb.net_commission    == pytest.approx(0.45)
        assert fb.vip_discount      == pytest.approx(0.0)
        assert fb.gst_amount        == pytest.approx(0.45 * 0.18)
        assert fb.total_with_gst    == pytest.approx(0.45 * 1.18)
        assert fb.fill_type         == "normal"
        assert fb.role              == "taker"

    def test_example_b_normal_maker(self):
        """Doc Example B: 10 × 0.001 × 90000 × 0.0002 = 0.18 USD"""
        fb = compute_estimated_fee(10, 90000, contract_value=0.001, is_taker=False)
        assert fb.net_commission == pytest.approx(0.18)
        assert fb.gst_amount     == pytest.approx(0.18 * 0.18)
        assert fb.role           == "maker"

    def test_example_c_vip_10pct_discount(self):
        """Doc Example C: gross=0.45, VIP 10% → net=0.405 USD"""
        fb = compute_estimated_fee(10, 90000, contract_value=0.001,
                                   is_taker=True, vip_discount=0.10)
        assert fb.gross_commission == pytest.approx(0.45)
        assert fb.vip_discount     == pytest.approx(0.045)
        assert fb.net_commission   == pytest.approx(0.405, rel=1e-6)
        assert fb.effective_rate   == pytest.approx(0.00045, rel=1e-6)

    def test_no_gst_on_zero_fee(self):
        fb = compute_estimated_fee(0, 90000)
        assert fb.gst_amount == 0.0

    def test_gst_rate_constant(self):
        fb = compute_estimated_fee(10, 90000, is_taker=True)
        assert fb.gst_amount == pytest.approx(fb.net_commission * GST_RATE)

    def test_effective_rate(self):
        fb = compute_estimated_fee(10, 90000, contract_value=0.001, is_taker=True)
        assert fb.effective_rate == pytest.approx(DEFAULT_TAKER_RATE)

    def test_vip_discount_clamped(self):
        """vip_discount > 1.0 is clamped to 1.0"""
        fb = compute_estimated_fee(10, 90000, is_taker=True, vip_discount=1.5)
        assert fb.net_commission == pytest.approx(0.0, abs=1e-9)


# ─── decode_fill_fee ──────────────────────────────────────────────────────────

class TestDecodeFillFee:
    def _fill(self, **kwargs):
        base = {
            "id": 1, "fill_type": "normal", "side": "buy", "role": "taker",
            "price": "90000", "size": 10, "commission": "0.45",
            "settling_asset_symbol": "USD", "product_symbol": "BTCUSD",
            "created_at": "2025-05-10T10:30:00Z",
            "meta_data": {
                "effective_commission_rate": "0.0005",
                "commission_deto": "0",
                "commission_deto_in_settling_asset": "0",
                "total_commission_in_settling_asset": "0.45",
                "liquidation_fee_deto": "0",
                "liquidation_fee_deto_in_settling_asset": "0",
                "total_liquidation_fee_in_settling_asset": "0",
                "tfc_used_for_commission": "0",
                "tfc_used_for_liquidation_fee": "0",
            },
        }
        base.update(kwargs)
        return base

    def test_example_a_normal_taker(self):
        """Doc Example A: fill.commission = 0.45 USD"""
        fb = decode_fill_fee(self._fill(), contract_value=0.001)
        assert fb.net_commission  == pytest.approx(0.45)
        assert fb.fill_type       == "normal"
        assert fb.role            == "taker"
        assert fb.notional_usd    == pytest.approx(900.0)
        assert fb.gst_amount      == pytest.approx(0.45 * 0.18)
        assert fb.effective_rate  == pytest.approx(0.0005)

    def test_example_b_normal_maker(self):
        fb = decode_fill_fee(self._fill(commission="0.18",
            role="maker",
            meta_data={
                "effective_commission_rate": "0.0002",
                "total_commission_in_settling_asset": "0.18",
                **{k: "0" for k in ["commission_deto","commission_deto_in_settling_asset",
                                     "liquidation_fee_deto","liquidation_fee_deto_in_settling_asset",
                                     "total_liquidation_fee_in_settling_asset",
                                     "tfc_used_for_commission","tfc_used_for_liquidation_fee"]},
            }), contract_value=0.001)
        assert fb.net_commission == pytest.approx(0.18)
        assert fb.role == "maker"

    def test_maker_rebate_negative_commission(self):
        """Negative commission = rebate earned"""
        fb = decode_fill_fee(self._fill(commission="-0.09", role="maker",
            meta_data={"effective_commission_rate": "-0.0001",
                       "total_commission_in_settling_asset": "-0.09",
                       **{k: "0" for k in ["commission_deto","commission_deto_in_settling_asset",
                                            "liquidation_fee_deto","liquidation_fee_deto_in_settling_asset",
                                            "total_liquidation_fee_in_settling_asset",
                                            "tfc_used_for_commission","tfc_used_for_liquidation_fee"]}}),
            contract_value=0.001)
        assert fb.net_commission < 0
        assert fb.is_rebate is True
        assert fb.gst_amount == 0.0  # no GST on rebates

    def test_adl_no_commission(self):
        """Doc Example E: ADL fill — commission = 0, no fee charged"""
        fb = decode_fill_fee(self._fill(fill_type="adl", commission="0",
            meta_data={"effective_commission_rate": "0",
                       **{k: "0" for k in ["commission_deto","commission_deto_in_settling_asset",
                                            "liquidation_fee_deto","liquidation_fee_deto_in_settling_asset",
                                            "total_liquidation_fee_in_settling_asset",
                                            "tfc_used_for_commission","tfc_used_for_liquidation_fee"]}}),
            contract_value=0.001)
        assert fb.net_commission == 0.0
        assert fb.gst_amount     == 0.0
        assert fb.effective_rate == 0.0
        assert fb.is_adl is True

    def test_liquidation_fill_separate_fee(self):
        """Doc Example D: liquidation has trading commission + separate liq_fee in meta_data"""
        meta = {
            "effective_commission_rate": "0.0005",
            "total_commission_in_settling_asset": "0.45",
            "total_liquidation_fee_in_settling_asset": "15.00",
            **{k: "0" for k in ["commission_deto","commission_deto_in_settling_asset",
                                  "liquidation_fee_deto","liquidation_fee_deto_in_settling_asset",
                                  "tfc_used_for_commission","tfc_used_for_liquidation_fee"]},
        }
        fb = decode_fill_fee(self._fill(fill_type="liquidation",
                                        commission="0.45", meta_data=meta),
                             contract_value=0.001)
        assert fb.fill_type      == "liquidation"
        assert fb.net_commission == pytest.approx(0.45)
        assert fb.liquidation_fee == pytest.approx(15.0)
        assert fb.total_cost     == pytest.approx(0.45 + 15.0)  # commission + liq_fee
        assert fb.is_liquidation is True

    def test_deto_discount(self):
        """Doc Example H: DETO discount reduces net commission in settling asset"""
        meta = {
            "effective_commission_rate": "0.000375",
            "commission_deto": "X_DETO",
            "commission_deto_in_settling_asset": "0.1125",
            "total_commission_in_settling_asset": "0.3375",
            **{k: "0" for k in ["liquidation_fee_deto","liquidation_fee_deto_in_settling_asset",
                                  "total_liquidation_fee_in_settling_asset",
                                  "tfc_used_for_commission","tfc_used_for_liquidation_fee"]},
        }
        fb = decode_fill_fee(self._fill(commission="0.3375", meta_data=meta),
                             contract_value=0.001)
        assert fb.net_commission   == pytest.approx(0.3375)
        assert fb.deto_discount    == pytest.approx(0.1125)
        assert fb.effective_rate   == pytest.approx(0.000375, rel=1e-6)

    def test_tfc_reduces_total_cost(self):
        """TFC credit offsets commission — total_cost = commission - tfc"""
        meta = {
            "effective_commission_rate": "0.0005",
            "total_commission_in_settling_asset": "0.45",
            "tfc_used_for_commission": "0.10",
            **{k: "0" for k in ["commission_deto","commission_deto_in_settling_asset",
                                  "liquidation_fee_deto","liquidation_fee_deto_in_settling_asset",
                                  "total_liquidation_fee_in_settling_asset",
                                  "tfc_used_for_liquidation_fee"]},
        }
        fb = decode_fill_fee(self._fill(commission="0.35", meta_data=meta),
                             contract_value=0.001)
        assert fb.tfc_used    == pytest.approx(0.10)
        assert fb.total_cost  == pytest.approx(0.35 - 0.10)

    def test_settlement_fill(self):
        """Settlement fills carry a commission if applicable."""
        fb = decode_fill_fee(self._fill(fill_type="settlement"), contract_value=0.001)
        assert fb.fill_type      == "settlement"
        assert fb.net_commission == pytest.approx(0.45)  # same as normal

    def test_sign_convention_positive_paid(self):
        """Positive commission = you paid."""
        fb = decode_fill_fee(self._fill(commission="0.45"), contract_value=0.001)
        assert fb.net_commission > 0
        assert fb.is_rebate is False

    def test_gst_not_charged_on_zero_fee(self):
        fb = decode_fill_fee(self._fill(fill_type="adl", commission="0",
            meta_data={"effective_commission_rate": "0",
                       **{k: "0" for k in ["commission_deto","commission_deto_in_settling_asset",
                                            "liquidation_fee_deto","liquidation_fee_deto_in_settling_asset",
                                            "total_liquidation_fee_in_settling_asset",
                                            "tfc_used_for_commission","tfc_used_for_liquidation_fee"]}}),
            contract_value=0.001)
        assert fb.gst_amount == 0.0


# ─── summarise_fills ──────────────────────────────────────────────────────────

class TestSummariseFills:
    def _bd(self, **kwargs):
        defaults = dict(
            notional_usd=900.0, gross_commission=0.45, vip_discount=0.0,
            deto_discount=0.0, tfc_used=0.0, net_commission=0.45,
            liquidation_fee=0.0, gst_amount=0.081, total_with_gst=0.531,
            total_cost=0.45, effective_rate=0.0005,
            fill_type="normal", role="taker", settling_asset="USD",
        )
        defaults.update(kwargs)
        return FeeBreakdown(**defaults)

    def test_empty_list(self):
        s = summarise_fills([])
        assert s.total_fills == 0

    def test_single_taker(self):
        s = summarise_fills([self._bd()])
        assert s.total_fills         == 1
        assert s.taker_fills         == 1
        assert s.maker_fills         == 0
        assert s.total_net_commission == pytest.approx(0.45)
        assert s.total_gst           == pytest.approx(0.081)

    def test_mixed_fill_types(self):
        fills = [
            self._bd(fill_type="normal",      role="taker"),
            self._bd(fill_type="liquidation", role="taker", liquidation_fee=15.0, total_cost=15.45),
            self._bd(fill_type="adl",         role="taker", net_commission=0.0, total_cost=0.0),
            self._bd(fill_type="maker",       role="maker", net_commission=-0.09, total_cost=-0.09,
                     gst_amount=0.0, total_with_gst=-0.09),
        ]
        s = summarise_fills(fills)
        assert s.total_fills       == 4
        assert s.normal_fills      == 1
        assert s.liquidation_fills == 1
        assert s.adl_fills         == 1
        assert s.taker_fills       == 3
        assert s.maker_fills       == 1
        assert s.total_rebates     == pytest.approx(0.09)

    def test_avg_effective_rate(self):
        fills = [
            self._bd(effective_rate=0.0005),
            self._bd(effective_rate=0.0003),
        ]
        s = summarise_fills(fills)
        assert s.avg_effective_rate == pytest.approx(0.0004)
