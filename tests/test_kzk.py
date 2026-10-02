import os
import random
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from kozaky import kzk
from kozaky.nds import crc16


def fake_rom(body, code=b'YG8P', padding=0):
    head = bytearray(0x200)
    head[0:12] = b'YU-GI-OH!WC8'
    head[12:16] = code
    struct.pack_into('<I', head, 0x80, 0x200 + len(body))
    struct.pack_into('<H', head, 0x15E, crc16(head[:0x15E]))
    return bytes(head) + body + b'\xff' * padding


class PatchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rnd = random.Random(7)
        cls.body = bytes(rnd.getrandbits(8) for _ in range(200_000))
        b = bytearray(cls.body)
        b[1000:1004] = b'EDIT'
        moved = bytes(b[50_000:60_000])
        del b[50_000:60_000]
        b[120_000:120_000] = moved
        b[150_000:150_000] = bytes(rnd.getrandbits(8) for _ in range(3000))
        del b[170_000:171_000]
        cls.clean = fake_rom(cls.body, padding=4096)
        cls.modded = fake_rom(bytes(b) + b'new tail data')
        cls.patch, cls.meta = kzk.make(cls.clean, cls.modded, 'test')

    def test_roundtrip_is_exact_and_small(self):
        self.assertEqual(kzk.apply(self.patch, self.clean), self.modded)
        self.assertLess(len(self.patch), 6000)

    def test_trimmed_source_gives_same_result(self):
        trimmed = self.clean[:0x200 + len(self.body)]
        self.assertEqual(kzk.apply(self.patch, trimmed), self.modded)

    def test_wrong_region_is_refused(self):
        with self.assertRaisesRegex(kzk.PatchRefused, 'YG8E'):
            kzk.apply(self.patch, fake_rom(self.body, code=b'YG8E'))

    def test_modified_source_is_refused(self):
        bad = bytearray(self.clean)
        bad[0x300] ^= 1
        with self.assertRaisesRegex(kzk.PatchRefused, 'clean dump'):
            kzk.apply(self.patch, bytes(bad))

    def test_already_patched_is_refused(self):
        with self.assertRaisesRegex(kzk.PatchRefused, 'already'):
            kzk.apply(self.patch, self.modded)


if __name__ == '__main__':
    unittest.main()
