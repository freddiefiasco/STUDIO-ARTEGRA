"""Make a DEVELOPER build of this tree for the engine proof (engine design section 3, G0g): a copy of the source tree whose
service/build_channel.py says CHANNEL = 'dev' (and, optionally, the sizes its proof runs may admit). Never packaged: the
release build (tools/build_release.py) refuses a tree whose channel is not 'release'.

    python tools/make_dev_build.py <destination folder> [--proven ws128=640,pc64=160]"""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPY = ('host', 'ui', 'service', 'engine', 'node_pack', 'runtime', 'tests', 'tools', 'cu_service.py', 'support_bundle.py',
        'pyproject.toml', 'uv.lock', 'models.manifest.json', 'asset-hashes.json')
RELEASE_LINES = "CHANNEL = 'release'\nDEV_PROVEN_MP = None\n"


def channel_source(proven=None):
    return "CHANNEL = 'dev'\n" + (f'DEV_PROVEN_MP = {dict(proven)!r}\n' if proven else 'DEV_PROVEN_MP = None\n')


def make(dest, proven=None):
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(f'{dest} is not empty')
    dest.mkdir(parents=True, exist_ok=True)
    for name in COPY:
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, dest / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.local'))
        elif src.exists():
            shutil.copy2(src, dest / name)
    p = dest / 'service' / 'build_channel.py'
    text = p.read_text(encoding='utf8')
    head, sep, tail = text.partition(RELEASE_LINES)
    if not sep:
        raise SystemExit('service/build_channel.py does not have the release lines this tool replaces')
    p.write_text(head + channel_source(proven) + tail, encoding='utf8')
    return dest


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('dest')
    ap.add_argument('--proven', default='')
    a = ap.parse_args(argv)
    proven = dict((k, float(v)) for k, v in (x.split('=') for x in a.proven.split(',') if x)) if a.proven else None
    print(make(a.dest, proven))


if __name__ == '__main__':
    sys.exit(main())
