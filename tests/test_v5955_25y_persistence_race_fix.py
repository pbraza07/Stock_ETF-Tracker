from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "update_market_snapshot.yml").read_text(encoding="utf-8")
PERSIST = (ROOT / "scripts" / "persist_generated_files.sh").read_text(encoding="utf-8")


def test_release_version_5955():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.55"


def test_workflow_uses_full_checkout_for_safe_fetch_reset():
    assert "fetch-depth: 0" in WORKFLOW


def test_verified_25y_snapshot_is_persisted_before_rankings():
    audit = WORKFLOW.index("Audit automatic 25Y annual-return coverage")
    persist = WORKFLOW.index("Persist verified 25Y market snapshot")
    monthly = WORKFLOW.index("Build actual 10Y monthly withdrawal rankings")
    recession = WORKFLOW.index("Build recession-balanced 10Y rankings")
    assert audit < persist < monthly < recession


def test_core_25y_files_are_in_first_checkpoint():
    for token in [
        "data/default_universe.csv",
        "data/market_snapshot.csv",
        "data/snapshot_metadata.json",
        "data/universe_metadata.json",
        "data/monthly_returns_10y.csv",
    ]:
        assert token in WORKFLOW


def test_rankings_have_separate_second_checkpoint():
    assert "Persist refreshed ranking data" in WORKFLOW
    for token in [
        "data/top100_rebalanced_monthly_withdrawal_10y_no_hwm.csv",
        "data/top100_not_rebalanced_monthly_withdrawal_10y_no_hwm.csv",
        "data/top100_recession_balanced_rebalanced_10y.csv",
        "data/top100_recession_balanced_not_rebalanced_10y.csv",
    ]:
        assert token in WORKFLOW


def test_persistence_helper_retries_concurrent_main_updates():
    assert "MAX_ATTEMPTS" in PERSIST
    assert "git fetch --no-tags origin main" in PERSIST
    assert "git reset --hard origin/main" in PERSIST
    assert "git push origin HEAD:main" in PERSIST
    assert "Push was rejected because main changed concurrently" in PERSIST
    assert 'cp -p "$TEMP_DIR/$file" "$file"' in PERSIST


def test_25y_generation_still_uses_2000_anchor():
    assert "MARKETSCOPE_ANNUAL_HISTORY_START: 2000-01-01" in WORKFLOW
    assert "python scripts/validate_25y_snapshot.py" in WORKFLOW
