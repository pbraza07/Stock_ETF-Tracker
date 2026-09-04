from __future__ import annotations

import subprocess
import sys
from pathlib import Path

LEGACY_COMMIT = "db83002526931db6271b25fcabbeb7800d4f151b"

def run(cmd, cwd: Path, capture=True):
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=capture,
        shell=False,
    )

def find_repo(start: Path) -> Path | None:
    candidates = [
        start,
        start / "Stock_ETF-Tracker",
        Path.home() / "Desktop" / "Stock_ETF-Tracker",
        Path.home() / "Downloads" / "Stock_ETF-Tracker",
        Path.home() / "Documents" / "Stock_ETF-Tracker",
    ]
    for c in candidates:
        if (c / ".git").exists() and (c / "app.py").exists():
            return c.resolve()
    return None

def main():
    # Allow: python FIX_LEGACY_MODULES_ANYWHERE.py "C:\path\to\Stock_ETF-Tracker"
    if len(sys.argv) > 1:
        repo = Path(sys.argv[1].strip('"')).expanduser().resolve()
    else:
        repo = find_repo(Path.cwd())

    if repo is None or not (repo / ".git").exists() or not (repo / "app.py").exists():
        print("\nERROR: MarketScope Git repository not found.")
        print("\nRun this command and include the full folder path, for example:")
        print(r'  py FIX_LEGACY_MODULES_ANYWHERE.py "C:\Users\YOURNAME\Downloads\Stock_ETF-Tracker"')
        print("\nThe correct folder must contain at least:")
        print("  .git")
        print("  app.py")
        print("  future_projection.py")
        print("  future_projection_ui.py")
        sys.exit(2)

    print(f"\nUsing MarketScope repository:\n  {repo}\n")

    # Ensure the historical commit is available locally.
    probe = run(["git", "cat-file", "-e", f"{LEGACY_COMMIT}^{{commit}}"], repo)
    if probe.returncode != 0:
        print("Historical v5.10.1 commit is not available locally. Fetching origin...")
        fetch = run(["git", "fetch", "origin"], repo)
        if fetch.returncode != 0:
            print(fetch.stderr or fetch.stdout)
            print("\nERROR: Could not fetch GitHub history.")
            sys.exit(3)

    files = [
        ("future_projection.py", "future_projection_legacy.py"),
        ("future_projection_ui.py", "future_projection_ui_legacy.py"),
    ]

    for source, target in files:
        result = run(["git", "show", f"{LEGACY_COMMIT}:{source}"], repo)
        if result.returncode != 0:
            print(result.stderr or result.stdout)
            print(f"\nERROR: Could not recover {source} from v5.10.1 commit.")
            sys.exit(4)
        (repo / target).write_text(result.stdout, encoding="utf-8", newline="\n")
        print(f"Created {target}")

    (repo / "VERSION.txt").write_text("5.10.2\n", encoding="utf-8", newline="\n")
    print("Updated VERSION.txt -> 5.10.2")

    # Syntax-check all four projection modules.
    check_files = [
        "future_projection.py",
        "future_projection_legacy.py",
        "future_projection_ui.py",
        "future_projection_ui_legacy.py",
    ]
    check = run([sys.executable, "-m", "py_compile", *check_files], repo)
    if check.returncode != 0:
        print(check.stderr or check.stdout)
        print("\nERROR: Python syntax validation failed.")
        sys.exit(5)

    print("\nSUCCESS: Missing legacy modules were restored and syntax validation passed.")
    print("\nNext, run these commands from the MarketScope folder:")
    print("  git add future_projection_legacy.py future_projection_ui_legacy.py VERSION.txt")
    print('  git commit -m "Fix MarketScope v5.10.2 missing legacy projection modules"')
    print("  git push origin main")
    print("\nRender should redeploy automatically after the push.")

if __name__ == "__main__":
    main()
