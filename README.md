# KozakyLab

Share Yu-Gi-Oh! DS mods as small `.kzk` patches. Players apply them to their own ROM.

Works with Nightmare Troubadour, GX Spirit Caller and World Championship 2007 to 2011, in every region they were released in. `python3 kozakylab.py games` lists the game codes.

No ROMs are included.

## Download

Get the latest version from the [Releases](https://github.com/BlueKitkallos/KozakyLab/releases) page: `KozakyLab-windows.zip`, `KozakyLab-macos.zip` or `KozakyLab-linux.tar.gz`. Unpack it and double-click KozakyLab. Nothing to install.

Windows may warn that the app is from an unknown publisher: click "More info", then "Run anyway". On macOS, right-click the app and choose Open the first time.

## From source

Needs Python 3.8+. On Linux, also `python3-tk`.

Run `kozakylab.py` with no arguments to open the window, or from a terminal:

```
python3 kozakylab.py apply mod.kzk clean.nds        # patch a ROM
python3 kozakylab.py make clean.nds modded.nds -o mod.kzk --name "My Mod" --author me --version 1.0
python3 kozakylab.py info rom.nds                   # game, region, clean dump or not (also works on a .kzk)
python3 kozakylab.py extract rom.nds out/           # files, overlays, unpacked .pac archives
```

A patch only applies to the ROM it was made from: same game, region, revision and clean dump. A trimmed dump counts as the same ROM. The patched ROM is checked against the modder's before it is saved.

## More

- `docs/FORMAT.md`: the `.kzk` format
- Tests: `python3 -m unittest discover -s tests`

## Legal

KozakyLab is an unofficial fan project, made for free and not sold. It is not affiliated with, endorsed, sponsored or approved by Konami, Konami Digital Entertainment, Kazuki Takahashi, Studio Dice, Shueisha, Nintendo, or anyone else holding rights to Yu-Gi-Oh! or the Nintendo DS.

Yu-Gi-Oh!, the game titles, card names, card art, characters and logos are trademarks and copyrights of their owners. Nintendo DS is a trademark of Nintendo. 

This repository contains no ROMs, game code, card data, art, music or text from any game. 

A `.kzk` patch holds the differences between a clean ROM and a modded one, made by whoever built the mod. Modders are responsible for making sure their patches contain only work they have the right to share. Players are responsible for what they apply. 

The software is provided as is, without warranty of any kind, under the MIT license (see `LICENSE`). The authors are not liable for any damage to files, saves or hardware, or for how anyone uses the tool or the patches made with it.
