"""Require complete current-run packages, retaining compatibility names and provenance."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

import variant

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def names(platform, arch, version):
    if platform in ('windows', 'windows7'):
        prefix = 'win7' if platform == 'windows7' else 'windows'
        endings = ['-setup.exe', '-portable.7z']
    elif platform in ('macos', 'macos10'):
        prefix = 'catalina' if platform == 'macos10' else 'macos'
        endings = ['.pkg']
    elif platform == 'linux':
        target_arches = {'x64': ('amd64', 'x86_64', 'x64'), 'arm64': ('arm64', 'aarch64', 'aarch64')}
        if arch not in target_arches:
            raise ValueError('Unknown Linux package architecture')
        return [f'clash-party-linux-{version}-{a}{suffix}' for a, suffix in
                zip(target_arches[arch], ('.deb', '.rpm', '.pkg.tar.zst'))]
    else:
        raise ValueError('Unknown package platform')
    return [f'clash-party-{prefix}-{version}-{arch}{ending}' for ending in endings]


def collect(root):
    state = variant.verify(root)
    source = root / 'source'
    platform, arch = state['platform'], state['arch']
    version = json.loads((source / 'package.json').read_text())['version']
    packages = []
    for name in names(platform, arch, version):
        path = source / 'dist' / name
        if not path.is_file() or path.is_symlink() or not path.stat().st_size:
            raise ValueError('Missing or empty package: ' + name)
        packages.append(path)
    destination = root / 'dist'
    destination.mkdir(exist_ok=False)
    files = []
    for path in packages:
        digest = sha(path)
        for name in (path.name, path.name.replace('clash-party', 'mihomo-party', 1)):
            shutil.copyfile(path, destination / name)
            (destination / (name + '.sha256')).write_text(digest + '\n')
            files.append({'name': name, 'size': path.stat().st_size, 'sha256': digest})
    info = {
        'source': json.loads((root / 'sources.lock.json').read_text()),
        'customization_sha256': (root / 'customize.sha256').read_text().strip(),
        'platform': platform, 'arch': arch,
        'dependency_lock_sha256': sha(source / 'pnpm-lock.yaml'),
        'tracked_source_sha256': state['files'],
        'downloaded_resources_sha256': {str(p.relative_to(source)): sha(p)
            for p in (source / 'extra').rglob('*') if p.is_file() and not p.is_symlink()},
        'build_repository': os.environ.get('GITHUB_REPOSITORY'), 'build_commit': os.environ.get('GITHUB_SHA'),
        'run_id': os.environ.get('GITHUB_RUN_ID'), 'run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
        'macos_signing': os.environ.get('MACOS_SIGNING', 'unsigned') if platform.startswith('macos') else 'not-applicable',
        'files': files,
    }
    identity = platform + '-' + arch
    (destination / f'build-info-{identity}.json').write_text(json.dumps(info, indent=2) + '\n')
    (destination / f'pnpm-lock-{identity}.yaml').write_bytes((source / 'pnpm-lock.yaml').read_bytes())
    (destination / f'SHA256SUMS-{identity}.txt').write_text(''.join(f"{f['sha256']}  {f['name']}\n" for f in files))
    return info


if __name__ == '__main__':
    collect(ROOT)
