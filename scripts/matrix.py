"""Preserve all eleven upstream release jobs, including compatibility variants."""
import json
import sys

TARGETS = [
    {'id': f'{platform}-{arch}', 'platform': platform, 'arch': arch, 'os': runner}
    for platform, runner, arches in (
        ('windows', 'windows-latest', ('x64', 'ia32', 'arm64')),
        ('windows7', 'windows-latest', ('x64', 'ia32')),
        ('linux', 'ubuntu-latest', ('x64', 'arm64')),
        ('macos', 'macos-latest', ('x64', 'arm64')),
        ('macos10', 'macos-latest', ('x64', 'arm64')),
    ) for arch in arches
]


def select(target):
    if target not in ('all', 'windows', 'windows7', 'linux', 'macos', 'macos10'):
        raise ValueError('Unknown build target')
    return {'include': [item for item in TARGETS if target in ('all', item['platform'])]}


if __name__ == '__main__':
    print('matrix=' + json.dumps(select(sys.argv[1] if len(sys.argv) > 1 else 'all'), separators=(',', ':')))
