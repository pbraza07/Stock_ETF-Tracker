"""Create an upgrade-safe repository-root release; leave durable user data intact."""

from pathlib import Path
import argparse
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LIVE_FILES = {
    "data/market_snapshot.csv",
    "data/snapshot_metadata.json",
    "data/saved_portfolio_simulations.json",
    "data/favorite_picks_history.json",
    "data/top12_recession_history.json",
    "data/top12_max_profit_history.json",
    "data/universe_change_history.json",
}
SKIP_DIRS = {
    ".git",
    ".cache",
    ".pytest_cache",
    "__pycache__",
    ".venv",
    "generated_pdfs",
}


def stage(destination):
    destination = Path(destination).resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise ValueError("Release staging must be outside the source tree.")
    destination.mkdir(parents=True, exist_ok=False)
    for source in sorted(ROOT.rglob("*")):
        relative = source.relative_to(ROOT)
        if not source.is_file() or source.is_symlink():
            continue
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if str(relative) in LIVE_FILES or source.name in {".env", "secrets.toml"}:
            continue
        if source.suffix in {".pyc", ".zip", ".tmp", ".log"}:
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return destination


def archive(staged, output):
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for source in sorted(Path(staged).rglob("*")):
            if (
                source.is_file()
                and not any(
                    part in SKIP_DIRS for part in source.relative_to(staged).parts
                )
                and source.suffix != ".pyc"
            ):
                zf.write(source, str(source.relative_to(staged)))
    with zipfile.ZipFile(output) as zf:
        assert zf.testzip() is None
        assert {"app.py", "requirements.txt", "VERSION.txt", "render.yaml"} <= set(
            zf.namelist()
        )
        assert not LIVE_FILES.intersection(zf.namelist())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("staging")
    parser.add_argument("output")
    args = parser.parse_args()
    archive(stage(args.staging), args.output)
