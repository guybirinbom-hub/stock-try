"""Duplicate triggers, concurrent runs, 504-after-accept, crash and restart.

All offline: LocalSimBroker, no network, no wall clock.
"""

from __future__ import annotations

import threading
from collections import Counter
from dataclasses import replace

import pytest

from stocktry.execution import ledger as ledger_mod
from stocktry.execution.testing import scenario


def legs(broker):
    return Counter((o.symbol, o.side) for o in broker.orders)


def test_two_sequential_runs_submit_one_order_per_leg(tmp_path):
    sc = scenario(tmp_path)
    first = sc.run()
    assert first.status == "completed"
    assert legs(sc.broker) == Counter({("SPY", "sell"): 1, ("IEF", "buy"): 1, ("GLD", "buy"): 1})
    second = sc.run()
    assert second.status == "already_done"
    assert second.submitted == []
    assert len(sc.broker.orders) == 3
    assert sc.broker.submit_calls == 3
    # every client_order_id follows <strategy>-<rebalance date>-<symbol>-<side>-a<attempt>
    assert sorted(o.client_order_id for o in sc.broker.orders) == [
        "demo-2026-10-01-GLD-buy-a1",
        "demo-2026-10-01-IEF-buy-a1",
        "demo-2026-10-01-SPY-sell-a1",
    ]


def test_concurrent_runs_interleaved_submit_one_order_per_leg(tmp_path):
    """Run B executes entirely inside run A's first submit (after A's lookups passed)."""
    sc = scenario(tmp_path)
    cfg_b = replace(sc.cfg, ledger_path=tmp_path / "machine_b" / "demo.jsonl")
    results = {}

    def hook(cid):
        sc.broker.before_submit_hook = None  # B must not recurse
        results["b"] = sc.run(cfg=cfg_b)

    sc.broker.before_submit_hook = hook
    results["a"] = sc.run()
    assert legs(sc.broker) == Counter({("SPY", "sell"): 1, ("IEF", "buy"): 1, ("GLD", "buy"): 1})
    assert results["b"].status == "completed"
    assert results["a"].status == "completed"
    assert "duplicate_client_order_id" in results["a"].alerts  # A's submit hit the broker's uniqueness check
    assert results["a"].submitted == []


def test_concurrent_runs_on_threads_submit_one_order_per_leg(tmp_path):
    sc = scenario(tmp_path)
    barrier = threading.Barrier(2, timeout=10)
    first_lookup_done = set()
    lock = threading.Lock()

    def lookup_hook(cid):
        me = threading.get_ident()
        with lock:
            wait = me not in first_lookup_done
            first_lookup_done.add(me)
        if wait:
            barrier.wait()  # both runs have planned and pass the pre-submit lookup together

    sc.broker.before_lookup_hook = lookup_hook
    errors, results = [], []

    def worker(name):
        cfg = replace(sc.cfg, ledger_path=tmp_path / name / "demo.jsonl")
        try:
            results.append(sc.run(cfg=cfg))
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in ("m1", "m2")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert not errors, errors
    assert legs(sc.broker) == Counter({("SPY", "sell"): 1, ("IEF", "buy"): 1, ("GLD", "buy"): 1})
    assert len({o.client_order_id for o in sc.broker.orders}) == len(sc.broker.orders) == 3


def test_same_machine_concurrent_run_is_refused_by_local_lock(tmp_path):
    from stocktry.execution.guards import ConcurrentRunError
    from stocktry.execution.ledger import RunLock

    sc = scenario(tmp_path)
    with RunLock(sc.cfg.ledger_path.with_suffix(".lock")):
        with pytest.raises(ConcurrentRunError):
            sc.run()
    assert sc.broker.orders == []


@pytest.mark.parametrize("mode", ["http_504_after_record", "timeout_after_record"])
def test_error_after_order_landed_does_not_duplicate(tmp_path, mode):
    sc = scenario(tmp_path)
    sc.broker.inject_failure("submit", mode, times=1)
    res = sc.run()
    assert res.status == "completed"
    assert legs(sc.broker) == Counter({("SPY", "sell"): 1, ("IEF", "buy"): 1, ("GLD", "buy"): 1})
    assert sc.broker.submit_calls == 3  # nothing was re-sent
    assert "submit_error_but_order_landed" in res.alerts
    assert sc.run().status == "already_done"
    assert len(sc.broker.orders) == 3


def test_error_before_order_landed_is_not_retried_in_run_but_next_run_places_it_once(tmp_path):
    sc = scenario(tmp_path)
    sc.broker.inject_failure("submit", "timeout_before_record", times=1)
    res = sc.run()
    assert res.status == "incomplete"
    assert "submit_failed" in res.alerts
    assert ("SPY", "sell") not in legs(sc.broker)  # the first order (the SPY sell) never landed
    res2 = sc.run()
    assert res2.status == "completed"
    assert legs(sc.broker)[("SPY", "sell")] == 1
    assert all(n == 1 for n in legs(sc.broker).values())


def test_pre_submit_lookup_failure_blocks_that_order(tmp_path):
    sc = scenario(tmp_path)
    sc.broker.inject_failure("get_order_by_client_id", "timeout", times=1)
    res = sc.run()
    assert "pre_submit_lookup_failed" in res.alerts
    assert ("SPY", "sell") not in legs(sc.broker)
    assert res.status == "incomplete"


class SimulatedCrash(BaseException):
    """Stands in for SIGKILL: not an Exception, so nothing in the runner catches it."""


def test_crash_after_submit_before_ledger_write_then_restart_reconciles(tmp_path, monkeypatch):
    sc = scenario(tmp_path)
    real_append = ledger_mod.Ledger.append

    def crashing_append(self, record):
        if record.get("event") == "submitted":
            raise SimulatedCrash()
        return real_append(self, record)

    monkeypatch.setattr(ledger_mod.Ledger, "append", crashing_append)
    with pytest.raises(SimulatedCrash):
        sc.run()
    assert [o.client_order_id for o in sc.broker.orders] == ["demo-2026-10-01-SPY-sell-a1"]
    monkeypatch.setattr(ledger_mod.Ledger, "append", real_append)

    res = sc.run()  # restart
    assert res.status == "completed"
    assert legs(sc.broker) == Counter({("SPY", "sell"): 1, ("IEF", "buy"): 1, ("GLD", "buy"): 1})
    assert [o.client_order_id for o in res.existing] == ["demo-2026-10-01-SPY-sell-a1"]
    records = ledger_mod.Ledger(sc.cfg.ledger_path).read()
    events = [r["event"] for r in records]
    assert events.count("submit_intent") == 3  # write-ahead intent survived the crash
    end = [r for r in records if r["event"] == "run_end"][-1]
    assert {o["client_order_id"] for o in end["orders"]} == {o.client_order_id for o in sc.broker.orders}


def test_ledger_is_append_only_and_hash_is_stable(tmp_path):
    sc = scenario(tmp_path)
    sc.run()
    before = sc.cfg.ledger_path.read_text().splitlines()
    sc.run()
    after = sc.cfg.ledger_path.read_text().splitlines()
    assert after[: len(before)] == before
    plans = [r for r in ledger_mod.Ledger(sc.cfg.ledger_path).read() if r["event"] == "plan"]
    assert plans[0]["inputs_hash"] == plans[1]["inputs_hash"]
