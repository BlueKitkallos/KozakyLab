import argparse
import os
import sys

from . import __version__, kzk
from .extract import extract
from .games import GAMES, KNOWN_DUMPS, REGIONS, describe, supported
from .kzk import PatchError
from .nds import Rom, RomError


def _read(path):
    try:
        with open(path, 'rb') as f:
            return f.read()
    except OSError as e:
        raise SystemExit(f'cannot read {path}: {e.strerror}')


def _write(path, data):
    try:
        with open(path, 'wb') as f:
            f.write(data)
    except OSError as e:
        raise SystemExit(f'cannot write {path}: {e.strerror}')


def _progress(done, total):
    print(f'\r  {done * 100 // max(total, 1):3d}%', end='', file=sys.stderr, flush=True)
    if done >= total:
        print(file=sys.stderr)


def patch_summary(meta):
    s = meta['source']
    lines = [f"{meta['name']}" + (f" {meta['version']}" if meta.get('version') else '')]
    if meta.get('author'):
        lines.append(f"by {meta['author']}")
    lines.append(f"for {describe(s['code'], s['rom_version'])}")
    if meta.get('description'):
        lines.append(meta['description'])
    return '\n'.join(lines)


def rom_summary(rom):
    lines = [describe(rom.code, rom.version)]
    if not supported(rom.code):
        lines.append('not a game KozakyLab knows; patches still work, names may be missing')
    titles = rom.banner_titles()
    if titles:
        lines.append('banner: ' + titles.get('English', next(iter(titles.values()))))
    size = f'{rom.used_size:,} bytes used, file {len(rom.data):,}'
    if rom.truncated:
        size += ' (CUT SHORT)'
    elif len(rom.data) > rom.used_size:
        size += ' (untrimmed)'
    lines.append(size)
    if not rom.truncated:
        lines.append(f'SHA-1 {rom.sha1()}' + (' (known clean dump)' if kzk.known_dump(rom) else ''))
    return '\n'.join(lines)


def cmd_info(a):
    data = _read(a.file)
    if data[:4] == kzk.MAGIC:
        meta, start = kzk.read(data)
        print(patch_summary(meta))
        print(f"patch {len(data):,} bytes, result {meta['target']['size']:,} bytes, made with {meta['tool']}")
        return
    print(rom_summary(Rom(data)))


def cmd_games(a):
    for base, (key, name) in GAMES.items():
        codes = sorted({c for c in KNOWN_DUMPS.values() if c.startswith(base)}, key=lambda c: 'JEPK'.index(c[3]))
        print(f'{key:8} {name}: ' + ', '.join(f'{c} {REGIONS[c[3]]}' for c in codes))


def cmd_make(a):
    src, tgt = _read(a.clean), _read(a.modded)
    name = a.name or os.path.splitext(os.path.basename(a.out))[0]
    print(f'diffing {a.modded} against {a.clean}', file=sys.stderr)
    patch, _ = kzk.make(src, tgt, name, a.author, a.version, a.description, _progress)
    if not kzk.known_dump(Rom(src)):
        print('warning: the clean ROM is not a dump KozakyLab recognises; players need this exact file',
              file=sys.stderr)
    _write(a.out, patch)
    print(f"{a.out}: {len(patch):,} bytes, checked: it rebuilds {a.modded} exactly")


def default_output(rom_path, meta):
    stem = os.path.splitext(rom_path)[0]
    tag = meta['name'] + (f" {meta['version']}" if meta.get('version') else '')
    return f'{stem} [{tag}].nds'


def cmd_apply(a):
    patch, rom = _read(a.patch), _read(a.rom)
    meta, _ = kzk.read(patch)
    print(patch_summary(meta), file=sys.stderr)
    out = a.out or default_output(a.rom, meta)
    result = kzk.apply(patch, rom)
    _write(out, result)
    print(f'{out}: patched and verified')


def cmd_extract(a):
    extract(a.rom, a.outdir, a.raw)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        from .gui import run
        return run()
    ap = argparse.ArgumentParser(prog='kozakylab', description='Yu-Gi-Oh! DS ROM patcher and extractor. '
                                 'Run with no arguments for the window.')
    ap.add_argument('--version', action='version', version=f'KozakyLab {__version__}')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('apply', help='apply a .kzk patch to a clean ROM')
    p.add_argument('patch')
    p.add_argument('rom')
    p.add_argument('-o', '--out', help='output ROM (default: "<rom> [<patch name>].nds" next to the ROM)')
    p.set_defaults(fn=cmd_apply)

    p = sub.add_parser('make', help='make a .kzk patch from a clean ROM and a modded ROM')
    p.add_argument('clean')
    p.add_argument('modded')
    p.add_argument('-o', '--out', required=True, help='patch file to write (.kzk)')
    p.add_argument('--name', help='mod name (default: output file name)')
    p.add_argument('--author', default='')
    p.add_argument('--version', dest='version', default='', help='mod version, e.g. 1.0')
    p.add_argument('--description', default='')
    p.set_defaults(fn=cmd_make)

    p = sub.add_parser('info', help='describe a ROM or a .kzk patch')
    p.add_argument('file')
    p.set_defaults(fn=cmd_info)

    p = sub.add_parser('extract', help='unpack a ROM: header, ARM binaries, overlays, files, .pac archives')
    p.add_argument('rom')
    p.add_argument('outdir')
    p.add_argument('--raw', action='store_true', help='keep .pac archives and compressed overlays as they are')
    p.set_defaults(fn=cmd_extract)

    p = sub.add_parser('games', help='list supported games and their game codes')
    p.set_defaults(fn=cmd_games)

    a = ap.parse_args(argv)
    try:
        a.fn(a)
    except (PatchError, RomError) as e:
        raise SystemExit(f'error: {e}')
