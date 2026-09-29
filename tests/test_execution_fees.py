"""Alpaca fee model (per day, per type, rounded up), dividend rounding, and parity with the backtester."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from stocktry.execution.fees import FeeFill, daily_fees, round_up_cent
from stocktry.execution.ledger import model_dividends

D1, D2 = date(2026, 10, 1), date(2026, 10, 2)


def round_trip(notional: float, price: float = 600.0) -> Decimal:
    sh = Decimal(str(notional)) / Decimal(str(price))
    fees = daily_fees([FeeFill(D1, "buy", sh, Decimal(str(price))), FeeFill(D2, "sell", sh, Decimal(str(price)))])
    return sum((v["total"] for v in fees.values()), Decimal(0))


@pytest.mark.parametrize("notional, expected", [
    (1, "0.04"), (10, "0.04"), (100, "0.04"), (1_000, "0.06"), (10_000, "0.24"),
])
def test_round_trip_fee_table_matches_research_report(notional, expected):
    assert round_trip(notional) == Decimal(expected)


def test_each_type_rounds_up_separately_and_aggregates_per_day():
    same_day = daily_fees([FeeFill(D1, "sell", Decimal("0.01"), Decimal(100)),
                           FeeFill(D1, "sell", Decimal("0.01"), Decimal(100))])
    assert same_day[D1] == {"sec": Decimal("0.01"), "taf": Decimal("0.01"), "cat": Decimal("0.01"),
                            "total": Decimal("0.03")}
    assert round_up_cent(Decimal("0.0000001")) == Decimal("0.01")
    assert round_up_cent(Decimal(0)) == Decimal("0.00")


def test_taf_cap_per_order():
    fees = daily_fees([FeeFill(D1, "sell", Decimal(100_000), Decimal(1))])
    assert fees[D1]["taf"] == Decimal("9.79")


def test_dividends_round_to_cents_so_tiny_positions_get_nothing():
    divs = {"SPY": [(date(2026, 9, 18), 1.83)]}
    tiny = model_dividends({"SPY": Decimal("0.0017")}, divs, date(2026, 9, 1), date(2026, 10, 1))
    assert tiny["total"] == Decimal("0.00")
    big = model_dividends({"SPY": Decimal("10")}, divs, date(2026, 9, 1), date(2026, 10, 1))
    assert big["total"] == Decimal("18.30")
    outside = model_dividends({"SPY": Decimal("10")}, divs, date(2026, 10, 1), date(2026, 11, 2))
    assert outside["total"] == Decimal("0")


def _compare(case):
    costs = pytest.importorskip("stocktry.backtest.costs")
    model = costs.AlpacaFeeModel()
    ours = daily_fees([FeeFill(D2, s, Decimal(str(n)) / Decimal(str(p)), Decimal(str(p))) for s, n, p in case])
    theirs = model.day_fees(D2, [costs.Order("X", s, n, n / p) for s, n, p in case])
    return ours[D2], theirs


def test_parity_with_backtest_cost_model_when_available():
    cases = [
        [("buy", 100.0, 600.0)],
        [("sell", 100.0, 600.0)],
        [("sell", 10_000.0, 600.0), ("buy", 2_500.0, 95.0)],
        [("sell", 100.0, 250.0), ("sell", 40.0, 95.0), ("buy", 60.0, 600.0)],
        [("sell", 5_000_000.0, 1.0)],  # TAF cap
    ]
    for case in cases:
        ours, theirs = _compare(case)
        assert float(ours["sec"]) == pytest.approx(theirs.sec, abs=1e-9)
        assert float(ours["taf"]) == pytest.approx(theirs.taf, abs=1e-9)
        assert float(ours["cat"]) == pytest.approx(theirs.cat, abs=1e-9)


@pytest.mark.xfail(strict=False, reason=(
    "core stocktry.backtest.costs.ceil_cent computes ceil(round(x*100, 6))/100, which turns a CAT fee "
    "below $0.000000005 (a ~$1 order) into $0.00; the fee schedule and the core docstring say $0.01"))
def test_parity_on_one_dollar_orders():
    for case in ([("buy", 1.0, 600.0)], [("sell", 1.0, 600.0)]):
        ours, theirs = _compare(case)
        assert float(ours["cat"]) == pytest.approx(theirs.cat, abs=1e-9)


def test_sim_charges_fees_and_ledger_models_them(tmp_path):
    from stocktry.execution.testing import scenario

    sc = scenario(tmp_path)
    res = sc.run()
    assert res.modelled_fees["2026-10-01"]["total"] == Decimal("0.03")  # SEC + TAF on the sell, CAT on all
    assert res.reconciliation["broker_fees"] == Decimal("0.03")
    paper_like = scenario(tmp_path / "paper", fee_schedule=None)  # Alpaca paper charges nothing
    res2 = paper_like.run()
    assert res2.reconciliation["broker_fees"] == Decimal(0)
    assert res2.modelled_fees["2026-10-01"]["total"] == Decimal("0.03")  # ledger still models them


def test_modelled_dividends_recorded_on_first_run_for_a_rebalance(tmp_path):
    from stocktry.execution.testing import scenario

    sc = scenario(tmp_path)
    divs = {"SPY": [(date(2026, 9, 18), 1.83)], "IEF": [(date(2026, 9, 1), 0.29)]}
    res = sc.run(dividends=divs)
    # pre-trade holdings: 0.16 SPY -> $0.29; 0.2 IEF -> $0.06
    assert res.modelled_dividends["total"] == Decimal("0.35")
    assert sc.run(dividends=divs).modelled_dividends is None  # re-run: holdings already changed
