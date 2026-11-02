"""Authenticate the exact Secret payload before executing it against locked source."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def payload():
    raw = os.environ.get('CLASH_PARTY_CUSTOMIZE_SCRIPT', '')
    if not raw.strip():
        raise ValueError('CLASH_PARTY_CUSTOMIZE_SCRIPT repository Secret is required')
    data = (raw.replace('\r\n', '\n').rstrip('\n') + '\n').encode()
    expected = (ROOT / 'customize.sha256').read_text().strip()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Customization Secret does not match this build snapshot')
    return data, expected


def main():
    data, digest = payload()
    if sys.argv[1:] == ['--check-secret']:
        print('Customization SHA-256: ' + digest)
        return
    verify_only = sys.argv[1:] == ['--verify']
    if sys.argv[1:] and not verify_only:
        raise ValueError('Usage: customize.py [--check-secret|--verify]')
    source = ROOT / 'source'
    lock = json.loads((ROOT / 'sources.lock.json').read_text())
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != lock['commit']:
        raise ValueError('Source HEAD does not match the reviewed commit')
    bash = os.environ['CLASH_PARTY_BASH']
    env = dict(os.environ, SOURCE=str(source))
    env.pop('CLASH_PARTY_CUSTOMIZE_SCRIPT', None)
    for mode in (('--verify',) if verify_only else ('apply', '--verify')):
        subprocess.run([bash, '-s', '--', mode], input=data, env=env, cwd=source, check=True)
    print('Verified customization SHA-256: ' + digest)


if __name__ == '__main__':
    try:
        main()
    except ValueError as error:
        print('::error::' + str(error), file=sys.stderr)
        raise SystemExit(1)
