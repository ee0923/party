"""Apply reviewed compatibility transforms, then detect tracked-source changes by build scripts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tracked(source):
    names = subprocess.check_output(['git', '-C', str(source), 'ls-files', '-z']).decode().split('\0')
    return [name for name in names if name]


def hashes(source, names):
    result = {}
    for name in names:
        path = source / name
        if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()) or not path.is_file():
            raise ValueError('Unsafe or missing source input: ' + name)
        result[name] = sha(path)
    return result


def configure(root, platform, arch, resolve=True):
    valid = {'windows': ('x64', 'ia32', 'arm64'), 'windows7': ('x64', 'ia32'),
             'linux': ('x64', 'arm64'), 'macos': ('x64', 'arm64'), 'macos10': ('x64', 'arm64')}
    if platform not in valid or arch not in valid[platform]:
        raise ValueError('Unknown compatibility target')
    state_path = root / 'source-state.json'
    if state_path.exists():
        raise ValueError('Refusing to replace an existing source snapshot')
    source = root / 'source'
    before = hashes(source, tracked(source))
    builder = source / 'electron-builder.yml'
    text = builder.read_text()
    if platform == 'linux':
        text = text.replace('productName: Clash Party', 'productName: clash-party')
    if platform == 'windows7':
        text = text.replace('windows', 'win7')
    if platform == 'macos10':
        text = text.replace('macos', 'catalina')
    builder.write_text(text)
    if platform in ('windows7', 'macos10'):
        manifest = source / 'package.json'
        package = json.loads(manifest.read_text())
        package['devDependencies']['electron'] = '22.3.27' if platform == 'windows7' else '32.2.2'
        if platform == 'windows7':
            package['type'] = 'commonjs'
        manifest.write_text(json.dumps(package, indent=2, ensure_ascii=False) + '\n')
        expected = hashes(source, before)
        if resolve:
            subprocess.run(['pnpm', 'install', '--lockfile-only', '--ignore-scripts', '--no-frozen-lockfile'],
                           cwd=source, check=True, shell=sys.platform == 'win32')
        actual = hashes(source, before)
        if any(actual[name] != digest for name, digest in expected.items() if name != 'pnpm-lock.yaml'):
            raise ValueError('Dependency resolution changed source outside its lockfile')
    after = hashes(source, before)
    permitted = {'electron-builder.yml', 'package.json', 'pnpm-lock.yaml'}
    if any(after[name] != digest for name, digest in before.items() if name not in permitted):
        raise ValueError('Compatibility preparation changed unexpected source files')
    lock = json.loads((root / 'sources.lock.json').read_text())
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if head != lock['commit']:
        raise ValueError('Source HEAD does not match the reviewed commit')
    state = {'platform': platform, 'arch': arch, 'source_commit': head, 'files': after}
    state_path.write_text(json.dumps(state, indent=2) + '\n')
    return state


def verify(root):
    state = json.loads((root / 'source-state.json').read_text())
    source = root / 'source'
    if set(tracked(source)) != set(state['files']) or hashes(source, state['files']) != state['files']:
        raise ValueError('Build scripts changed reviewed source or dependencies')
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if head != state['source_commit']:
        raise ValueError('Source commit changed during build')
    return state


if __name__ == '__main__':
    if sys.argv[1:] == ['--verify']:
        verify(ROOT)
        print('All tracked source and dependency hashes verified')
    else:
        configure(ROOT, *sys.argv[1:])
