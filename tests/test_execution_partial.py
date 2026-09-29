"""Partial fills: residual sizing, new client_order_id per attempt, at most two attempts."""

from __future__ import annotations

from decimal import Decimal

from stocktry.execution.testing import scenario


def ief_orders(broker):
    return sorted((o for o in broker.orders if o.symbol == "IEF"), key=lambda o: o.client_order_id)


def test_partial_then_done_for_day_resubmits_residual_once_and_completes(tmp_path):
    sc = scenario(tmp_path, scripted_fill_fractions={"IEF": [0.5, 1.0]}, partial_final_status="done_for_day")
    res = sc.run()
    a1, a2 = ief_orders(sc.broker)
    assert (a1.client_order_id, a1.status) == ("demo-2026-10-01-IEF-buy-a1", "done_for_day")
    assert (a2.client_order_id, a2.status) == ("demo-2026-10-01-IEF-buy-a2", "filled")
    # residual = what is still missing after a1, re-sized from fresh state (~half of a1)
    missing = a1.notional - a1.filled_notional
    assert abs(a2.notional - missing) <= Decimal("0.30")
    assert res.status == "completed"
    # IEF now ~ at target (30% of equity)
    acct = sc.broker.get_account()
    ief_value = sc.broker.positions["IEF"] * Decimal("95")
    assert abs(ief_value / acct.equity - Decimal("0.3")) < Decimal("0.01")


def test_partial_twice_stops_after_two_attempts_and_alerts(tmp_path):
    sc = scenario(tmp_path, scripted_fill_fractions={"IEF": [0.5, 0.5, 0.5]})
    res = sc.run()
    assert [o.client_order_id[-2:] for o in ief_orders(sc.broker)] == ["a1", "a2"]
    assert res.status == "incomplete" and res.exit_code == 1
    assert "rebalance_incomplete" in res.alerts
    # a later trigger for the same rebalance does not open a third attempt
    res2 = sc.run()
    assert len(ief_orders(sc.broker)) == 2
    assert res2.status == "already_done"


def test_partial_that_never_finishes_is_cancelled_then_residual_sent(tmp_path):
    sc = scenario(tmp_path, scripted_fill_fractions={"IEF": [0.4]}, partial_final_status=None)
    res = sc.run()
    a1, a2 = ief_orders(sc.broker)
    assert a1.status == "canceled" and a1.filled_qty > 0
    assert a2.status == "filled"
    assert res.status == "completed"


def test_seeded_random_partial_fills_are_deterministic(tmp_path):
    def run(seed, sub):
        sc = scenario(tmp_path / sub, partial_fill_prob=0.7, seed=seed)
        sc.run()
        return [(o.client_order_id, str(o.filled_qty), o.status) for o in sc.broker.orders]

    assert run(7, "a") == run(7, "b")
    assert all(len(v) <= 2 for v in [[o for o in run(11, "c") if "IEF" in o[0]]])


def test_sells_not_terminal_blocks_buys(tmp_path):
    sc = scenario(tmp_path, scripted_fill_fractions={"SPY": [0.5]}, partial_final_status=None)
    orig_cancel = sc.broker.cancel_order
    sc.broker.cancel_order = lambda oid: None  # cancel silently ignored: the sell stays open
    res = sc.run()
    sc.broker.cancel_order = orig_cancel
    assert res.status == "incomplete"
    assert not [o for o in sc.broker.orders if o.side == "buy"], "no buys while a sell is unresolved"
    assert "order_not_terminal" in res.alerts
