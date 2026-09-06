"""Remote history can never block click-to-table calculation."""
from unittest.mock import patch
from test_v5115_top12 import fixture, YEARS
import top12_jobs as jobs


def test_worker_reads_history_locally_only():
    calls = []
    def ledger(kind, remote=True):
        calls.append((kind, remote))
        if remote:
            raise AssertionError("ranking must not wait for remote history")
        return {}
    with patch.object(jobs, "load_ledger", ledger):
        output = jobs.calculate_rankings(
            fixture(), YEARS, "asof", lambda *a: {}, lambda *a: {}, 1.0, {}
        )
    assert calls == [("Recession", False), ("Max Profit", False)]
    assert len(output["result"]["Recession"]) == 12
    assert len(output["result"]["Max Profit"]) == 12


def test_persistence_cannot_occupy_calculation_executor():
    assert jobs.SAVE_EXECUTOR is not jobs.EXECUTOR
