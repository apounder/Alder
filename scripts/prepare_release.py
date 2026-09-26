"""Collect only complete, checksum-verified desktop downloads for a GitHub release."""
import hashlib
from pathlib import Path
import shutil
import sys
import tomllib


def collect(source, destination, version):
    assets, expected = {}, {}
    for manifest in source.rglob('*SHA256SUMS.txt'):
        for line in manifest.read_text(encoding='utf-8').splitlines():
            digest, name = line.split(maxsplit=1)
            name = name.strip()
            if Path(name).name != name or not name.startswith(f'Alder-{version}-'):
                raise ValueError(f'Unexpected release filename: {name}')
            if name in expected and expected[name] != digest:
                raise ValueError(f'Conflicting checksums for {name}')
            expected[name] = digest
    for name, digest in expected.items():
        matches = list(source.rglob(name))
        if not matches:
            raise ValueError(f'Missing download: {name}')
        for path in matches:
            with path.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                    raise ValueError(f'Checksum mismatch: {name}')
        assets[name] = matches[0]
    for suffix in ('Windows-x64-GUI-Setup.exe', 'macOS-AppleSilicon.dmg',
                   'macOS-Intel.dmg', 'Linux-x64.deb', 'Linux-arm64.deb'):
        if f'Alder-{version}-{suffix}' not in assets:
            raise ValueError(f'Release is incomplete: missing {suffix}')
    destination.mkdir(parents=True, exist_ok=False)
    for name, source_path in assets.items():
        shutil.copy2(source_path, destination / name)
    (destination / 'SHA256SUMS.txt').write_text(''.join(
        f'{expected[name]}  {name}\n' for name in sorted(assets)), encoding='utf-8')
    return list(assets)


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    files = collect(Path(sys.argv[1]), Path(sys.argv[2]), version)
    print(f'Verified {len(files)} desktop downloads for Alder {version}')
