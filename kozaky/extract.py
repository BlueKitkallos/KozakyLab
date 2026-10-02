import os
import struct

from .nds import Rom, blz_decompress, u32


def pac_files(d):
    if len(d) < 0x200:
        raise ValueError('too small')
    nblocks = d[2]
    names_end = struct.unpack_from('<H', d, 0)[0] if nblocks == 0 else nblocks * 0x200
    names = []
    for b in range(max(1, nblocks)):
        p = b * 0x200 + 3
        while p < min(names_end, (b + 1) * 0x200) and d[p] != 0:
            n = d[p]
            names.append(d[p + 2:p + 2 + n].decode('latin1'))
            p += 2 + n
    if not names:
        raise ValueError('no names')
    n = len(names)
    ents = [struct.unpack_from('<II', d, names_end + (i // 63) * 0x200 + 8 + (i % 63) * 8) for i in range(n)]
    base = (names_end + ((n - 1) // 63) * 0x200 + 8 + ((n - 1) % 63 + 1) * 8 + 0x1FF) & ~0x1FF
    out = {}
    for name, (off, size) in zip(names, ents):
        if base + off + size > len(d) or not name.isprintable() or '/' in name or name in ('.', '..'):
            raise ValueError('entry out of range')
        out[name] = bytes(d[base + off:base + off + size])
    return out


def _write(root, rel, data):
    path = os.path.join(root, *rel.split('/'))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)


def extract(rom_path, out, raw=False, log=print):
    rom = Rom.load(rom_path)
    d = rom.data
    for key, off, size in rom.sections():
        if key in ('header', 'arm9', 'arm7', 'banner', 'ov9', 'ov7'):
            name = {'ov9': 'y9.bin', 'ov7': 'y7.bin'}.get(key, key + '.bin')
            _write(out, name, d[off:off + size])
    arm9_end = u32(d, 0x20) + u32(d, 0x2C)
    if d[arm9_end:arm9_end + 4] == bytes.fromhex('2106c0de'):
        _write(out, 'arm9_footer.bin', d[arm9_end:arm9_end + 12])
    compressed = {fid for which in (9, 7) for _, fid, comp in rom.overlays(which) if comp}
    count = pacs = 0
    for fid, (key, path, off, size) in enumerate(rom.files()):
        blob = d[off:off + size]
        if fid in compressed and not raw:
            blob = blz_decompress(blob)
        if path.lower().endswith('.pac') and not raw:
            try:
                inner = pac_files(blob)
            except (ValueError, struct.error, IndexError):
                inner = None
            if inner is not None:
                for name, data in inner.items():
                    _write(out, path[:-4] + '/' + name, data)
                pacs += 1
                count += len(inner)
                continue
        _write(out, path, blob)
        count += 1
    log(f'{count} files written to {out} ({pacs} .pac archives unpacked, '
        f'{0 if raw else len(compressed)} overlays decompressed)')
    return count

