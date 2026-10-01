"""Publish validated generated files on latest remote head without rebasing them."""
from pathlib import Path
from datetime import datetime
import json
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from macro_snapshots import validate_snapshot

SERIES = ('USPHCI', 'RECPROUSM156N', 'SAHMREALTIME')


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    if result.returncode:
        # Git remote errors can contain credentials; do not echo raw output.
        raise RuntimeError('Git '+args[0]+' failed; check repository write permissions and branch rules')
    return result.stdout.strip()


def read(path, key):
    try:
        return validate_snapshot(json.loads(path.read_text()), key)
    except (OSError, ValueError, KeyError, TypeError, AssertionError):
        return None


def publish(repo, branch='main', attempts=4):
    repo = Path(repo).resolve()
    candidates = {key: read(repo/'data/macro_snapshots'/f'{key}.json', key) for key in SERIES}
    candidates = {key: value for key,value in candidates.items() if value is not None}
    if not candidates:
        print('No valid local snapshots to publish; remote files unchanged.')
        return
    for attempt in range(attempts):
        git(repo, 'fetch', 'origin', branch)
        with tempfile.TemporaryDirectory(prefix='marketscope-macro-') as temporary:
            worktree = Path(temporary)/'publish'
            git(repo, 'worktree', 'add', '--detach', str(worktree), 'FETCH_HEAD')
            try:
                changed = []
                for key, value in candidates.items():
                    relative = f'data/macro_snapshots/{key}.json'
                    path = worktree/relative
                    current = read(path, key)
                    if current and datetime.fromisoformat(current['retrieved_at']) >= datetime.fromisoformat(value['retrieved_at']):
                        continue
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
                    changed.append(relative)
                if not changed:
                    print('Remote snapshots already as recent or newer; nothing to publish.')
                    return
                git(worktree, 'add', '--', *changed)
                git(worktree, '-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com', 'commit', '-m', 'Refresh macro snapshots [skip render]')
                try:
                    git(worktree, 'push', 'origin', 'HEAD:refs/heads/'+branch)
                    print('Published '+str(len(changed))+' validated snapshots.')
                    return
                except RuntimeError:
                    if attempt + 1 == attempts:
                        raise
                    print('Push did not complete; retrying against latest remote head.')
            finally:
                # Only remove the temporary worktree created by this invocation.
                git(repo, 'worktree', 'remove', '--force', str(worktree))


if __name__ == '__main__':
    publish(Path(__file__).resolve().parents[1])
