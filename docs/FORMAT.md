# The .kzk format, version 1

All numbers are little endian.

| offset | size | field |
|---|---|---|
| 0 | 4 | magic `KZK\0` (`4B 5A 4B 00`) |
| 4 | 2 | format version, `1` |
| 6 | 2 | reserved, `0` |
| 8 | 4 | `N`, length of the metadata |
| 12 | `N` | metadata, UTF-8 JSON |
| 12 + `N` | rest of file | payload, one XZ stream |

A reader that finds a format version higher than it knows must refuse the file.

## Metadata

```json
{
 "format": 1,
 "name": "Tearlaments",
 "author": "someone",
 "version": "1.0",
 "description": "Tearlaments archetype",
 "game_name": "Yu-Gi-Oh! World Championship 2008",
 "source": {"code": "YG8P", "game": "wc2008", "region": "Europe", "rom_version": 0,
            "title": "YU-GI-OH!WC8", "size": 131373056, "sha1": "86c0d2b1..."},
 "target": {"code": "YG8P", "game": "wc2008", "region": "Europe", "rom_version": 0,
            "title": "YU-GI-OH!WC8", "size": 134217728, "sha1": "..."},
 "tool": "KozakyLab 0.1.0"
}
```

| field | meaning |
|---|---|
| `source.code` | game code, header bytes `0x0C`-`0x0F` |
| `source.rom_version` | header byte `0x1E` |
| `source.size` | ROM size from the header, u32 at `0x80` |
| `source.sha1` | SHA-1 of the first `source.size` bytes of the clean ROM |
| `target.size` | length of the output file |
| `target.sha1` | SHA-1 of the whole output file |

`game`, `region`, `title`, `game_name` and `tool` are for display. Readers ignore fields they don't know.

## Checks before applying

1. `code` and `rom_version` of the ROM equal `source.code` and `source.rom_version`. Otherwise: wrong game, region or revision.
2. If the ROM's SHA-1 (used area or whole file) equals `target.sha1`, the patch is already applied.
3. The SHA-1 of the ROM's first `size` bytes, `size` read from its own header at `0x80`, equals `source.sha1`. Otherwise: modified or bad dump.

Hashing only the used area lets trimmed and untrimmed dumps of the same ROM share one patch.

## Payload

The XZ stream decompresses to a list of commands, read until the end. The **source** is the ROM's first `source.size` bytes. The output starts empty, and `last` starts at 0.

Each command starts with an unsigned LEB128 varint `H`. `n = H >> 1`.

- `H & 1 == 0`, **insert**: the next `n` bytes of the stream are appended to the output.
- `H & 1 == 1`, **copy**: a second varint `Z` follows. `delta = Z >> 1` if `Z` is even, else `-((Z + 1) >> 1)`. `offset = last + delta`. Append `source[offset : offset + n]`, then `last = offset + n`. A copy outside the source is an error.

At the end the output length must equal `target.size` and its SHA-1 must equal `target.sha1`.

## How KozakyLab makes the commands

Not part of the format; any producer that writes valid commands is fine.

The modded ROM is split into regions: header, ARM9, ARM7, file name table, FAT, overlay tables, banner, and every file. Each region is matched to the same region of the clean ROM, by path for named files and by overlay id for overlays. Equal regions become one copy. Changed regions are diffed against their clean counterpart: 32-byte blocks of the clean region are indexed, every position of the modded region is looked up, and matches are extended in both directions. Bytes outside any region are copied when they equal the clean ROM at the same offset and inserted otherwise. If either ROM's file system can't be read, the whole ROM is diffed as one region.
