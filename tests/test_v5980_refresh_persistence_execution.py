from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "update_market_snapshot.yml").read_text(encoding="utf-8")


def test_refresh_persistence_helper_does_not_require_executable_file_mode():
    invocations = [
        line.strip()
        for line in WORKFLOW.splitlines()
        if "scripts/persist_generated_files.sh" in line
    ]
    assert invocations
    assert all(line.startswith("bash scripts/persist_generated_files.sh") for line in invocations)


def test_monthly_rankings_are_checkpointed_before_recession_rankings():
    build = WORKFLOW.index("Build actual 10Y monthly withdrawal rankings")
    checkpoint = WORKFLOW.index("Persist actual 10Y monthly withdrawal rankings immediately")
    recession = WORKFLOW.index("Build recession-balanced 10Y rankings")
    assert build < checkpoint < recession

    checkpoint_block = WORKFLOW[checkpoint:recession]
    assert "data/top100_rebalanced_monthly_withdrawal_10y_no_hwm.csv" in checkpoint_block
    assert "data/top100_not_rebalanced_monthly_withdrawal_10y_no_hwm.csv" in checkpoint_block
