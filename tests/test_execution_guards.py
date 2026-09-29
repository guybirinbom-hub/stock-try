"""Hard guards: prices, weights, whitelist, caps and carve-outs, units, sell-everything, min notional."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from stocktry.execution import planning
from stocktry.execution.guards import (
    LIMITS_OVERRIDE_ACK,
    GuardViolation,
    Limits,
    check_order_request,
    check_plan_caps,
)
from stocktry.execution.ledger import Ledger
from stocktry.execution.planning import OrderRequest, PlannedOrder, PriceQuote
from stocktry.execution.testing import scenario


def blocked(sc, code, **kw):
    with pytest.raises(GuardViolation) as ei:
        sc.run(**kw)
    assert ei.value.code == code, ei.value
    assert sc.broker.orders == [], "a guard violation must stop before any order"
    assert any(code in c[2]["data"].decode() for c in sc.transport.calls), "and must alert (ntfy)"
    assert Ledger(sc.cfg.ledger_path).read()[-1]["event"] == "guard_violation"
    return ei.value


# ------------------------------------------------------------------- prices (6)
@pytest.mark.parametrize("bad, code", [
    (float("nan"), "price_invalid"),
    (0.0, "price_invalid"),
    (-5.0, "price_invalid"),
])
def test_nan_zero_negative_price_refused(tmp_path, bad, code):
    sc = scenario(tmp_path)
    q = dict(sc.quotes)
    q["IEF"] = replace(q["IEF"], close=bad)
    blocked(sc, code, prices=q)


def test_stale_price_refused(tmp_path):
    sc = scenario(tmp_path)
    q = dict(sc.quotes)
    q["GLD"] = replace(q["GLD"], session=date(2026, 9, 29))
    blocked(sc, "price_stale", prices=q)


def test_undated_price_refused(tmp_path):
    sc = scenario(tmp_path)
    q = dict(sc.quotes)
    q["SPY"] = 500.0  # bare float: freshness cannot be verified
    blocked(sc, "price_undated", prices=q)


def test_missing_price_refused(tmp_path):
    sc = scenario(tmp_path)
    q = {k: v for k, v in sc.quotes.items() if k != "GLD"}
    blocked(sc, "price_missing", prices=q)


def test_big_move_refused_unless_corporate_action_flag(tmp_path):
    sc = scenario(tmp_path)
    q = dict(sc.quotes)
    q["SPY"] = replace(q["SPY"], prev_close=1000.0)  # -50% "move" (e.g. an unadjusted split)
    blocked(sc, "price_jump", prices=q)
    sc2 = scenario(tmp_path / "ca", cfg_overrides={"corporate_action_symbols": frozenset({"SPY"})})
    q2 = dict(sc2.quotes)
    q2["SPY"] = replace(q2["SPY"], prev_close=1000.0)
    assert sc2.run(prices=q2).status == "completed"


def test_live_price_far_from_close_refused(tmp_path):
    sc = scenario(tmp_path)
    sc.broker.set_prices({"IEF": 50.0})  # broker says 50, yesterday's close was 95
    blocked(sc, "live_price_jump")


# ------------------------------------------------------------------ weights (7)
@pytest.mark.parametrize("targets, code", [
    ({"SPY": 0.51, "IEF": 0.3, "GLD": 0.2}, "weights_sum_above_one"),
    ({"SPY": 0.5, "IEF": -0.1, "GLD": 0.2}, "negative_weight"),
    ({"SPY": 0.5, "TSLA": 0.3}, "symbol_not_in_universe"),
    ({"SPY": float("nan")}, "weight_not_finite"),
])
def test_bad_weights_refused(tmp_path, targets, code):
    sc = scenario(tmp_path)
    blocked(sc, code, targets=targets)


def test_weights_summing_to_one_within_tolerance_accepted(tmp_path):
    sc = scenario(tmp_path)
    assert sc.run(targets={"SPY": 0.5, "IEF": 0.3, "GLD": 0.2 + 5e-10}).status == "completed"


def test_weight_above_max_weight_refused(tmp_path):
    sc = scenario(tmp_path, cfg_overrides={"limits": Limits(max_weight=0.4)})  # tighter: no ack needed
    blocked(sc, "weight_above_max")


def test_position_outside_universe_refused(tmp_path):
    sc = scenario(tmp_path, positions={"SPY": 0.16, "IEF": 0.2, "GLD": 0.04, "QQQ": 0.01},
                  prices={"SPY": 500.0, "IEF": 95.0, "GLD": 250.0, "QQQ": 400.0})
    blocked(sc, "position_outside_universe")


def test_cash_symbol_in_targets_refused(tmp_path):
    sc = scenario(tmp_path, cfg_overrides={"cash_symbol": "GLD", "universe": ("SPY", "IEF")})
    blocked(sc, "cash_symbol_in_targets")


# --------------------------------------------------------------------- caps (8)
def test_per_order_cap_refused(tmp_path):
    # $100 all cash into one ETF: one $99.90 order > min($50, 25% x $100) = $25
    sc = scenario(tmp_path, cash=100, positions={}, targets={"SPY": 1.0},
                  cfg_overrides={"initial_deployment": True})
    gv = blocked(sc, "max_order_notional")
    assert "$25.00" in gv.detail


def test_per_order_cap_override_needs_exact_ack(tmp_path):
    loose = Limits(max_order_notional_abs=Decimal("200"), max_order_notional_frac=Decimal("1"))
    sc = scenario(tmp_path, cash=100, positions={}, targets={"SPY": 1.0},
                  cfg_overrides={"initial_deployment": True, "limits": loose, "limits_ack": "yes"})
    blocked(sc, "limits_override_unacknowledged")
    sc2 = scenario(tmp_path / "ok", cash=100, positions={}, targets={"SPY": 1.0},
                   cfg_overrides={"initial_deployment": True, "limits": loose, "limits_ack": LIMITS_OVERRIDE_ACK})
    assert sc2.run().status == "completed"
    assert len(sc2.broker.orders) == 1


def test_daily_cap_refused_and_initial_deployment_carve_out_works(tmp_path):
    four = {"SPY": 0.25, "IEF": 0.25, "GLD": 0.25, "EFA": 0.25}
    prices = {"SPY": 500.0, "IEF": 95.0, "GLD": 250.0, "EFA": 88.0}
    over = {"universe": ("SPY", "IEF", "GLD", "EFA")}
    sc = scenario(tmp_path, cash=100, positions={}, prices=prices, targets=four, cfg_overrides=over)
    gv = blocked(sc, "max_daily_notional")  # ~$99.90 gross > 60% x $100
    assert "daily cap $60.00" in gv.detail
    sc2 = scenario(tmp_path / "carve", cash=100, positions={}, prices=prices, targets=four,
                   cfg_overrides={**over, "initial_deployment": True})
    res = sc2.run()
    assert res.status == "completed" and len(sc2.broker.orders) == 4


def test_initial_deployment_flag_refused_when_not_all_cash(tmp_path):
    sc = scenario(tmp_path, cfg_overrides={"initial_deployment": True})
    blocked(sc, "initial_deployment_not_all_cash")


def test_daily_cap_counts_orders_already_placed_today(tmp_path):
    sc = scenario(tmp_path)
    sc.broker.submit_order("SPY", "sell", qty=Decimal("0.06"), client_order_id="manual-1")  # $30 today
    n_before = len(sc.broker.orders)
    # plan now: buy SPY $15 + IEF $20 + GLD $16 = $51; with the manual $30 -> $81 > $78 (60% of $130)
    with pytest.raises(GuardViolation) as ei:
        sc.run()
    assert ei.value.code == "max_daily_notional"
    assert len(sc.broker.orders) == n_before


def test_turnover_cap_refused(tmp_path):
    sc = scenario(tmp_path, cfg_overrides={"limits": Limits(max_turnover=Decimal("0.1"))})
    blocked(sc, "max_turnover")


def test_plan_caps_unit():
    def leg(sym, side, n):
        return PlannedOrder(sym, side, Decimal(n), None, Decimal(n) / 10, Decimal(10), 0.5, Decimal(0), Decimal(0))

    limits = Limits(max_order_notional_abs=Decimal("1000"), max_order_notional_frac=Decimal("2"),
                    max_daily_notional_frac=Decimal("10"))
    # one-way turnover (buys+sells)/(2E) = (150+100)/200 = 1.25 > 1.0
    with pytest.raises(GuardViolation) as ei:
        check_plan_caps([leg("A", "buy", 150), leg("B", "sell", 100)], equity=Decimal(100), limits=limits,
                        already_today=Decimal(0), initial_deployment=False, n_symbols=2)
    assert ei.value.code == "max_turnover"
    with pytest.raises(GuardViolation) as ei:
        check_plan_caps([leg("A", "buy", 1)] * 3, equity=Decimal(100), limits=Limits(), already_today=Decimal(0),
                        initial_deployment=False, n_symbols=1)
    assert ei.value.code == "max_orders_per_run"
    # tiny equity: the per-order cap (25% of $3 = $0.75) is below the $1 broker minimum
    with pytest.raises(GuardViolation) as ei:
        check_plan_caps([leg("A", "buy", 1)], equity=Decimal(3), limits=Limits(), already_today=Decimal(0),
                        initial_deployment=True, n_symbols=1)
    assert ei.value.code == "max_order_notional"


# -------------------------------------------------------------------- units (9)
def test_cents_vs_dollars_bug_refused(tmp_path, monkeypatch):
    real = planning.build_order_request

    def cents_bug(leg, cid):
        req = real(leg, cid)
        return replace(req, notional=req.notional * 100) if req.notional is not None else req

    monkeypatch.setattr(planning, "build_order_request", cents_bug)
    sc = scenario(tmp_path)
    blocked(sc, "units_mismatch")


def test_qty_notional_swap_refused(tmp_path, monkeypatch):
    real = planning.build_order_request

    def swap(leg, cid):
        req = real(leg, cid)
        return replace(req, notional=None, qty=req.notional) if req.notional is not None else req

    monkeypatch.setattr(planning, "build_order_request", swap)
    sc = scenario(tmp_path)
    blocked(sc, "qty_on_notional_leg")


def test_order_request_unit_checks():
    leg = PlannedOrder("SPY", "buy", Decimal("20.00"), None, Decimal("0.04"), Decimal("500"), 0.5,
                       Decimal(0), Decimal(20))
    ok = OrderRequest("SPY", "buy", "x-a1", notional=Decimal("20.00"))
    check_order_request(ok, leg, Decimal(0))
    for bad, code in [
        (replace(ok, notional=Decimal("2000.00")), "units_mismatch"),
        (replace(ok, notional=Decimal("0.20")), "below_min_notional"),
        (replace(ok, notional=Decimal("20.001")), "notional_precision"),
        (replace(ok, notional=None, qty=Decimal("20")), "qty_on_notional_leg"),
        (replace(ok, qty=Decimal("0.04")), "units_ambiguous"),
        (replace(ok, side="sell"), "request_mismatch"),
        (replace(ok, order_type="limit"), "request_type"),
    ]:
        with pytest.raises(GuardViolation) as ei:
            check_order_request(bad, leg, Decimal(0))
        assert ei.value.code == code
    close = PlannedOrder("SPY", "sell", None, Decimal("0.2"), Decimal("0.2"), Decimal("500"), 0.0,
                         Decimal(100), Decimal(0), close_position=True)
    check_order_request(OrderRequest("SPY", "sell", "x", qty=Decimal("0.2")), close, Decimal("0.2"))
    with pytest.raises(GuardViolation):
        check_order_request(OrderRequest("SPY", "sell", "x", qty=Decimal("20")), close, Decimal("0.2"))


# ----------------------------------------------------------- sell-everything (14)
def test_sell_everything_refused_unless_declared(tmp_path):
    sc = scenario(tmp_path, targets={})
    blocked(sc, "sell_everything_not_declared")
    sc2 = scenario(tmp_path / "declared", targets={}, cfg_overrides={"allow_exit_to_cash": True})
    res = sc2.run()
    assert res.status == "completed"
    assert sc2.broker.positions == {}
    # full exits are exact-quantity sells, exempt from notional caps for a declared exit ($80 SPY > $32.50 cap)
    spy = [o for o in sc2.broker.orders if o.symbol == "SPY"][0]
    assert spy.qty == Decimal("0.16") and spy.notional is None


def test_declared_exit_into_cash_symbol(tmp_path):
    prices = {"SPY": 500.0, "BIL": 91.5}
    sc = scenario(tmp_path, cash=1.0, positions={"SPY": 0.2}, prices=prices, targets={},
                  cfg_overrides={"universe": ("SPY",), "cash_symbol": "BIL", "allow_exit_to_cash": True})
    res = sc.run()
    assert res.status == "completed"
    assert set(sc.broker.positions) == {"BIL"}


def test_partial_derisking_below_threshold_needs_no_declaration(tmp_path):
    sc = scenario(tmp_path, targets={"SPY": 0.4, "IEF": 0.2, "GLD": 0.1})  # 70% target vs ~84% now
    assert sc.run().status == "completed"


# ------------------------------------------------------------ min notional ($1)
def test_impossible_leg_skips_whole_rebalance(tmp_path):
    # $3 account, 20% sleeves -> $0.60 positions cannot be opened (the $1 minimum)
    four = {"SPY": 0.2, "IEF": 0.2, "GLD": 0.2}
    sc = scenario(tmp_path, cash=3, positions={}, targets=four, cfg_overrides={"initial_deployment": True})
    blocked(sc, "min_notional_impossible_leg")


def test_small_drift_legs_are_skipped_not_traded(tmp_path):
    sc = scenario(tmp_path)
    sc.run()
    res = sc.run()
    assert res.status == "already_done"
    assert all(s.reason in ("below_min_notional", "leg_done_this_rebalance") for s in res.skipped)


def test_plan_never_uses_margin_buying_power():
    plan = planning.plan_rebalance(
        targets={"SPY": 1.0}, positions={}, prices={"SPY": Decimal(100)}, equity=Decimal(100),
        cash_available=Decimal(40), cash_buffer=Decimal("0.10"), min_notional=Decimal(1),
    )
    assert sum(l.notional for l in plan.buys) <= Decimal("39.90")


def test_quotes_from_frame_ignores_rows_after_session():
    import pandas as pd

    idx = pd.to_datetime(["2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01"])
    frame = pd.DataFrame({"SPY": [1.0, 2.0, 3.0, 99.0], "IEF": [1.0, 2.0, float("nan"), 99.0]}, index=idx)
    q = planning.quotes_from_frame(frame, date(2026, 9, 30))
    assert q["SPY"] == PriceQuote(3.0, date(2026, 9, 30), 2.0)
    assert q["IEF"].session == date(2026, 9, 29)  # stale -> the freshness guard will refuse it
