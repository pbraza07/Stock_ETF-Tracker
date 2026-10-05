import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# Lightweight yfinance stub for offline QA environments. Production installs
# the real yfinance package from requirements.txt; tests monkeypatch these calls.
try:
    import yfinance  # noqa: F401
except ModuleNotFoundError:
    import types
    yf_stub = types.ModuleType("yfinance")
    def _unavailable(*args, **kwargs):
        raise RuntimeError("yfinance unavailable in offline QA")
    yf_stub.download = _unavailable
    yf_stub.Ticker = _unavailable
    yf_stub.Search = _unavailable
    sys.modules["yfinance"] = yf_stub

import pytest
@pytest.fixture(autouse=True)
def isolated_performance_store(tmp_path,monkeypatch):
    monkeypatch.setenv('MARKETSCOPE_STATE_DIR',str(tmp_path/'runtime'))
    monkeypatch.setenv('MARKETSCOPE_EXTERNAL_WORKER','1')
    monkeypatch.delenv('MARKETSCOPE_DATABASE_URL',raising=False)
