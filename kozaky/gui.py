import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from . import __version__, kzk
from .cli import default_output, patch_summary, rom_summary
from .kzk import PatchError
from .nds import Rom, RomError

ROM_TYPES = [('DS ROM', '*.nds *.srl'), ('All files', '*')]
KZK_TYPES = [('KozakyLab patch', '*.kzk'), ('All files', '*')]


def _read(path):
    with open(path, 'rb') as f:
        return f.read()


class App:
    def __init__(self, root):
        self.root = root
        self.jobs = queue.Queue()
        self.a_meta = self.a_suggested = None
        root.title(f'KozakyLab {__version__}')
        root.minsize(560, 0)
        tabs = ttk.Notebook(root)
        tabs.pack(fill='both', expand=True, padx=8, pady=8)
        tabs.add(self._apply_tab(tabs), text='Apply patch')
        tabs.add(self._make_tab(tabs), text='Make patch')
        self.root.after(100, self._poll)

    def _file_row(self, parent, row, label, var, types, save=False, on_pick=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', pady=2)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky='ew', padx=4)

        def pick():
            ask = filedialog.asksaveasfilename if save else filedialog.askopenfilename
            path = ask(filetypes=types)
            if path:
                var.set(path)
                if on_pick:
                    on_pick(path)
        ttk.Button(parent, text='Browse', command=pick).grid(row=row, column=2)

    def _apply_tab(self, tabs):
        f = ttk.Frame(tabs, padding=8)
        f.columnconfigure(1, weight=1)
        self.a_patch, self.a_rom, self.a_out = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self._file_row(f, 0, 'Patch (.kzk)', self.a_patch, KZK_TYPES, on_pick=self._show_patch)
        self.a_patch_info = ttk.Label(f, justify='left', wraplength=520)
        self.a_patch_info.grid(row=1, column=1, columnspan=2, sticky='w', pady=(0, 6))
        self._file_row(f, 2, 'Clean ROM', self.a_rom, ROM_TYPES, on_pick=self._show_rom)
        self.a_rom_info = ttk.Label(f, justify='left', wraplength=520)
        self.a_rom_info.grid(row=3, column=1, columnspan=2, sticky='w', pady=(0, 6))
        self._file_row(f, 4, 'Save as', self.a_out, ROM_TYPES, save=True)
        self.a_button = ttk.Button(f, text='Patch ROM', command=self._apply)
        self.a_button.grid(row=5, column=1, sticky='w', pady=8)
        self.a_status = ttk.Label(f, justify='left', wraplength=520)
        self.a_status.grid(row=6, column=0, columnspan=3, sticky='w')
        return f

    def _make_tab(self, tabs):
        f = ttk.Frame(tabs, padding=8)
        f.columnconfigure(1, weight=1)
        self.m_clean, self.m_mod, self.m_out = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.m_name, self.m_author, self.m_version = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self._file_row(f, 0, 'Clean ROM', self.m_clean, ROM_TYPES)
        self._file_row(f, 1, 'Modded ROM', self.m_mod, ROM_TYPES)
        self._file_row(f, 2, 'Save patch as', self.m_out, KZK_TYPES, save=True)
        for row, (label, var) in enumerate((('Mod name', self.m_name), ('Author', self.m_author),
                                            ('Version', self.m_version)), start=3):
            ttk.Label(f, text=label).grid(row=row, column=0, sticky='w', pady=2)
            ttk.Entry(f, textvariable=var).grid(row=row, column=1, columnspan=2, sticky='ew', padx=4)
        ttk.Label(f, text='Description').grid(row=6, column=0, sticky='nw', pady=2)
        self.m_desc = tk.Text(f, height=4, width=40, wrap='word')
        self.m_desc.grid(row=6, column=1, columnspan=2, sticky='ew', padx=4)
        self.m_button = ttk.Button(f, text='Make patch', command=self._make)
        self.m_button.grid(row=7, column=1, sticky='w', pady=8)
        self.m_status = ttk.Label(f, justify='left', wraplength=520)
        self.m_status.grid(row=8, column=0, columnspan=3, sticky='w')
        return f

    def _show_patch(self, path):
        try:
            meta, _ = kzk.read(_read(path))
        except (OSError, PatchError) as e:
            self.a_patch_info['text'] = str(e)
            return
        self.a_patch_info['text'] = patch_summary(meta)
        self.a_meta = meta
        self._suggest_output()

    def _show_rom(self, path):
        try:
            self.a_rom_info['text'] = rom_summary(Rom.load(path))
        except (OSError, RomError) as e:
            self.a_rom_info['text'] = str(e)
        self._suggest_output()

    def _suggest_output(self):
        if self.a_rom.get() and self.a_meta and self.a_out.get() in ('', self.a_suggested):
            self.a_suggested = default_output(self.a_rom.get(), self.a_meta)
            self.a_out.set(self.a_suggested)

    def _run(self, button, status, work):
        button['state'] = 'disabled'
        status['text'] = 'Working...'

        def job():
            try:
                msg = work()
            except (OSError, PatchError, RomError) as e:
                msg = f'Error: {e}'
            self.jobs.put((button, status, msg))
        threading.Thread(target=job, daemon=True).start()

    def _poll(self):
        while not self.jobs.empty():
            button, status, msg = self.jobs.get()
            button['state'] = 'normal'
            status['text'] = msg
        self.root.after(100, self._poll)

    def _apply(self):
        patch, rom, out = self.a_patch.get(), self.a_rom.get(), self.a_out.get()
        if not (patch and rom and out):
            self.a_status['text'] = 'Pick a patch, a clean ROM and where to save.'
            return

        def work():
            result = kzk.apply(_read(patch), _read(rom))
            with open(out, 'wb') as f:
                f.write(result)
            return f'Done: {out}'
        self._run(self.a_button, self.a_status, work)

    def _make(self):
        clean, mod, out = self.m_clean.get(), self.m_mod.get(), self.m_out.get()
        if not (clean and mod and out):
            self.m_status['text'] = 'Pick the clean ROM, the modded ROM and where to save.'
            return
        name = self.m_name.get() or os.path.splitext(os.path.basename(out))[0]
        author, version, desc = self.m_author.get(), self.m_version.get(), self.m_desc.get('1.0', 'end').strip()

        def work():
            src = _read(clean)
            patch, _ = kzk.make(src, _read(mod), name, author, version, desc)
            with open(out, 'wb') as f:
                f.write(patch)
            msg = f'Done: {out} ({len(patch):,} bytes)'
            if not kzk.known_dump(Rom(src)):
                msg += '\nThe clean ROM is not a known dump: players need this exact file.'
            return msg
        self._run(self.m_button, self.m_status, work)


def run():
    root = tk.Tk(className='KozakyLab')
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        root.iconphoto(True, tk.PhotoImage(file=os.path.join(base, 'assets', 'icon.png')))
    except tk.TclError:
        pass
    App(root)
    root.mainloop()
