import hashlib
import json
import lzma
import struct

from . import __version__
from .games import KNOWN_DUMPS, describe, identify
from .nds import Rom, RomError

MAGIC = b'KZK\0'
FORMAT = 1
BLOCK = 32
CHUNK = 1 << 12


class PatchError(Exception):
    pass


class PatchRefused(PatchError):
    pass


def _varint(n, out):
    while n >= 0x80:
        out.append(n & 0x7F | 0x80)
        n >>= 7
    out.append(n)


def _read_varint(buf, pos):
    n = shift = 0
    while True:
        if pos >= len(buf):
            raise PatchError('patch data ends in the middle of a command')
        b = buf[pos]
        pos += 1
        n |= (b & 0x7F) << shift
        if b < 0x80:
            return n, pos
        shift += 7


def _match_len(a, ai, ae, b, bi, be):
    n = min(ae - ai, be - bi)
    lo, step = 0, CHUNK
    while lo < n:
        k = min(step, n - lo)
        if a[ai + lo:ai + lo + k] == b[bi + lo:bi + lo + k]:
            lo += k
            step = min(step * 2, 1 << 22)
            continue
        while k > 1:
            h = k // 2
            if a[ai + lo:ai + lo + h] == b[bi + lo:bi + lo + h]:
                lo += h
                k -= h
            else:
                k = h
        return lo
    return lo


class _Ops:
    def __init__(self, tgt):
        self.tgt = tgt
        self.ops = []

    def copy(self, src_off, n):
        if n <= 0:
            return
        if self.ops and self.ops[-1][0] == 'C' and self.ops[-1][1] + self.ops[-1][2] == src_off:
            self.ops[-1] = ('C', self.ops[-1][1], self.ops[-1][2] + n)
        else:
            self.ops.append(('C', src_off, n))

    def insert(self, start, end):
        if end <= start:
            return
        if self.ops and self.ops[-1][0] == 'I' and self.ops[-1][2] == start:
            self.ops[-1] = ('I', self.ops[-1][1], end)
        else:
            self.ops.append(('I', start, end))

    def encode(self):
        out = bytearray()
        last = 0
        for kind, a, b in self.ops:
            if kind == 'C':
                _varint(b << 1 | 1, out)
                rel = a - last
                _varint(rel << 1 if rel >= 0 else (-rel << 1) - 1, out)
                last = a + b
            else:
                _varint((b - a) << 1, out)
                out += self.tgt[a:b]
        return bytes(out)


def _delta(src, sb, se, tgt, tb, te, ops):
    index = {}
    for i in range(se - BLOCK - (se - BLOCK - sb) % BLOCK, sb - 1, -BLOCK):
        index[src[i:i + BLOCK]] = i
    p = lit = tb
    s_at_lit = sb
    while p + BLOCK <= te:
        guess = s_at_lit + (p - lit)
        window = tgt[p:p + BLOCK]
        if sb <= guess and guess + BLOCK <= se and src[guess:guess + BLOCK] == window:
            cand = guess
        else:
            cand = index.get(window)
            if cand is None:
                p += 1
                continue
        back = 0
        while p - back > lit and cand - back > sb and tgt[p - back - 1] == src[cand - back - 1]:
            back += 1
        n = BLOCK + back + _match_len(src, cand + BLOCK, se, tgt, p + BLOCK, te)
        ops.insert(lit, p - back)
        ops.copy(cand - back, n)
        p = lit = p - back + n
        s_at_lit = cand - back + n
    ops.insert(lit, te)


def _same(src, s_end, tgt, off, end):
    return end <= s_end and src[off:end] == tgt[off:end]


def _plan(src_rom, tgt_rom, progress):
    src, tgt = src_rom.data, tgt_rom.data
    s_end, t_end = src_rom.used_size, len(tgt)
    try:
        theirs = {k: (o, o + n) for k, o, n in src_rom.sections()}
        mine = sorted(tgt_rom.sections(), key=lambda s: (s[1], -s[2]))
    except (RomError, struct.error, IndexError, UnicodeDecodeError):
        theirs, mine = {'rom': (0, s_end)}, [('rom', 0, t_end)]
    ops = _Ops(tgt)

    def fill(off, end):
        if _same(src, s_end, tgt, off, end):
            ops.copy(off, end - off)
        else:
            ops.insert(off, end)

    cursor = 0
    for key, off, size in mine:
        end = min(off + size, t_end)
        off = max(off, cursor)
        if end <= off:
            continue
        if off > cursor:
            fill(cursor, off)
        so, se = theirs.get(key, (0, 0))
        se = min(se, s_end)
        if se - so == end - off and src[so:se] == tgt[off:end]:
            ops.copy(so, se - so)
        elif se > so:
            _delta(src, so, se, tgt, off, end, ops)
        else:
            fill(off, end)
        cursor = end
        if progress:
            progress(cursor, t_end)
    if cursor < t_end:
        fill(cursor, t_end)
    if progress:
        progress(t_end, t_end)
    return ops


def _rom_info(rom, sha1, size):
    g = identify(rom.code)
    return {'code': rom.code, 'game': g['game'], 'region': g['region'], 'rom_version': rom.version,
            'title': rom.title, 'size': size, 'sha1': sha1}


def make(src_data, tgt_data, name, author='', version='', description='', progress=None):
    src, tgt = Rom(src_data), Rom(tgt_data)
    src_sha1 = src.sha1()
    if src_data == tgt_data:
        raise PatchError('the two ROMs are identical')
    if src.code != tgt.code:
        raise PatchError(f'the two ROMs are different games: {describe(src.code, src.version)} '
                         f'and {describe(tgt.code, tgt.version)}')
    ops = _plan(src, tgt, progress)
    payload = lzma.compress(ops.encode(), format=lzma.FORMAT_XZ, preset=9 | lzma.PRESET_EXTREME)
    meta = {
        'format': FORMAT,
        'name': name,
        'author': author,
        'version': version,
        'description': description,
        'game_name': identify(src.code)['name'],
        'source': _rom_info(src, src_sha1, src.used_size),
        'target': _rom_info(tgt, hashlib.sha1(tgt_data).hexdigest(), len(tgt_data)),
        'tool': f'KozakyLab {__version__}',
    }
    raw = json.dumps(meta, ensure_ascii=False, indent=1).encode('utf-8')
    patch = MAGIC + struct.pack('<HHI', FORMAT, 0, len(raw)) + raw + payload
    if apply(patch, src_data) != tgt_data:
        raise PatchError('internal error: the patch does not rebuild the modded ROM')
    return patch, meta


def read(patch):
    if patch[:4] != MAGIC:
        raise PatchError('not a .kzk patch')
    fmt, _, n = struct.unpack_from('<HHI', patch, 4)
    if fmt > FORMAT:
        raise PatchError(f'patch format {fmt} needs a newer KozakyLab (this one reads up to {FORMAT})')
    try:
        meta = json.loads(patch[12:12 + n].decode('utf-8'))
    except ValueError:
        raise PatchError('patch header is damaged')
    return meta, 12 + n


def check(meta, rom):
    want, have = meta['source'], rom
    if (want['code'], want['rom_version']) != (have.code, have.version):
        raise PatchRefused(f"This patch is for {describe(want['code'], want['rom_version'])}.\n"
                           f'Your ROM is {describe(have.code, have.version)}.')
    sha1 = rom.sha1()
    if sha1 == meta['target']['sha1'] or hashlib.sha1(rom.data).hexdigest() == meta['target']['sha1']:
        raise PatchRefused('This ROM already has this patch applied.')
    if sha1 != want['sha1']:
        raise PatchRefused('Your ROM is the right game and region, but not the clean dump this patch was made '
                           f"from.\nExpected SHA-1 {want['sha1']}, yours is {sha1}.\n"
                           'It may be already modified or a bad dump.')
    return sha1


def apply(patch, rom_data):
    meta, start = read(patch)
    rom = Rom(rom_data)
    check(meta, rom)
    try:
        stream = lzma.decompress(patch[start:], format=lzma.FORMAT_XZ)
    except lzma.LZMAError:
        raise PatchError('patch data is damaged')
    src = memoryview(rom_data)[:rom.used_size]
    out = bytearray()
    pos = last = 0
    while pos < len(stream):
        head, pos = _read_varint(stream, pos)
        n = head >> 1
        if head & 1:
            z, pos = _read_varint(stream, pos)
            off = last + (z >> 1 if not z & 1 else -((z + 1) >> 1))
            if off < 0 or off + n > len(src):
                raise PatchError('patch copies from outside the ROM')
            out += src[off:off + n]
            last = off + n
        else:
            if pos + n > len(stream):
                raise PatchError('patch data ends in the middle of a command')
            out += stream[pos:pos + n]
            pos += n
    if len(out) != meta['target']['size'] or hashlib.sha1(out).hexdigest() != meta['target']['sha1']:
        raise PatchError('patched ROM does not match the expected result')
    return bytes(out)


def known_dump(rom):
    if rom.truncated:
        return False
    return rom.sha1() in KNOWN_DUMPS or hashlib.sha1(rom.data).hexdigest() in KNOWN_DUMPS
