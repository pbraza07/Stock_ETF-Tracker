#!/usr/bin/env python3
"""Repair MarketScope v5.10.2 deployments missing legacy projection modules."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

V5101_COMMIT = "db83002526931db6271b25fcabbeb7800d4f151b"
TARGET_VERSION = "5.10.2"


def run(*args: str, cwd: Path, capture: bool = True) -> str:
    proc = subprocess.run(
        list(args), cwd=cwd, text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{detail}")
    return (proc.stdout or "").strip()


def git_file(repo: Path, commit: str, path: str) -> str:
    return run("git", "show", f"{commit}:{path}", cwd=repo)


def main() -> None:
    requested = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    try:
        repo = Path(run("git", "rev-parse", "--show-toplevel", cwd=requested)).resolve()
    except Exception as exc:
        raise SystemExit(f"ERROR: Run this from inside your MarketScope Git repository.\n{exc}")

    engine = repo / "future_projection.py"
    ui = repo / "future_projection_ui.py"
    if not engine.exists() or not ui.exists():
        raise SystemExit("ERROR: future_projection.py or future_projection_ui.py is missing. This is not the MarketScope repository root.")

    engine_text = engine.read_text(encoding="utf-8")
    ui_text = ui.read_text(encoding="utf-8")
    if "import future_projection_legacy as _legacy" not in engine_text:
        raise SystemExit("ERROR: current future_projection.py is not the v5.10.2 compatibility wrapper. No hotfix applied.")
    if "import future_projection_ui_legacy as _legacy" not in ui_text:
        raise SystemExit("ERROR: current future_projection_ui.py is not the v5.10.2 compatibility wrapper. No hotfix applied.")

    try:
        original_engine = git_file(repo, V5101_COMMIT, "future_projection.py") + "\n"
        original_ui = git_file(repo, V5101_COMMIT, "future_projection_ui.py") + "\n"
    except Exception as exc:
        raise SystemExit(
            "ERROR: Could not read the v5.10.1 source commit from local Git history.\n"
            "Run: git fetch --all --prune\nThen run this hotfix again.\n\n" + str(exc)
        )

    legacy_engine = repo / "future_projection_legacy.py"
    legacy_ui = repo / "future_projection_ui_legacy.py"

    # Never overwrite unrelated files silently.
    if legacy_engine.exists() and legacy_engine.read_text(encoding="utf-8") != original_engine:
        raise SystemExit("ERROR: future_projection_legacy.py already exists but does not match v5.10.1. No files changed.")
    if legacy_ui.exists() and legacy_ui.read_text(encoding="utf-8") != original_ui:
        raise SystemExit("ERROR: future_projection_ui_legacy.py already exists but does not match v5.10.1. No files changed.")

    legacy_engine.write_text(original_engine, encoding="utf-8")
    legacy_ui.write_text(original_ui, encoding="utf-8")
    (repo / "VERSION.txt").write_text(TARGET_VERSION + "\n", encoding="utf-8")

    # Validate imports/syntax before telling the user to deploy.
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile",
         str(engine), str(ui), str(legacy_engine), str(legacy_ui)],
        cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise SystemExit("ERROR: Python syntax validation failed:\n" + (proc.stderr or proc.stdout))

    print("SUCCESS: MarketScope v5.10.2 legacy-module hotfix installed.")
    print("Created/verified:")
    print("  future_projection_legacy.py  <- exact v5.10.1 engine")
    print("  future_projection_ui_legacy.py <- exact v5.10.1 UI")
    print("Updated:")
    print("  VERSION.txt -> 5.10.2")
    print("\nNow run:")
    print("  git add future_projection_legacy.py future_projection_ui_legacy.py VERSION.txt")
    print('  git commit -m "Fix MarketScope v5.10.2 missing legacy projection modules"')
    print("  git push origin main")
    print("\nRender should auto-deploy the corrected commit.")


if __name__ == "__main__":
    main()
