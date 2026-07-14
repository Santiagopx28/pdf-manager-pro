"""
PDF Manager - Herramienta completa para gestión de archivos PDF
Funciones: Organizar, Comprimir, Reordenar, Eliminar páginas, Separar PDFs
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
import subprocess
import shutil
import glob
import time
import io
import tempfile
from pathlib import Path
import sys
from pypdf import PdfReader, PdfWriter

try:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.units import cm as CM_TO_PT
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

# ──────────────────────────────────────────────
#  VERSION
# ──────────────────────────────────────────────
VERSION = "1.1.4"

try:
    from updater import check_for_updates
    HAS_UPDATER = True
except ImportError:
    HAS_UPDATER = False


# ──────────────────────────────────────────────
#  PALETA DE COLORES
# ──────────────────────────────────────────────
BG       = "#1E1E2E"
PANEL    = "#2A2A3E"
ACCENT   = "#7C6AF7"
ACCENT2  = "#A78BFA"
SUCCESS  = "#22C55E"
DANGER   = "#EF4444"
WARNING  = "#F59E0B"
TEXT     = "#E2E8F0"
SUBTEXT  = "#94A3B8"
BORDER   = "#3A3A5C"
WHITE    = "#FFFFFF"
HOVER    = "#6D5CE6"


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text   = text
        self.tip    = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _=None):
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, background="#2D2D42",
                 foreground=TEXT, relief="flat", padx=8, pady=4,
                 font=("Segoe UI", 9)).pack()

    def hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class PDFManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF Manager Pro")
        self.geometry("980x680")
        self.minsize(820, 580)
        self.configure(bg=BG)
        self.resizable(True, True)

        # Centrar ventana
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"980x680+{(sw-980)//2}+{(sh-680)//2}")

        self._build_ui()

    # ── Construcción del UI ──────────────────────
    def _build_ui(self):
        # Barra de título personalizada
        header = tk.Frame(self, bg=PANEL, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="📄", font=("Segoe UI Emoji", 22),
                 bg=PANEL, fg=ACCENT2).pack(side="left", padx=(18, 6), pady=10)
        tk.Label(header, text="PDF Manager Pro", font=("Segoe UI", 16, "bold"),
                 bg=PANEL, fg=WHITE).pack(side="left", pady=10)
        tk.Label(header, text="Organiza · Comprime · Separa · Edita tus PDFs",
                 font=("Segoe UI", 9), bg=PANEL, fg=SUBTEXT).pack(side="left", padx=14, pady=10)

        # Contenedor principal
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=0, pady=0)

        # Sidebar de pestañas
        sidebar = tk.Frame(main, bg=PANEL, width=190)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="HERRAMIENTAS", font=("Segoe UI", 8, "bold"),
                 bg=PANEL, fg=SUBTEXT).pack(pady=(20, 8), padx=16, anchor="w")

        # Área de contenido
        self.content = tk.Frame(main, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)

        # Barra de estado
        self.status_var = tk.StringVar(value="Listo")
        status_bar = tk.Frame(self, bg=PANEL, height=30)
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)
        tk.Label(status_bar, textvariable=self.status_var,
                 bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9),
                 anchor="w").pack(side="left", padx=14, fill="y")

        self.progress = ttk.Progressbar(status_bar, length=160, mode="indeterminate")
        self.progress.pack(side="right", padx=14, pady=6)

        # Construir pestañas
        self.frames = {}
        tabs = [
            ("🔗  Unir PDFs",       "merge",    self._build_merge),
            ("⚫  Blanco y Negro",  "bw",       self._build_bw),
            ("✂️  Separar PDF",     "split",    self._build_split),
            ("🗑️  Eliminar páginas","delete",   self._build_delete),
            ("🔀  Reordenar",       "reorder",  self._build_reorder),
            ("🗜️  Comprimir",       "compress", self._build_compress),
            ("🔄  Rotar páginas",   "rotate",   self._build_rotate),
            ("📑  Foliación",       "foliate",  self._build_foliate),
        ]

        self.active_btn = None
        self.btn_refs   = {}

        for label, key, builder in tabs:
            fr = tk.Frame(self.content, bg=BG)
            self.frames[key] = fr
            builder(fr)

            btn = tk.Button(
                sidebar, text=label, anchor="w",
                font=("Segoe UI", 10), relief="flat", cursor="hand2",
                bg=PANEL, fg=TEXT, activebackground=ACCENT,
                activeforeground=WHITE, bd=0,
                command=lambda k=key: self._show_tab(k)
            )
            btn.pack(fill="x", padx=8, pady=2, ipady=8)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=HOVER) if b != self.active_btn else None)
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=PANEL) if b != self.active_btn else None)
            self.btn_refs[key] = btn

        self._show_tab("merge")

    def _show_tab(self, key):
        for k, fr in self.frames.items():
            fr.pack_forget()
        self.frames[key].pack(fill="both", expand=True)

        if self.active_btn:
            self.active_btn.config(bg=PANEL, fg=TEXT)
        btn = self.btn_refs[key]
        btn.config(bg=ACCENT, fg=WHITE)
        self.active_btn = btn

    # ── Helpers visuales ─────────────────────────
    def _card(self, parent, title, subtitle=""):
        outer = tk.Frame(parent, bg=BG)
        outer.pack(fill="both", expand=True, padx=24, pady=20)

        tk.Label(outer, text=title, font=("Segoe UI", 15, "bold"),
                 bg=BG, fg=WHITE).pack(anchor="w")
        if subtitle:
            tk.Label(outer, text=subtitle, font=("Segoe UI", 9),
                     bg=BG, fg=SUBTEXT).pack(anchor="w", pady=(2, 12))
        else:
            tk.Label(outer, text="", bg=BG).pack(pady=4)

        card = tk.Frame(outer, bg=PANEL, bd=0,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True)
        return outer, card

    def _btn(self, parent, text, cmd, color=ACCENT, icon=""):
        full = f"{icon}  {text}" if icon else text
        b = tk.Button(parent, text=full, command=cmd,
                      bg=color, fg=WHITE, relief="flat", cursor="hand2",
                      font=("Segoe UI", 10, "bold"), padx=18, pady=8,
                      activebackground=HOVER, activeforeground=WHITE, bd=0)
        b.bind("<Enter>", lambda e: b.config(bg=HOVER if color == ACCENT else color))
        b.bind("<Leave>", lambda e: b.config(bg=color))
        return b

    def _listbox(self, parent, height=8, expand=True):
        frame = tk.Frame(parent, bg=BORDER, bd=1)
        sb = tk.Scrollbar(frame, bg=PANEL)
        lb = tk.Listbox(frame, selectmode="extended", bg="#1A1A2E",
                        fg=TEXT, selectbackground=ACCENT, selectforeground=WHITE,
                        font=("Segoe UI", 10), relief="flat", bd=0,
                        activestyle="none", height=height,
                        yscrollcommand=sb.set)
        sb.config(command=lb.yview)
        sb.pack(side="right", fill="y")
        lb.pack(fill="both", expand=True, padx=2, pady=2)
        frame.pack(fill="both" if expand else "x", expand=expand, padx=16, pady=(2, 4) if not expand else 8)
        return lb

    def _set_status(self, msg, color=SUBTEXT):
        self.status_var.set(f"  {msg}")

    def _run_threaded(self, fn):
        self.progress.start(10)
        def wrapper():
            try:
                fn()
            finally:
                self.after(0, self.progress.stop)
        threading.Thread(target=wrapper, daemon=True).start()

    # ══════════════════════════════════════════════
    #  TAB 1 – UNIR PDFs
    # ══════════════════════════════════════════════
    def _build_merge(self, parent):
        _, card = self._card(parent,
            "🔗  Unir PDFs",
            "Combina múltiples archivos PDF en uno solo")

        tk.Label(card, text="Archivos seleccionados (en orden):",
                 bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(14, 2))
        self.merge_lb = self._listbox(card, height=10)

        btn_row = tk.Frame(card, bg=PANEL)
        btn_row.pack(fill="x", padx=16, pady=(0, 10))

        self._btn(btn_row, "Agregar PDFs", self._merge_add, icon="➕").pack(side="left", padx=(0, 6))
        self._btn(btn_row, "↑ Subir",  self._merge_up,   color="#475569").pack(side="left", padx=3)
        self._btn(btn_row, "↓ Bajar",  self._merge_down, color="#475569").pack(side="left", padx=3)
        self._btn(btn_row, "Quitar",   self._merge_remove, color=DANGER).pack(side="left", padx=3)
        self._btn(btn_row, "Limpiar",  lambda: self.merge_lb.delete(0, "end"), color="#374151").pack(side="left", padx=3)

        sep = tk.Frame(card, bg=BORDER, height=1)
        sep.pack(fill="x", padx=16, pady=6)

        action_row = tk.Frame(card, bg=PANEL)
        action_row.pack(fill="x", padx=16, pady=(0, 16))
        self._btn(action_row, "Unir y Guardar", self._merge_run, icon="💾").pack(side="left")
        self._btn(action_row, "Convertir a Blanco y Negro",
                  lambda: self._show_tab("bw"), color="#475569", icon="⚫").pack(side="left", padx=(10, 0))

    def _merge_add(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF", "*.pdf")])
        for f in files:
            self.merge_lb.insert("end", f)

    def _merge_up(self):
        sel = self.merge_lb.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        val = self.merge_lb.get(i)
        self.merge_lb.delete(i)
        self.merge_lb.insert(i - 1, val)
        self.merge_lb.selection_set(i - 1)

    def _merge_down(self):
        sel = self.merge_lb.curselection()
        if not sel or sel[0] >= self.merge_lb.size() - 1:
            return
        i = sel[0]
        val = self.merge_lb.get(i)
        self.merge_lb.delete(i)
        self.merge_lb.insert(i + 1, val)
        self.merge_lb.selection_set(i + 1)

    def _merge_remove(self):
        for i in reversed(self.merge_lb.curselection()):
            self.merge_lb.delete(i)

    def _merge_run(self):
        items = list(self.merge_lb.get(0, "end"))
        if not items:
            messagebox.showwarning("Aviso", "Agrega al menos un archivo PDF.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".pdf",
                                           filetypes=[("PDF", "*.pdf")],
                                           title="Guardar PDF unido como...")
        if not out:
            return
        def do():
            try:
                writer = PdfWriter()
                total = 0
                for path in items:
                    reader = PdfReader(path)
                    for page in reader.pages:
                        writer.add_page(page)
                        total += 1
                with open(out, "wb") as f:
                    writer.write(f)
                self.after(0, lambda: messagebox.showinfo("✅ Éxito",
                    f"PDF unido correctamente.\n{len(items)} archivos · {total} páginas\n\n{out}"))
                self._set_status(f"PDF unido: {Path(out).name}")
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
        self._run_threaded(do)

    # ══════════════════════════════════════════════
    #  TAB 1B – BLANCO Y NEGRO (escala de grises)
    # ══════════════════════════════════════════════
    def _build_bw(self, parent):
        _, card = self._card(parent,
            "⚫  Blanco y Negro",
            "Convierte todo el contenido del PDF (texto e imágenes) a escala de grises")

        top = tk.Frame(card, bg=PANEL)
        top.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(top, text="Archivo PDF:", bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9)).pack(anchor="w")
        row = tk.Frame(top, bg=PANEL)
        row.pack(fill="x", pady=4)
        self.bw_path = tk.StringVar()
        tk.Entry(row, textvariable=self.bw_path, state="readonly",
                 bg="#1A1A2E", fg=TEXT, relief="flat", font=("Segoe UI", 10),
                 readonlybackground="#1A1A2E").pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self._btn(row, "Abrir", self._bw_open, icon="📂").pack(side="left")

        self.bw_info = tk.Label(card, text="", bg=PANEL, fg=ACCENT2, font=("Segoe UI", 9))
        self.bw_info.pack(anchor="w", padx=16)

        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", padx=16, pady=10)

        gs = self._find_ghostscript()
        gs_color = SUCCESS if gs else WARNING
        gs_msg   = ("✅  Ghostscript detectado — conversión a blanco y negro disponible"
                    if gs else
                    "⚠️  Ghostscript NO instalado. Esta función lo requiere para convertir\n"
                    "    texto e imágenes a escala de grises de forma fiel.\n"
                    "    Descárgalo gratis: ghostscript.com/releases  (~30 MB)")
        tk.Label(card, text=gs_msg, bg=PANEL, fg=gs_color,
                 font=("Segoe UI", 9), wraplength=530, justify="left").pack(anchor="w", padx=16)

        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", padx=16, pady=10)

        self.bw_run_btn = self._btn(card, "Convertir y Guardar", self._bw_run, icon="⚫")
        self.bw_run_btn.pack(anchor="w", padx=16, pady=(0, 16))
        if not gs:
            self.bw_run_btn.config(state="disabled")

    def _bw_open(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if f:
            self.bw_path.set(f)
            n = PdfReader(f).get_num_pages()
            self.bw_info.config(text=f"  📄 {n} páginas  ·  {Path(f).name}")

    def _bw_run(self):
        path = self.bw_path.get()
        if not path:
            messagebox.showwarning("Aviso", "Selecciona un archivo PDF.")
            return
        gs = self._find_ghostscript()
        if not gs:
            messagebox.showerror("Error", "Ghostscript no está instalado. Es necesario para esta función.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".pdf",
                                           filetypes=[("PDF", "*.pdf")],
                                           title="Guardar PDF en blanco y negro como...")
        if not out:
            return

        def do():
            try:
                cmd = [
                    gs, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
                    "-sColorConversionStrategy=Gray", "-dProcessColorModel=/DeviceGray",
                    "-dNOPAUSE", "-dBATCH",
                    f"-sOutputFile={out}", path,
                ]
                result = subprocess.run(cmd, capture_output=True)
                if result.returncode != 0:
                    raise RuntimeError(f"Ghostscript error:\n{result.stderr.decode(errors='replace')}")
                self.after(0, lambda: messagebox.showinfo("✅ Éxito",
                    f"PDF convertido a blanco y negro correctamente.\n\n{out}"))
                self._set_status(f"Convertido a blanco y negro: {Path(out).name}")
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
        self._run_threaded(do)

    # ══════════════════════════════════════════════
    #  TAB 2 – SEPARAR PDF
    # ══════════════════════════════════════════════
    def _build_split(self, parent):
        _, card = self._card(parent,
            "✂️  Separar PDF",
            "Divide un PDF en varios archivos por rangos o página por página")

        # Selección de archivo
        top = tk.Frame(card, bg=PANEL)
        top.pack(fill="x", padx=16, pady=(14, 4))

        tk.Label(top, text="Archivo PDF:", bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(anchor="w")
        row = tk.Frame(top, bg=PANEL)
        row.pack(fill="x", pady=4)
        self.split_path = tk.StringVar()
        tk.Entry(row, textvariable=self.split_path, state="readonly",
                 bg="#1A1A2E", fg=TEXT, relief="flat", font=("Segoe UI", 10),
                 readonlybackground="#1A1A2E").pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self._btn(row, "Abrir", self._split_open, icon="📂").pack(side="left")

        self.split_info = tk.Label(card, text="", bg=PANEL, fg=ACCENT2, font=("Segoe UI", 9))
        self.split_info.pack(anchor="w", padx=16)

        sep = tk.Frame(card, bg=BORDER, height=1)
        sep.pack(fill="x", padx=16, pady=10)

        # Modo
        tk.Label(card, text="Modo de separación:", bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=16)

        self.split_mode = tk.StringVar(value="all")
        modes = tk.Frame(card, bg=PANEL)
        modes.pack(anchor="w", padx=16, pady=4)
        tk.Radiobutton(modes, text="Una página por archivo", variable=self.split_mode,
                       value="all", bg=PANEL, fg=TEXT, selectcolor=ACCENT,
                       activebackground=PANEL, font=("Segoe UI", 10),
                       command=self._split_toggle).pack(side="left", padx=(0, 20))
        tk.Radiobutton(modes, text="Por rangos personalizados", variable=self.split_mode,
                       value="range", bg=PANEL, fg=TEXT, selectcolor=ACCENT,
                       activebackground=PANEL, font=("Segoe UI", 10),
                       command=self._split_toggle).pack(side="left")

        self.range_frame = tk.Frame(card, bg=PANEL)
        self.range_frame.pack(fill="x", padx=16, pady=4)
        tk.Label(self.range_frame, text="Rangos (ej: 1-3, 4-6, 7):",
                 bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9)).pack(anchor="w")
        self.split_range = tk.Entry(self.range_frame, bg="#1A1A2E", fg=TEXT,
                                    insertbackground=TEXT, relief="flat",
                                    font=("Segoe UI", 10))
        self.split_range.pack(fill="x", ipady=6, pady=2)
        Tooltip(self.split_range, "Ejemplo: 1-3, 4-5, 6  →  generará 3 archivos")
        self.range_frame.pack_forget()

        sep2 = tk.Frame(card, bg=BORDER, height=1)
        sep2.pack(fill="x", padx=16, pady=10)

        self._btn(card, "Separar PDF", self._split_run, icon="✂️").pack(anchor="w", padx=16, pady=(0, 16))

    def _split_toggle(self):
        if self.split_mode.get() == "range":
            self.range_frame.pack(fill="x", padx=16, pady=4)
        else:
            self.range_frame.pack_forget()

    def _split_open(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if f:
            self.split_path.set(f)
            n = PdfReader(f).get_num_pages()
            self.split_info.config(text=f"  📄 {n} páginas  ·  {Path(f).name}")

    def _parse_ranges(self, text, total):
        parts = [p.strip() for p in text.split(",")]
        ranges = []
        for part in parts:
            if "-" in part:
                a, b = part.split("-")
                ranges.append((int(a), int(b)))
            else:
                n = int(part)
                ranges.append((n, n))
        return ranges

    def _split_run(self):
        path = self.split_path.get()
        if not path:
            messagebox.showwarning("Aviso", "Selecciona un archivo PDF primero.")
            return
        out_dir = filedialog.askdirectory(title="Carpeta de destino")
        if not out_dir:
            return
        mode = self.split_mode.get()
        reader = PdfReader(path)
        total  = reader.get_num_pages()
        stem   = Path(path).stem

        def do():
            try:
                if mode == "all":
                    for i in range(total):
                        w = PdfWriter()
                        w.add_page(reader.pages[i])
                        out = os.path.join(out_dir, f"{stem}_pagina_{i+1:03d}.pdf")
                        with open(out, "wb") as f:
                            w.write(f)
                    self.after(0, lambda: messagebox.showinfo("✅ Éxito",
                        f"Se crearon {total} archivos en:\n{out_dir}"))
                else:
                    text = self.split_range.get().strip()
                    if not text:
                        self.after(0, lambda: messagebox.showwarning("Aviso", "Escribe los rangos de páginas."))
                        return
                    ranges = self._parse_ranges(text, total)
                    for idx, (a, b) in enumerate(ranges, 1):
                        w = PdfWriter()
                        for pg in range(a - 1, b):
                            w.add_page(reader.pages[pg])
                        out = os.path.join(out_dir, f"{stem}_parte_{idx}.pdf")
                        with open(out, "wb") as f:
                            w.write(f)
                    self.after(0, lambda: messagebox.showinfo("✅ Éxito",
                        f"Se crearon {len(ranges)} archivos en:\n{out_dir}"))
                self._set_status("Separación completada")
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
        self._run_threaded(do)

    # ══════════════════════════════════════════════
    #  TAB 3 – ELIMINAR PÁGINAS
    # ══════════════════════════════════════════════
    def _build_delete(self, parent):
        _, card = self._card(parent,
            "🗑️  Eliminar páginas",
            "Quita páginas específicas de un PDF y guarda el resultado")

        top = tk.Frame(card, bg=PANEL)
        top.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(top, text="Archivo PDF:", bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9)).pack(anchor="w")
        row = tk.Frame(top, bg=PANEL)
        row.pack(fill="x", pady=4)
        self.del_path = tk.StringVar()
        tk.Entry(row, textvariable=self.del_path, state="readonly",
                 bg="#1A1A2E", fg=TEXT, relief="flat", font=("Segoe UI", 10),
                 readonlybackground="#1A1A2E").pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self._btn(row, "Abrir", self._del_open, icon="📂").pack(side="left")

        self.del_info = tk.Label(card, text="", bg=PANEL, fg=ACCENT2, font=("Segoe UI", 9))
        self.del_info.pack(anchor="w", padx=16)

        sep = tk.Frame(card, bg=BORDER, height=1)
        sep.pack(fill="x", padx=16, pady=10)

        tk.Label(card, text="Páginas a eliminar (ej: 1, 3, 5-8):",
                 bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9)).pack(anchor="w", padx=16)
        self.del_pages = tk.Entry(card, bg="#1A1A2E", fg=TEXT, insertbackground=TEXT,
                                  relief="flat", font=("Segoe UI", 11))
        self.del_pages.pack(fill="x", padx=16, ipady=7, pady=4)
        Tooltip(self.del_pages, "Ejemplo: 1, 3, 5-8  elimina las páginas 1, 3, 5, 6, 7, 8")

        tk.Label(card, text="⚠️  Las páginas restantes se renumeran automáticamente.",
                 bg=PANEL, fg=WARNING, font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(4, 12))

        self._btn(card, "Eliminar y Guardar", self._del_run, icon="🗑️").pack(anchor="w", padx=16, pady=(0, 16))

    def _del_open(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if f:
            self.del_path.set(f)
            n = PdfReader(f).get_num_pages()
            self.del_info.config(text=f"  📄 {n} páginas  ·  {Path(f).name}")

    def _del_run(self):
        path  = self.del_path.get()
        pages_text = self.del_pages.get().strip()
        if not path:
            messagebox.showwarning("Aviso", "Selecciona un archivo PDF.")
            return
        if not pages_text:
            messagebox.showwarning("Aviso", "Escribe las páginas a eliminar.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".pdf",
                                           filetypes=[("PDF", "*.pdf")],
                                           title="Guardar PDF resultante como...")
        if not out:
            return

        reader = PdfReader(path)
        total  = reader.get_num_pages()

        # Parsear páginas a eliminar
        to_del = set()
        try:
            for part in pages_text.split(","):
                part = part.strip()
                if not part:
                    continue
                if "-" in part:
                    a, b = part.split("-")
                    to_del.update(range(int(a) - 1, int(b)))
                else:
                    to_del.add(int(part) - 1)
        except ValueError:
            messagebox.showerror("Error", "Formato inválido. Usa números separados por comas (ej: 1, 3, 5-8).")
            return

        invalid = [i + 1 for i in to_del if i < 0 or i >= total]
        if invalid:
            messagebox.showerror("Error",
                f"Página(s) fuera de rango: {invalid}\nEl PDF solo tiene {total} página(s).")
            return

        def do():
            try:
                writer = PdfWriter()
                removed = 0
                for i in range(total):
                    if i not in to_del:
                        writer.add_page(reader.pages[i])
                    else:
                        removed += 1
                with open(out, "wb") as f:
                    writer.write(f)
                self.after(0, lambda: messagebox.showinfo("✅ Éxito",
                    f"{removed} página(s) eliminadas.\n"
                    f"Quedan {total - removed} páginas.\n\n{out}"))
                self._set_status(f"Páginas eliminadas: {out}")
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
        self._run_threaded(do)

    # ══════════════════════════════════════════════
    #  TAB 4 – REORDENAR
    # ══════════════════════════════════════════════
    def _build_reorder(self, parent):
        _, card = self._card(parent,
            "🔀  Reordenar páginas",
            "Cambia el orden de las páginas de un PDF")

        top = tk.Frame(card, bg=PANEL)
        top.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(top, text="Archivo PDF:", bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9)).pack(anchor="w")
        row = tk.Frame(top, bg=PANEL)
        row.pack(fill="x", pady=4)
        self.reorder_path = tk.StringVar()
        tk.Entry(row, textvariable=self.reorder_path, state="readonly",
                 bg="#1A1A2E", fg=TEXT, relief="flat", font=("Segoe UI", 10),
                 readonlybackground="#1A1A2E").pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self._btn(row, "Abrir", self._reorder_open, icon="📂").pack(side="left")

        self.reorder_info = tk.Label(card, text="", bg=PANEL, fg=ACCENT2, font=("Segoe UI", 9))
        self.reorder_info.pack(anchor="w", padx=16)

        sep = tk.Frame(card, bg=BORDER, height=1)
        sep.pack(fill="x", padx=16, pady=10)

        tk.Label(card, text="Nuevo orden de páginas (ej: 3, 1, 2, 4):",
                 bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9)).pack(anchor="w", padx=16)
        self.reorder_entry = tk.Entry(card, bg="#1A1A2E", fg=TEXT, insertbackground=TEXT,
                                      relief="flat", font=("Segoe UI", 11))
        self.reorder_entry.pack(fill="x", padx=16, ipady=7, pady=4)
        Tooltip(self.reorder_entry, "Ejemplo: 3, 1, 2 → mueve la página 3 al inicio")

        tk.Label(card,
                 text="💡 Puedes repetir páginas (ej: 1, 1, 2 duplica la página 1) o usar solo un subconjunto.",
                 bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9),
                 wraplength=480, justify="left").pack(anchor="w", padx=16, pady=(4, 12))

        self._btn(card, "Reordenar y Guardar", self._reorder_run, icon="💾").pack(anchor="w", padx=16, pady=(0, 16))

    def _reorder_open(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if f:
            self.reorder_path.set(f)
            n = PdfReader(f).get_num_pages()
            self.reorder_info.config(text=f"  📄 {n} páginas  ·  {Path(f).name}")
            self.reorder_entry.delete(0, "end")
            self.reorder_entry.insert(0, ", ".join(str(i) for i in range(1, n + 1)))

    def _reorder_run(self):
        path = self.reorder_path.get()
        order_text = self.reorder_entry.get().strip()
        if not path or not order_text:
            messagebox.showwarning("Aviso", "Selecciona un PDF y escribe el nuevo orden.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".pdf",
                                           filetypes=[("PDF", "*.pdf")],
                                           title="Guardar PDF reordenado como...")
        if not out:
            return
        try:
            order = [int(x.strip()) - 1 for x in order_text.split(",")]
        except ValueError:
            messagebox.showerror("Error", "Formato de orden inválido. Usa números separados por comas.")
            return

        reader = PdfReader(path)
        def do():
            try:
                writer = PdfWriter()
                for idx in order:
                    writer.add_page(reader.pages[idx])
                with open(out, "wb") as f:
                    writer.write(f)
                self.after(0, lambda: messagebox.showinfo("✅ Éxito",
                    f"PDF reordenado correctamente.\n{len(order)} páginas.\n\n{out}"))
                self._set_status("PDF reordenado")
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
        self._run_threaded(do)

    # ══════════════════════════════════════════════
    #  TAB 5 – COMPRIMIR  (soporte archivos grandes)
    # ══════════════════════════════════════════════
    def _find_ghostscript(self):
        # 1. PATH del sistema
        for cmd in ["gswin64c", "gswin32c", "gs"]:
            if shutil.which(cmd):
                return shutil.which(cmd)
        # 2. Instalación estándar de Windows
        for pattern in [
            r"C:\Program Files\gs\gs*\bin\gswin64c.exe",
            r"C:\Program Files (x86)\gs\gs*\bin\gswin32c.exe",
            r"C:\Program Files\gs\gs*\bin\gswin32c.exe",
        ]:
            matches = glob.glob(pattern)
            if matches:
                return matches[-1]
        # 3. Ghostscript portátil empaquetado junto al .exe (gs_portable\bin\)
        try:
            base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
        except Exception:
            base = Path(".")
        for rel in [
            base / "gs_portable" / "bin" / "gswin64c.exe",
            base / "gs_portable" / "bin" / "gswin32c.exe",
        ]:
            if rel.exists():
                return str(rel)
        return None

    def _build_compress(self, parent):
        self._comp_cancel_flag = False
        self._comp_proc        = None

        _, card = self._card(parent,
            "🗜️  Comprimir PDF",
            "Optimizado para archivos grandes — muestra progreso en tiempo real")

        # ── Selector de archivo ──────────────────
        top = tk.Frame(card, bg=PANEL)
        top.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(top, text="Archivo PDF:", bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9)).pack(anchor="w")
        row = tk.Frame(top, bg=PANEL)
        row.pack(fill="x", pady=4)
        self.comp_path = tk.StringVar()
        tk.Entry(row, textvariable=self.comp_path, state="readonly",
                 bg="#1A1A2E", fg=TEXT, relief="flat", font=("Segoe UI", 10),
                 readonlybackground="#1A1A2E").pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self._btn(row, "Abrir", self._comp_open, icon="📂").pack(side="left")

        self.comp_info = tk.Label(card, text="", bg=PANEL, fg=ACCENT2, font=("Segoe UI", 9))
        self.comp_info.pack(anchor="w", padx=16, pady=(2, 0))

        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", padx=16, pady=10)

        # ── Estado Ghostscript ───────────────────
        gs = self._find_ghostscript()
        gs_color = SUCCESS if gs else WARNING
        gs_msg   = ("✅  Ghostscript detectado — compresión real disponible (imágenes + texto)"
                    if gs else
                    "⚠️  Ghostscript NO instalado.\n"
                    "    Sin él solo se comprimen metadatos (poca reducción en PDFs con imágenes).\n"
                    "    Descárgalo gratis: ghostscript.com/releases  (~30 MB)")
        tk.Label(card, text=gs_msg, bg=PANEL, fg=gs_color,
                 font=("Segoe UI", 9), wraplength=530, justify="left").pack(anchor="w", padx=16)

        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", padx=16, pady=10)

        # ── Nivel de compresión ──────────────────
        tk.Label(card, text="Nivel de compresión:", bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=16)

        self.comp_level = tk.StringVar(value="ebook")
        niveles = tk.Frame(card, bg=PANEL)
        niveles.pack(anchor="w", padx=16, pady=(4, 0))
        for val, lbl, tip in [
            ("screen",  "🔴 Máxima  (72 dpi)   — WhatsApp / email",    "Menor tamaño, calidad baja"),
            ("ebook",   "🟡 Alta    (150 dpi)  — Lectura pantalla",     "Mejor equilibrio tamaño/calidad"),
            ("printer", "🟢 Media   (300 dpi)  — Impresión casera",     "Buena calidad, menos reducción"),
            ("prepress","⚪ Mínima  (original) — Archivo profesional",  "Casi sin pérdida de calidad"),
        ]:
            rb = tk.Radiobutton(niveles, text=lbl, variable=self.comp_level, value=val,
                                bg=PANEL, fg=TEXT, selectcolor=ACCENT, activebackground=PANEL,
                                font=("Segoe UI", 10), state="normal" if gs else "disabled")
            rb.pack(anchor="w", pady=1)
            Tooltip(rb, tip)

        # ── Opciones avanzadas para archivos grandes ──
        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", padx=16, pady=10)

        tk.Label(card, text="Opciones para archivos grandes:", bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=16)

        adv = tk.Frame(card, bg=PANEL)
        adv.pack(anchor="w", padx=16, pady=(4, 0))

        self.comp_batch    = tk.BooleanVar(value=True)
        self.comp_lowmem   = tk.BooleanVar(value=True)
        self.comp_chunksz  = tk.IntVar(value=200)

        cb1 = tk.Checkbutton(adv, text="Modo bajo consumo de memoria  (recomendado para +500 MB)",
                              variable=self.comp_lowmem, bg=PANEL, fg=TEXT,
                              selectcolor=ACCENT, activebackground=PANEL, font=("Segoe UI", 10))
        cb1.pack(anchor="w", pady=1)
        Tooltip(cb1, "Ghostscript procesa en bloques internos en vez de cargar todo en RAM")

        cb2 = tk.Checkbutton(adv, text="Procesar en lotes de páginas  (evita bloqueo de la app)",
                              variable=self.comp_batch, bg=PANEL, fg=TEXT,
                              selectcolor=ACCENT, activebackground=PANEL, font=("Segoe UI", 10))
        cb2.pack(anchor="w", pady=1)
        Tooltip(cb2, "Divide el PDF en grupos y muestra el progreso mientras comprime")

        chunk_row = tk.Frame(adv, bg=PANEL)
        chunk_row.pack(anchor="w", pady=2)
        tk.Label(chunk_row, text="  Páginas por lote:", bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(side="left")
        tk.Spinbox(chunk_row, from_=50, to=1000, increment=50,
                   textvariable=self.comp_chunksz, width=6,
                   bg="#1A1A2E", fg=TEXT, insertbackground=TEXT,
                   buttonbackground=PANEL, relief="flat",
                   font=("Segoe UI", 10)).pack(side="left", padx=8)
        Tooltip(chunk_row, "Lotes más pequeños usan menos memoria; lotes más grandes son más rápidos")

        # ── Barra de progreso dedicada ───────────
        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", padx=16, pady=10)

        prog_frame = tk.Frame(card, bg=PANEL)
        prog_frame.pack(fill="x", padx=16, pady=(0, 4))

        self.comp_prog_lbl = tk.Label(prog_frame, text="", bg=PANEL, fg=SUBTEXT,
                                      font=("Segoe UI", 9))
        self.comp_prog_lbl.pack(anchor="w")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Comp.Horizontal.TProgressbar",
                        troughcolor=BORDER, background=ACCENT,
                        thickness=14, borderwidth=0)
        self.comp_progbar = ttk.Progressbar(prog_frame, style="Comp.Horizontal.TProgressbar",
                                            orient="horizontal", mode="determinate",
                                            length=100, maximum=100, value=0)
        self.comp_progbar.pack(fill="x", pady=(4, 0))

        self.comp_eta_lbl = tk.Label(prog_frame, text="", bg=PANEL, fg=SUBTEXT,
                                     font=("Segoe UI", 9))
        self.comp_eta_lbl.pack(anchor="w", pady=(2, 0))

        self.comp_result = tk.Label(card, text="", bg=PANEL, fg=SUCCESS,
                                    font=("Segoe UI", 10, "bold"))
        self.comp_result.pack(anchor="w", padx=16, pady=(4, 0))

        # ── Botones acción ───────────────────────
        btn_row = tk.Frame(card, bg=PANEL)
        btn_row.pack(anchor="w", padx=16, pady=(8, 16))
        self.comp_run_btn = self._btn(btn_row, "Comprimir y Guardar", self._comp_run, icon="🗜️")
        self.comp_run_btn.pack(side="left", padx=(0, 10))
        self.comp_cancel_btn = self._btn(btn_row, "Cancelar", self._comp_cancel,
                                         color=DANGER, icon="✖")
        self.comp_cancel_btn.pack(side="left")
        self.comp_cancel_btn.config(state="disabled")

    # ── helpers de compresión ─────────────────────
    def _comp_open(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if not f:
            return
        self.comp_path.set(f)
        size = os.path.getsize(f)
        # Contar páginas sin cargar todo en RAM
        try:
            n = PdfReader(f).get_num_pages()
        except Exception:
            n = "?"
        mb = size / 1024 / 1024
        self.comp_info.config(
            text=f"  📄 {n} páginas  ·  {mb:.1f} MB  ({size/1024:.0f} KB)  ·  {Path(f).name}")
        self.comp_result.config(text="")
        self.comp_prog_lbl.config(text="")
        self.comp_eta_lbl.config(text="")
        self.comp_progbar["value"] = 0

    def _comp_cancel(self):
        self._comp_cancel_flag = True
        if self._comp_proc and self._comp_proc.poll() is None:
            self._comp_proc.terminate()
        self._set_status("Compresión cancelada por el usuario")
        self.comp_prog_lbl.config(text="⛔ Cancelado")
        self.comp_run_btn.config(state="normal")
        self.comp_cancel_btn.config(state="disabled")

    def _comp_set_progress(self, pct, lbl="", eta=""):
        self.comp_progbar["value"] = pct
        if lbl:
            self.comp_prog_lbl.config(text=lbl)
        if eta:
            self.comp_eta_lbl.config(text=eta)

    def _fmt_time(self, seconds):
        if seconds < 60:
            return f"{int(seconds)}s"
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s}s"

    @staticmethod
    def _pypdf_optimize_file(filepath):
        """Aplica compress_identical_objects de pypdf sobre un archivo existente (in-place)."""
        tmp = filepath + ".pdfopt.tmp"
        try:
            writer = PdfWriter()
            writer.append(fileobj=filepath)
            writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
            with open(tmp, "wb") as f:
                writer.write(f)
            del writer
            os.replace(tmp, filepath)
        except Exception:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass

    def _comp_run(self):
        path = self.comp_path.get()
        if not path:
            messagebox.showwarning("Aviso", "Selecciona un archivo PDF.")
            return
        out = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            title="Guardar PDF comprimido como...")
        if not out:
            return

        orig_size          = os.path.getsize(path)
        gs                 = self._find_ghostscript()
        use_batch          = self.comp_batch.get()
        use_lowmem         = self.comp_lowmem.get()
        chunk_sz           = self.comp_chunksz.get()
        level              = self.comp_level.get()
        self._comp_cancel_flag = False

        self.comp_run_btn.config(state="disabled")
        self.comp_cancel_btn.config(state="normal")
        self.comp_progbar["value"] = 0
        self.comp_result.config(text="")

        def gs_flags():
            flags = [
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                f"-dPDFSETTINGS=/{level}",
                "-dNOPAUSE", "-dBATCH",
            ]
            if use_lowmem:
                flags += [
                    "-dBufferSpace=200000000",   # 200 MB buffer
                    "-dMaxInlineImageSize=0",
                    "-dPDFSTRINGLENGTH=65535",
                ]
            return flags

        # ─────────────────────────────────────────
        def do_ghostscript_single():
            """Ghostscript en un solo comando — más rápido, sin progreso granular."""
            self.after(0, lambda: self._comp_set_progress(5,
                "⏳ Iniciando Ghostscript...", "Estimando tiempo..."))
            cmd = [gs] + gs_flags() + [f"-sOutputFile={out}", path]
            t0  = time.time()
            self._comp_proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Hilo aparte para animar la barra mientras GS trabaja
            def pulse():
                val = 5
                while self._comp_proc.poll() is None:
                    if self._comp_cancel_flag:
                        return
                    elapsed = time.time() - t0
                    # estimar progreso por tamaño escrito
                    try:
                        written = os.path.getsize(out) if os.path.exists(out) else 0
                        pct = min(95, 5 + int(written / orig_size * 90))
                    except Exception:
                        pct = min(95, val + 1)
                    val = pct
                    eta_s = ""
                    if pct > 10:
                        total_est = elapsed / (pct / 100)
                        eta_s = f"Tiempo restante estimado: {self._fmt_time(total_est - elapsed)}"
                    self.after(0, lambda p=pct, e=eta_s: self._comp_set_progress(
                        p, f"Comprimiendo… {p}%", e))
                    time.sleep(1)

            threading.Thread(target=pulse, daemon=True).start()
            stdout, stderr = self._comp_proc.communicate()
            if self._comp_cancel_flag:
                return
            if self._comp_proc.returncode != 0:
                raise RuntimeError(f"Ghostscript error:\n{stderr.decode(errors='replace')}")
            # 2.º paso: compress_identical_objects sobre el resultado de GS
            self.after(0, lambda: self._comp_set_progress(97, "Optimizando estructura (pypdf)…"))
            self._pypdf_optimize_file(out)
            return "Ghostscript + pypdf"

        # ─────────────────────────────────────────
        def do_ghostscript_batch():
            """Divide en lotes, comprime cada uno y une — progreso real por página."""
            total_pgs = PdfReader(path).get_num_pages()
            tmp_dir   = tempfile.mkdtemp(prefix="pdfmgr_")
            parts     = []
            t0        = time.time()

            try:
                chunks = list(range(0, total_pgs, chunk_sz))
                for ci, start in enumerate(chunks):
                    if self._comp_cancel_flag:
                        return None

                    end       = min(start + chunk_sz, total_pgs)
                    chunk_in  = os.path.join(tmp_dir, f"chunk_in_{ci}.pdf")
                    chunk_out = os.path.join(tmp_dir, f"chunk_out_{ci}.pdf")

                    # Extraer lote con append() — evita "Page must be part of PdfWriter"
                    w = PdfWriter()
                    w.append(fileobj=path, pages=(start, end))
                    with open(chunk_in, "wb") as f:
                        w.write(f)
                    del w

                    # Comprimir lote con GS
                    cmd = [gs] + gs_flags() + [f"-sOutputFile={chunk_out}", chunk_in]
                    self._comp_proc = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    _, stderr = self._comp_proc.communicate()
                    if self._comp_cancel_flag:
                        return None
                    if self._comp_proc.returncode != 0:
                        raise RuntimeError(
                            f"Error en lote {ci+1}:\n{stderr.decode(errors='replace')}")

                    parts.append(chunk_out)
                    pct     = int((ci + 1) / len(chunks) * 90)
                    elapsed = time.time() - t0
                    eta_s   = ""
                    if pct > 5:
                        total_est = elapsed / (pct / 100)
                        eta_s = f"Tiempo restante estimado: {self._fmt_time(total_est - elapsed)}"
                    lbl = f"Lote {ci+1}/{len(chunks)} — páginas {start+1}–{end} de {total_pgs}"
                    self.after(0, lambda p=pct, lb=lbl, e=eta_s:
                        self._comp_set_progress(p, lb, e))

                # Unir partes ya comprimidas con GS directamente (no con pypdf)
                self.after(0, lambda: self._comp_set_progress(92, "Uniendo lotes comprimidos…"))
                merge_cmd = [gs,
                             "-sDEVICE=pdfwrite",
                             "-dCompatibilityLevel=1.4",
                             "-dNOPAUSE", "-dBATCH", "-dQUIET",
                             f"-sOutputFile={out}"] + parts
                result = subprocess.run(merge_cmd, capture_output=True)
                if result.returncode != 0:
                    raise RuntimeError(
                        f"Error al unir lotes:\n{result.stderr.decode(errors='replace')}")
                # 2.º paso: compress_identical_objects sobre el resultado de GS
                self.after(0, lambda: self._comp_set_progress(97, "Optimizando estructura (pypdf)…"))
                self._pypdf_optimize_file(out)

            finally:
                for fname in os.listdir(tmp_dir):
                    try:
                        os.remove(os.path.join(tmp_dir, fname))
                    except Exception:
                        pass
                try:
                    os.rmdir(tmp_dir)
                except Exception:
                    pass

            return "Ghostscript (lotes) + pypdf"

        # ─────────────────────────────────────────
        def do_pypdf_fallback():
            """Sin GS: procesamiento por lotes con vaciado de RAM entre chunks.

            Estrategia para PDFs de 1 GB / 6000 páginas:
            - Cada chunk se procesa en un PdfWriter independiente y se guarda
              como archivo temporal en disco.
            - Al final se unen los temporales con un writer nuevo (sin imágenes
              en RAM) y se aplica compress_identical_objects.
            - Nunca se mezcla PdfReader.pages con add_page() para evitar
              el error 'Page must be part of a PdfWriter' de pypdf >=4.
            """
            total_pgs = PdfReader(path).get_num_pages()
            CHUNK     = max(chunk_sz, 200)   # mínimo 200 págs; más = menos archivos tmp
            t0        = time.time()
            tmp_dir   = tempfile.mkdtemp(prefix="pdfmgr_comp_")
            parts     = []

            try:
                chunks = list(range(0, total_pgs, CHUNK))
                for ci, start in enumerate(chunks):
                    if self._comp_cancel_flag:
                        return None
                    end = min(start + CHUNK, total_pgs)

                    # Writer independiente por chunk — se libera de RAM al salir del bloque
                    w = PdfWriter()
                    w.append(fileobj=path, pages=(start, end))
                    tmp_out = os.path.join(tmp_dir, f"part_{ci:04d}.pdf")
                    with open(tmp_out, "wb") as tf:
                        w.write(tf)
                    del w   # liberar RAM

                    parts.append(tmp_out)
                    pct     = int((ci + 1) / len(chunks) * 80)
                    elapsed = time.time() - t0
                    eta_s   = ""
                    if pct > 5:
                        total_est = elapsed / (pct / 100)
                        eta_s = f"Tiempo restante estimado: {self._fmt_time(total_est - elapsed)}"
                    self.after(0, lambda p=pct, pg=end, eta=eta_s:
                        self._comp_set_progress(p,
                            f"Procesando páginas {pg}/{total_pgs}  ({p}%)", eta))

                # Unir todos los temporales en el archivo final
                self.after(0, lambda: self._comp_set_progress(85, "Uniendo partes…"))
                final_writer = PdfWriter()
                for part in parts:
                    final_writer.append(fileobj=part)

                self.after(0, lambda: self._comp_set_progress(93, "Optimizando estructura…"))
                final_writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)

                self.after(0, lambda: self._comp_set_progress(97, "Guardando archivo final…"))
                with open(out, "wb") as f:
                    final_writer.write(f)
                del final_writer

            finally:
                # Limpiar temporales siempre, incluso si hubo error
                for fname in parts:
                    try:
                        os.remove(fname)
                    except Exception:
                        pass
                try:
                    os.rmdir(tmp_dir)
                except Exception:
                    pass

            return "pypdf (sin Ghostscript)"

        # ─────────────────────────────────────────
        def _reset_buttons():
            self.comp_run_btn.config(state="normal")
            self.comp_cancel_btn.config(state="disabled")
            self.progress.stop()

        def do():
            self.after(0, self.progress.start, 10)
            try:
                if gs:
                    if use_batch:
                        method = do_ghostscript_batch()
                    else:
                        method = do_ghostscript_single()
                else:
                    method = do_pypdf_fallback()

                if self._comp_cancel_flag or method is None:
                    if os.path.exists(out):
                        try:
                            os.remove(out)
                        except Exception:
                            pass
                    self.after(0, _reset_buttons)
                    self.after(0, lambda: self._comp_set_progress(0, "⛔ Cancelado"))
                    return

                self.after(0, lambda: self._comp_set_progress(100, "✅ Compresión finalizada"))

                new_size  = os.path.getsize(out)
                reduction = (1 - new_size / orig_size) * 100
                orig_mb   = orig_size / 1024 / 1024
                new_mb    = new_size  / 1024 / 1024

                sign  = "✅" if reduction > 0 else "⚠️"
                extra = ("" if reduction > 0
                         else "\n\nEl PDF ya estaba optimizado o no contiene imágenes comprimibles.")

                def show_result():
                    self.comp_result.config(
                        text=f"✅  {orig_mb:.1f} MB  →  {new_mb:.1f} MB  (−{reduction:.1f}%)  · {method}")
                    _reset_buttons()
                    messagebox.showinfo(f"{sign} Compresión completada",
                        f"Método:     {method}\n"
                        f"Original:   {orig_mb:.2f} MB\n"
                        f"Comprimido: {new_mb:.2f} MB\n"
                        f"Reducción:  {reduction:.1f}%{extra}\n\n"
                        f"Guardado en:\n{out}")

                self.after(0, show_result)
                self._set_status(f"Compresión completada — −{reduction:.1f}%  ({method})")

            except BaseException as e:
                import traceback, os as _os
                tb = traceback.format_exc()
                # Escribir log junto al PDF de salida para diagnóstico
                log_path = out + ".error.log"
                try:
                    with open(log_path, "w", encoding="utf-8") as lf:
                        lf.write(tb)
                except Exception:
                    pass
                err_msg = f"{type(e).__name__}: {e}\n\nLog guardado en:\n{log_path}"
                self.after(0, lambda: messagebox.showerror("Error al comprimir", err_msg))
                self.after(0, _reset_buttons)
                self.after(0, lambda: self._comp_set_progress(0, "❌ Error — ver log"))

        threading.Thread(target=do, daemon=True).start()

    # ══════════════════════════════════════════════
    #  TAB 6 – ROTAR PÁGINAS
    # ══════════════════════════════════════════════
    def _build_rotate(self, parent):
        _, card = self._card(parent,
            "🔄  Rotar páginas",
            "Gira páginas individuales o todo el documento")

        top = tk.Frame(card, bg=PANEL)
        top.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(top, text="Archivo PDF:", bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9)).pack(anchor="w")
        row = tk.Frame(top, bg=PANEL)
        row.pack(fill="x", pady=4)
        self.rot_path = tk.StringVar()
        tk.Entry(row, textvariable=self.rot_path, state="readonly",
                 bg="#1A1A2E", fg=TEXT, relief="flat", font=("Segoe UI", 10),
                 readonlybackground="#1A1A2E").pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self._btn(row, "Abrir", self._rot_open, icon="📂").pack(side="left")

        self.rot_info = tk.Label(card, text="", bg=PANEL, fg=ACCENT2, font=("Segoe UI", 9))
        self.rot_info.pack(anchor="w", padx=16)

        sep = tk.Frame(card, bg=BORDER, height=1)
        sep.pack(fill="x", padx=16, pady=10)

        # Alcance
        tk.Label(card, text="Páginas a rotar:", bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9)).pack(anchor="w", padx=16)
        scope_f = tk.Frame(card, bg=PANEL)
        scope_f.pack(anchor="w", padx=16, pady=4)
        self.rot_scope = tk.StringVar(value="all")
        tk.Radiobutton(scope_f, text="Todas las páginas", variable=self.rot_scope,
                       value="all", bg=PANEL, fg=TEXT, selectcolor=ACCENT,
                       activebackground=PANEL, font=("Segoe UI", 10)).pack(side="left", padx=(0, 20))
        tk.Radiobutton(scope_f, text="Páginas específicas:", variable=self.rot_scope,
                       value="custom", bg=PANEL, fg=TEXT, selectcolor=ACCENT,
                       activebackground=PANEL, font=("Segoe UI", 10)).pack(side="left")
        self.rot_pages = tk.Entry(scope_f, width=18, bg="#1A1A2E", fg=TEXT,
                                  insertbackground=TEXT, relief="flat", font=("Segoe UI", 10))
        self.rot_pages.pack(side="left", padx=8, ipady=4)
        Tooltip(self.rot_pages, "Ejemplo: 1, 3, 5-8")

        sep2 = tk.Frame(card, bg=BORDER, height=1)
        sep2.pack(fill="x", padx=16, pady=10)

        # Ángulo
        tk.Label(card, text="Ángulo de rotación:", bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9)).pack(anchor="w", padx=16)
        ang_f = tk.Frame(card, bg=PANEL)
        ang_f.pack(anchor="w", padx=16, pady=6)
        self.rot_angle = tk.IntVar(value=90)
        for ang, label in [(90, "90° →"), (180, "180°"), (270, "← 90°")]:
            tk.Radiobutton(ang_f, text=label, variable=self.rot_angle, value=ang,
                           bg=PANEL, fg=TEXT, selectcolor=ACCENT, activebackground=PANEL,
                           font=("Segoe UI", 11)).pack(side="left", padx=12)

        self._btn(card, "Rotar y Guardar", self._rot_run, icon="🔄").pack(anchor="w", padx=16, pady=(16, 16))

    def _rot_open(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if f:
            self.rot_path.set(f)
            n = PdfReader(f).get_num_pages()
            self.rot_info.config(text=f"  📄 {n} páginas  ·  {Path(f).name}")

    def _rot_run(self):
        path = self.rot_path.get()
        if not path:
            messagebox.showwarning("Aviso", "Selecciona un archivo PDF.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".pdf",
                                           filetypes=[("PDF", "*.pdf")],
                                           title="Guardar PDF rotado como...")
        if not out:
            return

        reader = PdfReader(path)
        total  = reader.get_num_pages()
        angle  = self.rot_angle.get()

        if self.rot_scope.get() == "custom":
            scope_text = self.rot_pages.get().strip()
            if not scope_text:
                messagebox.showwarning("Aviso", "Escribe las páginas a rotar.")
                return
            to_rotate = set()
            try:
                for part in scope_text.split(","):
                    part = part.strip()
                    if not part:
                        continue
                    if "-" in part:
                        a, b = part.split("-")
                        to_rotate.update(range(int(a) - 1, int(b)))
                    else:
                        to_rotate.add(int(part) - 1)
            except ValueError:
                messagebox.showerror("Error", "Formato inválido. Usa números separados por comas (ej: 1, 3, 5-8).")
                return
            invalid = [i + 1 for i in to_rotate if i < 0 or i >= total]
            if invalid:
                messagebox.showerror("Error",
                    f"Página(s) fuera de rango: {invalid}\nEl PDF solo tiene {total} página(s).")
                return
        else:
            to_rotate = set(range(total))

        def do():
            try:
                writer = PdfWriter()
                for i in range(total):
                    page = reader.pages[i]
                    if i in to_rotate:
                        page.rotate(angle)
                    writer.add_page(page)
                with open(out, "wb") as f:
                    writer.write(f)
                self.after(0, lambda: messagebox.showinfo("✅ Éxito",
                    f"{len(to_rotate)} página(s) rotadas {angle}°.\n\n{out}"))
                self._set_status("Páginas rotadas correctamente")
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
        self._run_threaded(do)


    # ══════════════════════════════════════════════
    #  TAB 7 – FOLIACIÓN (Numeración Consecutiva)
    # ══════════════════════════════════════════════
    def _build_foliate(self, parent):
        self._fol_total_pages = None
        _, card = self._card(parent,
            "📑  Foliación",
            "Estampa un número consecutivo en la esquina de cada página del PDF")

        if not HAS_REPORTLAB:
            tk.Label(card,
                     text="⚠️  Módulo 'reportlab' no instalado.\n"
                          "    Ejecuta:  pip install reportlab",
                     bg=PANEL, fg=WARNING, font=("Segoe UI", 10),
                     wraplength=500, justify="left").pack(padx=16, pady=20, anchor="w")
            return

        # ── Selector de archivo ──────────────────
        top = tk.Frame(card, bg=PANEL)
        top.pack(fill="x", padx=16, pady=(8, 2))
        tk.Label(top, text="Archivo PDF:", bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(anchor="w")
        row = tk.Frame(top, bg=PANEL)
        row.pack(fill="x", pady=2)
        self.fol_path = tk.StringVar()
        tk.Entry(row, textvariable=self.fol_path, state="readonly",
                 bg="#1A1A2E", fg=TEXT, relief="flat", font=("Segoe UI", 10),
                 readonlybackground="#1A1A2E").pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self._btn(row, "Abrir", self._foliate_open, icon="📂").pack(side="left")

        self.fol_info = tk.Label(card, text="", bg=PANEL, fg=ACCENT2, font=("Segoe UI", 9))
        self.fol_info.pack(anchor="w", padx=16)

        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", padx=16, pady=4)

        # ── Opciones ─────────────────────────────
        opts = tk.Frame(card, bg=PANEL)
        opts.pack(fill="x", padx=16, pady=4)

        # Número inicial
        col1 = tk.Frame(opts, bg=PANEL)
        col1.pack(side="left", padx=(0, 28))
        tk.Label(col1, text="Número inicial:", bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self.fol_start = tk.IntVar(value=1)
        spin = tk.Spinbox(col1, from_=1, to=99999, increment=1,
                          textvariable=self.fol_start, width=8,
                          bg="#1A1A2E", fg=TEXT, insertbackground=TEXT,
                          buttonbackground=PANEL, relief="flat", font=("Segoe UI", 11))
        spin.pack(ipady=5, pady=2)
        self.fol_start.trace_add("write", lambda *_: self._foliate_update_info())
        Tooltip(spin, "El primer folio que aparecerá en la página 1 del documento")

        # Tamaño de fuente
        col2 = tk.Frame(opts, bg=PANEL)
        col2.pack(side="left")
        tk.Label(col2, text="Tamaño de fuente:", bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self.fol_fontsize = tk.IntVar(value=11)
        tk.Spinbox(col2, from_=7, to=24, increment=1,
                   textvariable=self.fol_fontsize, width=6,
                   bg="#1A1A2E", fg=TEXT, insertbackground=TEXT,
                   buttonbackground=PANEL, relief="flat", font=("Segoe UI", 11)).pack(ipady=5, pady=2)

        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", padx=16, pady=4)

        # ── Posición ──────────────────────────────
        tk.Label(card, text="Posición en la página:", bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=16)
        pos_f = tk.Frame(card, bg=PANEL)
        pos_f.pack(anchor="w", padx=16, pady=2)
        self.fol_position = tk.StringVar(value="top-right")
        for val, lbl in [
            ("top-right",    "Superior derecho"),
            ("top-left",     "Superior izquierdo"),
            ("bottom-right", "Inferior derecho"),
            ("bottom-left",  "Inferior izquierdo"),
        ]:
            tk.Radiobutton(pos_f, text=lbl, variable=self.fol_position, value=val,
                           bg=PANEL, fg=TEXT, selectcolor=ACCENT, activebackground=PANEL,
                           font=("Segoe UI", 10)).pack(side="left", padx=(0, 16))

        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", padx=16, pady=4)

        # ── Ajuste por página específica o rango ──
        self._fol_overrides = []
        ov_add_f = tk.Frame(card, bg=PANEL)
        ov_add_f.pack(anchor="w", padx=16, pady=(2, 2))

        tk.Label(ov_add_f, text="Excepción — página(s):", bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.fol_ov_range = tk.StringVar(value="1")
        ov_range_entry = tk.Entry(ov_add_f, textvariable=self.fol_ov_range, width=8,
                                  bg="#1A1A2E", fg=TEXT, insertbackground=TEXT,
                                  relief="flat", font=("Segoe UI", 11))
        ov_range_entry.pack(side="left", ipady=4, padx=(0, 10))
        Tooltip(ov_range_entry, "Una página (ej: 4) o un rango (ej: 4-8)")

        tk.Label(ov_add_f, text="horiz. (cm):", bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.fol_ov_offset_cm = tk.DoubleVar(value=0.0)
        tk.Spinbox(ov_add_f, from_=-5.0, to=5.0, increment=0.1, format="%.1f",
                   textvariable=self.fol_ov_offset_cm, width=5,
                   bg="#1A1A2E", fg=TEXT, insertbackground=TEXT,
                   buttonbackground=PANEL, relief="flat", font=("Segoe UI", 11)).pack(side="left", ipady=3, padx=(0, 10))

        tk.Label(ov_add_f, text="vert. (cm):", bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.fol_ov_offset_y_cm = tk.DoubleVar(value=0.0)
        tk.Spinbox(ov_add_f, from_=-5.0, to=5.0, increment=0.1, format="%.1f",
                   textvariable=self.fol_ov_offset_y_cm, width=5,
                   bg="#1A1A2E", fg=TEXT, insertbackground=TEXT,
                   buttonbackground=PANEL, relief="flat", font=("Segoe UI", 11)).pack(side="left", ipady=3, padx=(0, 10))

        ov_btn_f = tk.Frame(card, bg=PANEL)
        ov_btn_f.pack(anchor="w", padx=16, pady=(0, 2))
        add_btn = self._btn(ov_btn_f, "Agregar", self._foliate_override_add, color="#475569", icon="➕")
        add_btn.pack(side="left", padx=(0, 4))
        Tooltip(add_btn,
                "Corre el folio horizontalmente (izquierda = negativo, derecha = positivo)\n"
                "y/o verticalmente (arriba = positivo, abajo = negativo) en la página\n"
                "o rango de páginas indicado. Útil cuando un sello institucional tapa\n"
                "la numeración, o para aplicar el mismo ajuste a varias páginas a la vez\n"
                "(ej: 4-8 → 1 cm a la izquierda).")
        self._btn(ov_btn_f, "Quitar", self._foliate_override_remove, color=DANGER).pack(side="left")

        self.fol_overrides_lb = self._listbox(card, height=2, expand=False)

        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", padx=16, pady=4)

        self.fol_preview = tk.Label(card,
                                    text="Selecciona un PDF para ver el rango de foliación.",
                                    bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 9, "italic"))
        self.fol_preview.pack(anchor="w", padx=16, pady=(0, 4))

        self._btn(card, "Aplicar Foliación", self._foliate_run, icon="📑").pack(anchor="w", padx=16, pady=(0, 10))

    def _foliate_open(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if f:
            self.fol_path.set(f)
            n = PdfReader(f).get_num_pages()
            self._fol_total_pages = n
            self.fol_info.config(text=f"  📄 {n} páginas  ·  {Path(f).name}")
            self._foliate_update_info()

    def _foliate_update_info(self):
        total = getattr(self, "_fol_total_pages", None)
        if not total:
            return
        try:
            start     = int(self.fol_start.get())
            end_folio = start + total - 1
            self.fol_preview.config(
                fg=ACCENT2,
                text=f"  El documento quedará foliado del  {start}  al  {end_folio}  ({total} páginas)")
        except (tk.TclError, ValueError):
            pass

    def _foliate_override_add(self):
        range_text = self.fol_ov_range.get().strip()
        if not range_text:
            messagebox.showerror("Error", "Escribe una página (ej: 4) o un rango de páginas (ej: 4-8).")
            return
        try:
            if "-" in range_text:
                a, b = range_text.split("-", 1)
                start, end = int(a.strip()), int(b.strip())
            else:
                start = end = int(range_text.strip())
        except ValueError:
            messagebox.showerror("Error", "Formato inválido. Usa una página (ej: 4) o un rango (ej: 4-8).")
            return
        if start > end:
            start, end = end, start
        if start < 1:
            messagebox.showerror("Error", "La página debe ser mayor o igual a 1.")
            return
        total = getattr(self, "_fol_total_pages", None)
        if total and end > total:
            messagebox.showerror("Error",
                f"La página {end} no existe. El documento cargado solo tiene {total} página(s).")
            return

        try:
            dx = float(self.fol_ov_offset_cm.get())
            dy = float(self.fol_ov_offset_y_cm.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("Error", "El ajuste debe ser un número válido.")
            return

        for ov in self._fol_overrides:
            if start <= ov["end"] and ov["start"] <= end:
                overlap = (f"{ov['start']}" if ov["start"] == ov["end"]
                           else f"{ov['start']}-{ov['end']}")
                messagebox.showwarning("Aviso",
                    f"Ya existe un ajuste que se superpone con la página(s) {overlap}. "
                    "Quítalo primero si quieres cambiarlo.")
                return

        self._fol_overrides.append({"start": start, "end": end, "dx": dx, "dy": dy})
        label = f"Página {start}" if start == end else f"Páginas {start}–{end}"
        self.fol_overrides_lb.insert("end", f"{label}  →  x: {dx:+.1f} cm, y: {dy:+.1f} cm")

    def _foliate_override_remove(self):
        for i in reversed(self.fol_overrides_lb.curselection()):
            self.fol_overrides_lb.delete(i)
            del self._fol_overrides[i]

    def _foliate_run(self):
        path = self.fol_path.get()
        if not path:
            messagebox.showwarning("Aviso", "Selecciona un archivo PDF.")
            return
        try:
            start = int(self.fol_start.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("Error", "El número inicial debe ser un entero válido.")
            return

        out = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            title="Guardar PDF foliado como...")
        if not out:
            return

        font_size  = self.fol_fontsize.get()
        position   = self.fol_position.get()
        margin     = 22
        overrides  = list(self._fol_overrides)

        def do():
            try:
                reader = PdfReader(path)
                writer = PdfWriter()
                total  = reader.get_num_pages()

                for i in range(total):
                    page = reader.pages[i]
                    # Hornea cualquier /Rotate existente en el contenido de la
                    # página (deja /Rotate=0) para que el folio siempre caiga
                    # en la esquina visual correcta, sin importar si la página
                    # venía rotada (común en escaneos).
                    page.transfer_rotation_to_content()
                    w     = float(page.mediabox.width)
                    h     = float(page.mediabox.height)
                    label = f"{start + i}"
                    dx_cm, dy_cm = 0.0, 0.0
                    for ov in overrides:
                        if ov["start"] <= (i + 1) <= ov["end"]:
                            dx_cm, dy_cm = ov["dx"], ov["dy"]
                            break
                    x_shift = dx_cm * CM_TO_PT
                    y_shift = dy_cm * CM_TO_PT

                    # Capa con el folio generada por reportlab
                    packet = io.BytesIO()
                    c = rl_canvas.Canvas(packet, pagesize=(w, h))
                    c.setFillColorRGB(0, 0, 0)
                    c.setFont("Helvetica-Bold", font_size)

                    if position == "top-right":
                        c.drawRightString(w - margin + x_shift, h - margin - font_size + y_shift, label)
                    elif position == "top-left":
                        c.drawString(margin + x_shift, h - margin - font_size + y_shift, label)
                    elif position == "bottom-right":
                        c.drawRightString(w - margin + x_shift, margin + 4 + y_shift, label)
                    else:
                        c.drawString(margin + x_shift, margin + 4 + y_shift, label)

                    c.save()
                    packet.seek(0)

                    stamp = PdfReader(packet).pages[0]
                    page.merge_page(stamp)
                    writer.add_page(page)
                    self.after(0, lambda pg=i + 1:
                        self._set_status(f"Foliando página {pg}/{total}…"))

                with open(out, "wb") as f:
                    writer.write(f)

                end_folio = start + total - 1
                self.after(0, lambda: messagebox.showinfo("✅ Foliación completada",
                    f"Folios aplicados:    {start}  →  {end_folio}\n"
                    f"Páginas procesadas:  {total}\n\n"
                    f"Guardado en:\n{out}"))
                self._set_status(f"Foliación completada — folios {start} al {end_folio}")

            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error al foliar", str(e)))

        self._run_threaded(do)


if __name__ == "__main__":
    app = PDFManagerApp()
    if HAS_UPDATER:
        app.after(2000, lambda: check_for_updates(app, VERSION))
    app.mainloop()
