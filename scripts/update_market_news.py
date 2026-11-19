"""Refresh the HTML headline snapshot used by MarketScope."""
from pathlib import Path
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scraped_news import collect_pages

if __name__ == "__main__":
    path = ROOT / "data/web_headlines.json"
    previous = json.loads(path.read_text()) if path.exists() else {}
    result = collect_pages(previous)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    for site, entry in result.items():
        print(site, entry["status"], flush=True)
    if os.getenv("GITHUB_ACTIONS") == "true":
        def git(*args):
            subprocess.run(["git", *args], cwd=ROOT, check=True)
        git("add", "--", "data/web_headlines.json")
        git("-c", "user.name=github-actions[bot]", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "commit", "-m", "Refresh scraped MarketScope headlines [skip render]")
        git("pull", "--rebase", "origin", os.environ["GITHUB_REF_NAME"])
        git("push", "origin", "HEAD:" + os.environ["GITHUB_REF_NAME"])
