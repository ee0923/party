"""Publish one validated target immediately, independently of the other matrix jobs."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(root, identity, env):
    lock = json.loads((root / 'sources.lock.json').read_text())
    app = {'FlClash': 'flclash', 'Clash Party': 'clash-party'}[lock['name']]
    version = lock['ref'].removeprefix('v')
    if not re.fullmatch(r'[0-9][0-9A-Za-z.+-]*', version):
        raise ValueError('Invalid locked release version')
    targets = {'flclash': {'android-all', *(f'{p}-{a}' for p in ('linux', 'macos', 'windows') for a in ('amd64', 'arm64'))},
               'clash-party': {*(f'{p}-{a}' for p in ('linux', 'macos', 'macos10', 'windows', 'windows7') for a in ('x64', 'arm64')), 'windows-ia32', 'windows7-ia32'}}
    # The upstream Win7 matrix has no arm64 target.
    targets['clash-party'].discard('windows7-arm64')
    if identity not in targets[app]:
        raise ValueError('Unknown package target')
    if not env.get('GH_TOKEN') or env.get('GH_REPO') != env.get('GITHUB_REPOSITORY'):
        raise ValueError('Token and current build repository are required')
    if not re.fullmatch(r'[0-9a-f]{40}', env.get('GITHUB_SHA', '')) or not env.get('GITHUB_RUN_ID'):
        raise ValueError('Current build identity is required')
    dist = root / 'dist'
    if dist.is_symlink():
        raise ValueError('Package directory must not be a symlink')
    info_name = f'build-info-{identity}.json'
    manifest_name = f'SHA256SUMS-{identity}.txt'
    # Reject symlinks and directories before reading or publishing any file.
    if any(p.is_symlink() or not p.is_file() for p in dist.iterdir()):
        raise ValueError('Only regular package files may be published')
    info = json.loads((dist / info_name).read_text())
    if (info['source'] != lock or info['platform'] + '-' + info['arch'] != identity
            or info['customization_sha256'] != (root / 'customize.sha256').read_text().strip()
            or info['build_repository'] != env['GH_REPO'] or info['build_commit'] != env['GITHUB_SHA']
            or str(info['run_id']) != env['GITHUB_RUN_ID']
            or str(info['run_attempt']) != env.get('GITHUB_RUN_ATTEMPT', '1')):
        raise ValueError('Package provenance does not match this run')
    packages = {}
    for line in (dist / manifest_name).read_text().splitlines():
        digest, name = line.split('  ', 1)
        if (not re.fullmatch(r'[0-9a-f]{64}', digest) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+_-]*', name)
                or name in packages or sha(dist / name) != digest):
            raise ValueError('Invalid or changed package checksum')
        packages[name] = digest
    records = info['files']
    if not packages or len(records) != len(packages) or {p['name']: p['sha256'] for p in records} != packages:
        raise ValueError('Manifest does not match package provenance')
    if any((dist / p['name']).stat().st_size != p['size'] or p['size'] <= 0 for p in records):
        raise ValueError('Empty or changed package')
    allowed = set(packages) | {info_name, manifest_name}
    if app == 'flclash':
        locks = ('pubspec.lock', 'core/go.sum', 'plugins/rust_api/rust/Cargo.lock', 'services/helper/Cargo.lock')
        if set(info['dependency_lock_sha256']) != set(locks):
            raise ValueError('Incomplete dependency lock provenance')
        for source in locks:
            name = f'lock-{identity}-' + source.replace('/', '_')
            if sha(dist / name) != info['dependency_lock_sha256'][source]:
                raise ValueError('Dependency lock changed')
            allowed.add(name)
    else:
        name = f'pnpm-lock-{identity}.yaml'
        if sha(dist / name) != info['dependency_lock_sha256']:
            raise ValueError('Dependency lock changed')
        allowed.add(name)
        for package, digest in packages.items():
            name = package + '.sha256'
            if (dist / name).read_text() != digest + '\n':
                raise ValueError('Compatibility checksum changed')
            allowed.add(name)
    if {p.name for p in dist.iterdir()} != allowed:
        raise ValueError('Unexpected files in package directory')
    return app + '-v' + version, [dist / name for name in sorted(allowed)]


def publish(root, identity, env):
    tag, files = validate(root, identity, env)
    repo = env['GH_REPO']
    def gh(*args):
        return subprocess.run(['gh', 'release', *args, '--repo', repo], env=env, check=False).returncode == 0
    for attempt in range(1, 6):
        if (gh('view', tag) or gh('create', tag, '--target', env['GITHUB_SHA'], '--prerelease',
                                '--title', tag, '--notes', 'Custom build. Source, customization, signing mode and package hashes are included in build-info files.')):
            if gh('upload', tag, *(str(path) for path in files), '--clobber'):
                return
        if attempt < 5:
            time.sleep(attempt * 5)
    raise RuntimeError('Release publication failed after 5 attempts')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: publish-release.py PLATFORM-ARCH')
    publish(Path(__file__).resolve().parents[1], sys.argv[1], dict(os.environ))
