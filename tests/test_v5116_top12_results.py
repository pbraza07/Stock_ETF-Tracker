from concurrent.futures import Future
from unittest.mock import patch
import pytest
from streamlit.testing.v1 import AppTest
from test_v5115_top12 import fixture, YEARS
from top12_rankings import build_top12_rankings
from top12_jobs import calculate_rankings


@pytest.fixture(scope="module")
def payload():
    return {
        "result": build_top12_rankings(fixture(), YEARS, simulations=100),
        "histories": {},
    }


class Executor:
    def __init__(self, payload, pending=False):
        self.future = Future()
        if not pending:
            self.future.set_result(payload)
        self.calls = 0

    def submit(self, function, *args):
        if function.__name__ == "save_histories":
            saved = Future()
            saved.set_exception(RuntimeError("history provider down"))
            return saved
        self.calls += 1
        return self.future


SOURCE = """
import streamlit as st
from unittest.mock import patch
import top12_ui as ui
from runtime_performance import preserve_navigation_state
preserve_navigation_state()
st.session_state.setdefault('workspace_navigation', 'Favorite Picks')
main,favorites=st.tabs(['Market','Favorite Picks'],key='workspace_navigation',on_change='rerun')
if favorites.open:
    with favorites:
        with patch.object(ui, 'EXECUTOR', st.session_state.qa_executor), patch.object(ui, 'ranking_exports', side_effect=RuntimeError('export down')):
            ui.render_top12_rankings(st.session_state.qa_market, st.session_state.qa_years, '2026-09-04', lambda *a: {}, lambda *a: {})
"""


def app_for(executor):
    app = AppTest.from_string(SOURCE)
    app.session_state.qa_executor = executor
    app.session_state.qa_market = fixture()
    app.session_state.qa_years = YEARS
    return app.run()


@pytest.mark.parametrize(
    "button,kind", [("t12_recession", "Recession"), ("t12_profit", "Max Profit")]
)
def test_each_button_renders_despite_save_and_export_failure(payload, button, kind):
    app = app_for(Executor(payload))
    app.button(key=button).click().run()
    assert not app.exception
    assert app.session_state.t12_input_view == kind
    assert app.session_state.workspace_navigation == "Favorite Picks"
    assert len(app.dataframe[0].value) == 12
    assert kind + " Score" in app.dataframe[0].value.columns
    assert any("Reports could not" in warning.value for warning in app.warning)
    app.run()
    assert len(app.dataframe[0].value) == 12


def test_pending_calculation_survives_rerun_and_prevents_duplicates(payload):
    executor = Executor(payload, pending=True)
    app = app_for(executor)
    app.button(key="t12_profit").click().run()
    app.run()
    assert app.button(key="t12_profit").disabled
    assert executor.calls == 1
    assert app.session_state.t12_job["future"] is executor.future
    executor.future.set_result(payload)
    app.run()
    assert not app.exception and len(app.dataframe[0].value) == 12


def test_worker_falls_back_and_does_not_save_before_return(payload):
    import top12_jobs as jobs

    with patch.object(jobs, "load_ledger", return_value={}), patch.object(
        jobs, "build_top12_rankings", return_value=payload["result"]
    ), patch.object(
        jobs, "record_run", side_effect=RuntimeError("history malformed")
    ), patch.object(
        jobs, "persist_ledger"
    ) as save:
        result = calculate_rankings(
            fixture(),
            YEARS,
            "asof",
            lambda *a: (_ for _ in ()).throw(RuntimeError("monthly down")),
            lambda *a: (_ for _ in ()).throw(RuntimeError("live down")),
            1.0,
            {},
        )
    assert len(result["result"]["Recession"]) == 12
    assert not save.called
    assert any("Annual approximations" in w for w in result["result"]["warnings"])


def test_failure_is_visible_and_previous_result_retained(payload):
    executor = Executor(payload, pending=True)
    app = app_for(executor)
    app.session_state.t12_result = payload["result"]
    app.button(key="t12_recession").click().run()
    executor.future.set_exception(ValueError("Insufficient sector diversity"))
    app.run()
    assert not app.exception
    assert any("Insufficient sector diversity" in error.value for error in app.error)
    assert len(app.dataframe[0].value) == 12


def test_switching_tabs_keeps_completed_results(payload):
    app = app_for(Executor(payload))
    app.button(key="t12_profit").click().run()
    app.session_state.workspace_navigation = "Market"
    app.run()
    assert not app.dataframe
    app.session_state.workspace_navigation = "Favorite Picks"
    app.run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 12
    assert "Max Profit Score" in app.dataframe[0].value


def test_slow_supplemental_provider_falls_back(payload):
    import threading
    import top12_jobs as jobs

    release = threading.Event()

    def slow(*args):
        release.wait(5)
        return {}

    try:
        with patch.object(jobs, "LIVE_WAIT_SECONDS", 0.01), patch.object(
            jobs, "load_ledger", return_value={}
        ), patch.object(jobs, "build_top12_rankings", return_value=payload["result"]):
            result = calculate_rankings(
                fixture(), YEARS, "asof", lambda *a: {}, slow, 1.0, {}
            )
        assert len(result["result"]["Max Profit"]) == 12
        assert any(
            "Recent supplemental inputs unavailable" in w
            for w in result["result"]["warnings"]
        )
    finally:
        release.set()


def test_real_worker_calculates_both_tables_without_network():
    import top12_jobs as jobs

    with patch.object(jobs, "load_ledger", return_value={}):
        payload = calculate_rankings(
            fixture(), YEARS, "asof", lambda *a: {}, lambda *a: {}, 1.0, {}
        )
    assert len(payload["result"]["Recession"]) == 12
    assert len(payload["result"]["Max Profit"]) == 12
    assert all(len(h["runs"]) == 1 for h in payload["histories"].values())


@pytest.mark.parametrize("kind", ["Recession", "Max Profit"])
def test_callback_request_survives_interrupted_run_without_button_pulse(payload, kind):
    # Simulate an enclosing app stopping/rerunning after callbacks, before the
    # Top 12 body is reached. The next run has no button=True event.
    source = SOURCE.replace(
        "preserve_navigation_state()",
        """preserve_navigation_state()
if st.session_state.pop('qa_interrupt_after_callback', False):
    ui.request_ranking(st.session_state.qa_requested_kind)
    st.stop()
""",
    )
    executor = Executor(payload)
    app = AppTest.from_string(source)
    app.session_state.qa_executor = executor
    app.session_state.qa_market = fixture()
    app.session_state.qa_years = YEARS
    app.session_state.qa_requested_kind = kind
    app.session_state.qa_interrupt_after_callback = True
    app.run()
    assert executor.calls == 0
    app.run()
    assert not app.exception
    assert executor.calls == 1
    assert len(app.dataframe[0].value) == 12
    assert kind + " Score" in app.dataframe[0].value.columns
    app.run()
    assert executor.calls == 1
