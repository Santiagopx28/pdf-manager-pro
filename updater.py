"""
Auto-update module for PDF Manager Pro.
Checks GitHub Releases on startup (background thread) and offers in-place replacement.
"""

import os
import sys
import threading
import tempfile
import subprocess
import tkinter as tk
from tkinter import ttk

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

# ── GitHub API ────────────────────────────────────────────────────────────────
RELEASES_URL = "https://api.github.com/repos/Santiagopx28/pdf-manager-pro/releases/latest"
REQUEST_TIMEOUT = 8

# ── Color palette (mirrors pdf_manager.py — no import to avoid circulars) ────
_BG     = "#1E1E2E"
_PANEL  = "#2A2A3E"
_ACCENT = "#7C6AF7"
_TEXT   = "#E2E8F0"
_SUB    = "#94A3B8"
_BORDER = "#3A3A5C"
_DANGER = "#EF4444"
_SUCCESS = "#22C55E"
_HOVER  = "#6D5CE6"


# ── Version helpers ───────────────────────────────────────────────────────────

def _parse_version(v: str) -> tuple:
    """'v1.2.3' or '1.2.3' → (1, 2, 3). Returns (0,0,0) on any error."""
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except Exception:
        return (0, 0, 0)


# ── GitHub API ────────────────────────────────────────────────────────────────

def _get_latest_release():
    """Fetch latest release metadata. Returns dict or None on error/offline."""
    if not _HAS_REQUESTS:
        return None
    try:
        resp = requests.get(
            RELEASES_URL,
            timeout=REQUEST_TIMEOUT,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


# ── Download ──────────────────────────────────────────────────────────────────

def _download_file(url: str, dest: str, progress_cb=None, cancel_flag=None) -> bool:
    """Stream-download url → dest. Returns True on success, False if cancelled or error."""
    try:
        r = requests.get(url, stream=True, timeout=120)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=65536):
                if cancel_flag and cancel_flag.is_set():
                    return False
                if chunk:
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if total and progress_cb:
                        progress_cb(downloaded, total)
        return True
    except Exception:
        return False


# ── Self-replace batch ────────────────────────────────────────────────────────

def _write_replace_batch(current_exe: str, new_exe: str, pid: int) -> str:
    """
    Write a .bat to %TEMP% that waits for the current process to exit,
    copies the new exe over the old one, relaunches, and deletes itself.
    Encoding 'mbcs' = Windows ANSI, required for cmd.exe on non-UTF8 systems.
    """
    bat_path = os.path.join(tempfile.gettempdir(), "pdfmgr_update.bat")
    script = (
        "@echo off\n"
        "setlocal\n"
        f"set CUR_PID={pid}\n"
        ":wait\n"
        f'tasklist /FI "PID eq %CUR_PID%" 2>NUL | find /I "{pid}" >NUL\n'
        "if not errorlevel 1 (\n"
        "    timeout /t 1 /nobreak >NUL\n"
        "    goto wait\n"
        ")\n"
        "timeout /t 2 /nobreak >NUL\n"
        f'copy /Y "{new_exe}" "{current_exe}"\n'
        "if errorlevel 1 (\n"
        f'    echo Error al reemplazar el ejecutable >> "%TEMP%\\pdfmgr_update.log"\n'
        "    exit /b 1\n"
        ")\n"
        f'start "" "{current_exe}"\n'
        'del "%~f0"\n'
    )
    with open(bat_path, "w", encoding="mbcs") as fh:
        fh.write(script)
    return bat_path


# ── UI helpers ────────────────────────────────────────────────────────────────

def _center_over(child: tk.Toplevel, parent: tk.Tk, w: int, h: int):
    parent.update_idletasks()
    px, py = parent.winfo_x(), parent.winfo_y()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    x = px + (pw - w) // 2
    y = py + (ph - h) // 2
    child.geometry(f"{w}x{h}+{x}+{y}")


def _styled_btn(parent, text: str, bg: str, cmd, hover: str = None, width: int = 18):
    btn = tk.Button(
        parent, text=text, bg=bg, fg=_TEXT,
        font=("Segoe UI", 10, "bold"),
        relief="flat", bd=0, cursor="hand2",
        activebackground=hover or bg, activeforeground=_TEXT,
        padx=14, pady=7, width=width,
        command=cmd,
    )
    if hover:
        btn.bind("<Enter>", lambda e: btn.config(bg=hover))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    return btn


# ── Progress dialog ───────────────────────────────────────────────────────────

def _show_progress_dialog(root: tk.Tk, latest_version: str, download_url: str):
    dlg = tk.Toplevel(root)
    dlg.title("Descargando actualización")
    dlg.configure(bg=_BG)
    dlg.resizable(False, False)
    dlg.transient(root)
    dlg.grab_set()
    _center_over(dlg, root, 440, 220)

    cancel_flag = threading.Event()
    _cancelled = [False]

    # Title
    tk.Label(
        dlg, text=f"Descargando versión {latest_version}",
        bg=_BG, fg=_ACCENT, font=("Segoe UI", 12, "bold"),
    ).pack(pady=(20, 4))

    # Status
    status_var = tk.StringVar(value="Iniciando descarga…")
    tk.Label(dlg, textvariable=status_var, bg=_BG, fg=_TEXT,
             font=("Segoe UI", 9)).pack()

    # Progress bar
    bar_frame = tk.Frame(dlg, bg=_BG)
    bar_frame.pack(fill="x", padx=30, pady=(10, 4))
    style = ttk.Style(dlg)
    style.configure("Update.Horizontal.TProgressbar",
                    troughcolor=_PANEL, background=_ACCENT, thickness=12)
    bar = ttk.Progressbar(bar_frame, style="Update.Horizontal.TProgressbar",
                          orient="horizontal", length=380, mode="determinate")
    bar.pack()

    pct_var = tk.StringVar(value="0 %")
    tk.Label(dlg, textvariable=pct_var, bg=_BG, fg=_SUB,
             font=("Segoe UI", 9)).pack(pady=(0, 10))

    def cancel():
        cancel_flag.set()
        _cancelled[0] = True
        dlg.destroy()

    _styled_btn(dlg, "Cancelar", _DANGER, cancel, width=12).pack(pady=(0, 16))

    def _on_progress(downloaded: int, total: int):
        if _cancelled[0]:
            return
        pct = int(downloaded / total * 100)
        mb_done = downloaded / 1_048_576
        mb_total = total / 1_048_576

        def _update():
            bar["value"] = pct
            pct_var.set(f"{pct} %  ({mb_done:.1f} / {mb_total:.1f} MB)")
            status_var.set("Descargando…")
        root.after(0, _update)

    def _do_download():
        tmp_dir = tempfile.gettempdir()
        dest = os.path.join(tmp_dir, f"pdfmgr_update_{latest_version}.exe")

        ok = _download_file(download_url, dest,
                            progress_cb=_on_progress,
                            cancel_flag=cancel_flag)

        if _cancelled[0] or not ok:
            if os.path.exists(dest):
                try:
                    os.remove(dest)
                except Exception:
                    pass
            return

        def _apply():
            if not dlg.winfo_exists():
                return
            status_var.set("Aplicando actualización…")
            bar["value"] = 100
            dlg.update_idletasks()

            if not getattr(sys, "frozen", False):
                # Dev mode: just open the downloaded file location
                import webbrowser
                webbrowser.open(tmp_dir)
                dlg.destroy()
                return

            current_exe = sys.executable
            pid = os.getpid()
            bat = _write_replace_batch(current_exe, dest, pid)
            subprocess.Popen(
                ["cmd.exe", "/C", bat],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
            dlg.destroy()
            root.after(300, root.destroy)

        root.after(0, _apply)

    threading.Thread(target=_do_download, daemon=True).start()


# ── Update-available dialog ───────────────────────────────────────────────────

def _show_update_dialog(root: tk.Tk, current_version: str,
                        latest_version: str, download_url: str):
    dlg = tk.Toplevel(root)
    dlg.title("Actualización disponible")
    dlg.configure(bg=_BG)
    dlg.resizable(False, False)
    dlg.transient(root)
    dlg.grab_set()
    _center_over(dlg, root, 440, 230)

    # Icon + title row
    hdr = tk.Frame(dlg, bg=_BG)
    hdr.pack(fill="x", padx=30, pady=(22, 2))
    tk.Label(hdr, text="⬆  Nueva versión disponible",
             bg=_BG, fg=_ACCENT, font=("Segoe UI", 13, "bold")).pack(anchor="w")

    # Version info
    info = tk.Frame(dlg, bg=_PANEL, padx=16, pady=10)
    info.pack(fill="x", padx=30, pady=8)
    tk.Label(info, text=f"Versión instalada:   {current_version}",
             bg=_PANEL, fg=_SUB, font=("Segoe UI", 9)).pack(anchor="w")
    tk.Label(info, text=f"Versión disponible:  {latest_version}",
             bg=_PANEL, fg=_SUCCESS, font=("Segoe UI", 9, "bold")).pack(anchor="w")

    # Buttons
    btn_row = tk.Frame(dlg, bg=_BG)
    btn_row.pack(pady=(4, 20))

    def _start():
        dlg.destroy()
        _show_progress_dialog(root, latest_version, download_url)

    _styled_btn(btn_row, "Descargar e Instalar", _ACCENT, _start,
                hover=_HOVER, width=22).pack(side="left", padx=6)
    _styled_btn(btn_row, "Recordar luego", "#374151", dlg.destroy,
                hover="#4B5563", width=14).pack(side="left", padx=6)


# ── Public entry point ────────────────────────────────────────────────────────

def check_for_updates(root: tk.Tk, current_version: str):
    """
    Spawn a daemon thread that checks GitHub Releases.
    If a newer .exe asset is found, schedule a dialog on the Tk event loop.
    Never raises — update check is best-effort.
    """
    def _worker():
        try:
            release = _get_latest_release()
            if not release:
                return
            latest = release.get("tag_name", "").lstrip("v")
            if not latest:
                return
            if _parse_version(latest) <= _parse_version(current_version):
                return
            url = next(
                (a["browser_download_url"]
                 for a in release.get("assets", [])
                 if a.get("name", "").lower().endswith(".exe")),
                None,
            )
            if not url:
                return
            root.after(0, lambda: _show_update_dialog(root, current_version, latest, url))
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()
