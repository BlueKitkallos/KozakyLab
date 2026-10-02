import hashlib
import struct

HEADER_SIZE = 0x200
BANNER_SIZES = {1: 0x840, 2: 0x940, 3: 0xA40, 0x103: 0x23C0}
BANNER_LANGS = ('Japanese', 'English', 'French', 'German', 'Italian', 'Spanish')


class RomError(Exception):
    pass


def u16(d, o):
    return struct.unpack_from('<H', d, o)[0]


def u32(d, o):
    return struct.unpack_from('<I', d, o)[0]


def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


class Rom:
    def __init__(self, data):
        if len(data) < HEADER_SIZE:
            raise RomError('file is too small to be a DS ROM')
        if crc16(data[:0x15E]) != u16(data, 0x15E):
            raise RomError('not a DS ROM (header checksum does not match)')
        self.data = data
        self.title = data[0:12].rstrip(b'\0').decode('latin1')
        self.code = data[12:16].decode('latin1')
        self.version = data[0x1E]
        self.used_size = u32(data, 0x80)
        if not HEADER_SIZE <= self.used_size <= 1 << 30:
            raise RomError(f'header gives a ROM size of {self.used_size:#x} bytes')

    @classmethod
    def load(cls, path):
        with open(path, 'rb') as f:
            return cls(f.read())

    @property
    def truncated(self):
        return len(self.data) < self.used_size

    def sha1(self):
        if self.truncated:
            raise RomError(f'ROM file is cut short: {len(self.data)} bytes, header says {self.used_size}')
        return hashlib.sha1(memoryview(self.data)[:self.used_size]).hexdigest()

    def _span(self, off_at, size_at):
        return u32(self.data, off_at), u32(self.data, size_at)

    def banner_titles(self):
        off = u32(self.data, 0x68)
        if not off or off + 0x840 > len(self.data):
            return {}
        out = {}
        for i, lang in enumerate(BANNER_LANGS):
            raw = self.data[off + 0x240 + i * 0x100:off + 0x340 + i * 0x100]
            text = raw.decode('utf-16-le', 'replace').split('\0')[0].strip()
            if text:
                out[lang] = text.replace('\n', ' / ')
        return out

    def fat(self):
        off, size = self._span(0x48, 0x4C)
        self._check(off, size, 'FAT')
        return [struct.unpack_from('<II', self.data, off + i * 8) for i in range(size // 8)]

    def overlays(self, which):
        off, size = self._span(0x50, 0x54) if which == 9 else self._span(0x58, 0x5C)
        self._check(off, size, f'ARM{which} overlay table')
        out = []
        for i in range(size // 32):
            e = off + i * 32
            ov_id, file_id, comp = u32(self.data, e), u32(self.data, e + 0x18), u32(self.data, e + 0x1C)
            out.append((ov_id, file_id, bool(comp >> 24 & 1)))
        return out

    def paths(self):
        fnt, size = self._span(0x40, 0x44)
        self._check(fnt, size, 'FNT')
        d = self.data
        names = {}
        stack = [(0xF000, '')]
        seen = set()
        while stack:
            dir_id, prefix = stack.pop()
            if dir_id in seen or len(seen) > 0x1000:
                raise RomError('file name table loops')
            seen.add(dir_id)
            entry = fnt + (dir_id & 0xFFF) * 8
            sub, fid = fnt + u32(d, entry), u16(d, entry + 4)
            while True:
                if sub >= fnt + size:
                    raise RomError('file name table runs past its end')
                ln = d[sub]
                sub += 1
                if ln == 0:
                    break
                name = d[sub:sub + (ln & 0x7F)].decode('latin1')
                sub += ln & 0x7F
                if ln & 0x80:
                    stack.append((u16(d, sub), prefix + name + '/'))
                    sub += 2
                else:
                    names[fid] = prefix + name
                    fid += 1
        return names

    def files(self):
        fat = self.fat()
        paths = self.paths()
        keys = {}
        for which in (9, 7):
            for ov_id, fid, _ in self.overlays(which):
                keys[fid] = (f'ov{which}:{ov_id}', f'overlay{which}/overlay{which}_{ov_id:04d}.bin')
        out = []
        for fid, (start, end) in enumerate(fat):
            if fid in paths:
                key, path = 'file:' + paths[fid], 'data/' + paths[fid]
            else:
                key, path = keys.get(fid, (f'fid:{fid}', f'unnamed/file_{fid:04d}.bin'))
            if end < start:
                raise RomError(f'FAT entry {fid} ends before it starts')
            out.append((key, path, start, end - start))
        return out

    def sections(self):
        d = self.data
        out = [('header', 0, HEADER_SIZE)]
        for key, o, s in (('arm9', 0x20, 0x2C), ('arm7', 0x30, 0x3C), ('fnt', 0x40, 0x44),
                          ('fat', 0x48, 0x4C), ('ov9', 0x50, 0x54), ('ov7', 0x58, 0x5C)):
            off, size = self._span(o, s)
            if size:
                self._check(off, size, key)
                out.append((key, off, size))
        banner = u32(d, 0x68)
        if banner:
            self._check(banner, 2, 'banner')
            size = BANNER_SIZES.get(u16(d, banner), 0x840)
            self._check(banner, size, 'banner')
            out.append(('banner', banner, size))
        out += [(key, off, size) for key, _, off, size in self.files() if size]
        return out

    def _check(self, off, size, what):
        if off + size > len(self.data):
            raise RomError(f'{what} at {off:#x}+{size:#x} lies past the end of the file')


def blz_decompress(data):
    if len(data) < 8:
        return bytes(data)
    end_info, extra = struct.unpack_from('<II', data, len(data) - 8)
    if extra == 0:
        return bytes(data)
    hdr_len, comp_len = end_info >> 24, end_info & 0xFFFFFF
    if comp_len > len(data) or hdr_len < 8:
        raise RomError('bad code compression footer')
    out = bytearray(len(data) + extra)
    out[:len(data)] = data
    src, stop, dst = len(data) - hdr_len, len(data) - comp_len, len(out)
    while src > stop:
        src -= 1
        flags = out[src]
        for _ in range(8):
            if src <= stop:
                break
            if flags & 0x80:
                b1, b2 = out[src - 1], out[src - 2]
                src -= 2
                disp = ((b1 & 0x0F) << 8 | b2) + 3
                for _ in range((b1 >> 4) + 3):
                    dst -= 1
                    out[dst] = out[dst + disp]
            else:
                src -= 1
                dst -= 1
                out[dst] = out[src]
            flags <<= 1
    return bytes(out)
