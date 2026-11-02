"""Fetch a reviewed upstream ref and its pinned submodules without build credentials."""
import json
from pathlib import Path
import re
import subprocess


def checkout(lock, target):
    target = Path(target)
    if target.exists():
        raise ValueError('Refusing to overwrite an existing source directory')
    if not re.fullmatch(r'[0-9a-f]{40}', lock['commit']):
        raise ValueError('Expected a full source commit')
    if not lock['repository'].startswith(('https://', '/')):
        raise ValueError('Expected an HTTPS source repository')
    subprocess.run(['git', 'init', '-q', str(target)], check=True)
    git = ['git', '-C', str(target)]
    subprocess.run([*git, 'config', 'core.autocrlf', 'false'], check=True)
    subprocess.run([*git, 'remote', 'add', 'origin', lock['repository']], check=True)
    subprocess.run([*git, 'fetch', '--depth=1', 'origin', lock['ref']], check=True)
    actual = subprocess.check_output([*git, 'rev-parse', 'FETCH_HEAD^{commit}'], text=True).strip()
    if actual != lock['commit']:
        raise ValueError('Upstream ref moved; review the source and patch before upgrading')
    subprocess.run([*git, 'checkout', '--detach', actual], check=True)
    subprocess.run([*git, '-c', 'url.https://github.com/.insteadOf=git@github.com:',
                    'submodule', 'update', '--init', '--recursive'], check=True)
    print(f"Source: {lock['name']} {lock['ref']} {actual}")


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    checkout(json.loads((root / 'sources.lock.json').read_text()), root / 'source')
