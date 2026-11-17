"""GUI for setting the Mad Catz STRIKE 3 macro keys.

Run with:  python macro_gui.py   (or pythonw macro_gui.py for no console window)
Add --tray to start hidden in the system tray and listening right away.
"""
import argparse
import ctypes
import json
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import font as tkfont

import button_actions as ba

__version__ = "1.0"

try:  # optional: pip install pystray pillow
    import pystray
    from PIL import Image, ImageDraw, ImageTk
except ImportError:
    pystray = None
    Image = None

# ---------- theme ----------
BG = "#0b0b0d"          # window background
PANEL = "#16161a"       # main panel
FIELD = "#212127"       # inputs, keycaps, buttons
BORDER = "#303038"
TEXT = "#ececf0"
MUTED = "#8b8b97"
ACCENT = "#e10600"      # Mad Catz-style red
ACCENT_HOVER = "#ff2a1f"
MODE_COLORS = {"red": "#e10600", "blue": "#1e88ff", "green": "#19c25a"}
IDLE_COLOR = "#5a5a64"

HELP = ('Program or shortcut path  ·  website (https://…)  ·  '
        'quoted program + arguments, e.g.  "C:\\…\\brave.exe" --incognito')

SETTINGS_PATH = os.path.join(ba.app_dir(), "gui_settings.json")

# Names for the Windows objects that keep the app to a single running copy.
MUTEX_NAME = "Local\\STRIKE3MacroKeys.SingleInstance"
SHOW_EVENT_NAME = "Local\\STRIKE3MacroKeys.Show"


class SingleInstance:
    """Windows named mutex + event: the first copy owns the mutex and waits on the event;
    a second copy sets the event (asking the first to show itself) and exits."""
    ERROR_ALREADY_EXISTS = 183
    WAIT_OBJECT_0 = 0
    INFINITE = 0xFFFFFFFF

    def __init__(self):
        self.kernel32 = None
        self.mutex = self.event = None
        self.already_running = False
        if sys.platform != "win32":
            return
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateMutexW.restype = k.CreateEventW.restype = ctypes.c_void_p
        k.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        k.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_bool, ctypes.c_wchar_p]
        k.SetEvent.argtypes = [ctypes.c_void_p]
        k.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k.WaitForSingleObject.restype = ctypes.c_uint32
        self.kernel32 = k
        self.mutex = k.CreateMutexW(None, False, MUTEX_NAME)  # held until the process exits
        self.already_running = ctypes.get_last_error() == self.ERROR_ALREADY_EXISTS
        self.event = k.CreateEventW(None, False, False, SHOW_EVENT_NAME)  # auto-reset

    def ask_first_copy_to_show(self):
        if self.event:
            self.kernel32.SetEvent(self.event)

    def watch(self, on_show):
        """Call on_show (from a background thread) whenever another copy is started."""
        if not self.event:
            return

        def wait():
            while self.kernel32.WaitForSingleObject(self.event, self.INFINITE) == self.WAIT_OBJECT_0:
                on_show()

        threading.Thread(target=wait, daemon=True).start()
DEFAULT_SETTINGS = {"follow_mode": True, "minimize_to_tray": True, "close_to_tray": False}


def load_settings():
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {k: bool(data.get(k, v)) for k, v in DEFAULT_SETTINGS.items()}
    except (OSError, ValueError, AttributeError):
        return dict(DEFAULT_SETTINGS)


def parse_config(data):
    """Check an imported file and return complete actions, or raise ValueError."""
    if not isinstance(data, dict) or not any(isinstance(data.get(m), dict) for m in ba.MODES):
        raise ValueError("This file has no red / blue / green key settings.")
    for mode in ba.MODES:
        for btn, value in data.get(mode, {}).items():
            if not isinstance(value, str):
                raise ValueError(f"{mode} {btn} should be text, not {type(value).__name__}.")
    return ba.complete_actions(data)


class MacroGui:
    def __init__(self, root, start_hidden=False):
        self.root = root
        if start_hidden:
            root.withdraw()
        self.q = queue.Queue()
        self.stop_event = threading.Event()
        self.thread = None
        self.last_mode = None
        self.shown_mode = None
        self.dirty = False
        self.tray = None
        self.view_state = None
        self.told_about_tray = False
        self.chrome_done = False
        self.save_btn = None

        family = "Bahnschrift" if "Bahnschrift" in tkfont.families(root) else "Segoe UI"
        self.f_title = (family, 22, "bold")
        self.f_head = (family, 9, "bold")
        self.f_key = (family, 11, "bold")
        self.f_btn = (family, 9, "bold")
        self.f_body = ("Segoe UI", 10)
        self.f_small = ("Segoe UI", 9)

        try:
            actions = ba.load_actions()
        except (OSError, ValueError) as e:
            messagebox.showerror("actions.json", f"Could not read actions.json:\n{e}\n\nStarting empty.")
            actions = ba.complete_actions({})

        self.vars = {}
        self.key_labels = {}
        for mode in ba.MODES:
            self.vars[mode] = {}
            for btn in ba.BUTTONS:
                v = tk.StringVar(value=actions[mode][btn])
                v.trace_add("write", lambda *_: self.set_dirty(True))
                self.vars[mode][btn] = v

        settings = load_settings()
        self.follow = tk.BooleanVar(value=settings["follow_mode"])
        self.min_to_tray = tk.BooleanVar(value=settings["minimize_to_tray"])
        self.close_to_tray = tk.BooleanVar(value=settings["close_to_tray"])
        for v in (self.follow, self.min_to_tray, self.close_to_tray):
            v.trace_add("write", lambda *_: self.save_settings())

        root.configure(bg=BG)
        self.build()
        self.set_dirty(False)
        self.select_mode("red")
        if Image is not None:
            self.window_icon = ImageTk.PhotoImage(make_icon(ACCENT))
            root.iconphoto(True, self.window_icon)

        root.protocol("WM_DELETE_WINDOW", self.on_close_button)
        root.bind("<Map>", self.on_map)
        root.bind("<Unmap>", self.on_unmap)
        self.start_tray()
        root.after(50, self.poll_queue)

    # ---------- widgets ----------
    def button(self, parent, text, command, primary=False, width=None):
        b = tk.Button(parent, text=text, command=command, font=self.f_btn, fg=TEXT,
                      activeforeground=TEXT, disabledforeground=MUTED, relief="flat", bd=0,
                      highlightthickness=0, padx=12, pady=5, cursor="hand2")
        if width:
            b.config(width=width)
        self.recolor(b, *((ACCENT, ACCENT_HOVER) if primary else (FIELD, BORDER)))
        b.bind("<Enter>", lambda e: b["state"] != "disabled" and b.config(bg=b.colors[1]))
        b.bind("<Leave>", lambda e: b.config(bg=b.colors[0]))
        return b

    @staticmethod
    def recolor(b, bg, hover):
        b.colors = (bg, hover)
        b.config(bg=bg, activebackground=hover)

    def build(self):
        root = self.root
        root.minsize(900, 0)

        # header
        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(header, text="STRIKE 3", font=self.f_title, fg=TEXT, bg=BG).pack(side="left")
        tk.Label(header, text="MACRO KEY CONFIGURATOR", font=self.f_head, fg=ACCENT,
                 bg=BG).pack(side="left", anchor="s", padx=(12, 0), pady=(0, 7))
        tk.Label(header, text=f"v{__version__}", font=self.f_head, fg=MUTED,
                 bg=BG).pack(side="left", anchor="s", padx=(8, 0), pady=(0, 7))
        ind = tk.Frame(header, bg=BG)
        ind.pack(side="right", anchor="s", pady=(0, 6))
        self.dot = tk.Canvas(ind, width=12, height=12, bg=BG, highlightthickness=0)
        self.dot_item = self.dot.create_oval(1, 1, 11, 11, fill=IDLE_COLOR, outline="")
        self.dot.pack(side="left", padx=(0, 7))
        self.ind_text = tk.Label(ind, text="NOT LISTENING", font=self.f_head, fg=MUTED, bg=BG)
        self.ind_text.pack(side="left")
        tk.Frame(root, bg=ACCENT, height=2).pack(fill="x", padx=20, pady=(10, 14))

        # mode tabs
        modebar = tk.Frame(root, bg=BG)
        modebar.pack(fill="x", padx=20)
        self.mode_tabs = {}
        for i, mode in enumerate(ba.MODES):
            tab = tk.Label(modebar, text=f"MODE {i + 1}  ·  {mode.upper()}", font=self.f_btn,
                           bg=PANEL, fg=MUTED, padx=20, pady=9, cursor="hand2")
            tab.pack(side="left", padx=(0, 3))
            tab.bind("<Button-1>", lambda e, m=mode: self.select_mode(m))
            tab.bind("<Enter>", lambda e, m=mode: m != self.shown_mode and self.mode_tabs[m].config(fg=TEXT))
            tab.bind("<Leave>", lambda e, m=mode: m != self.shown_mode and self.mode_tabs[m].config(fg=MUTED))
            self.mode_tabs[mode] = tab

        # key panel
        body = tk.Frame(root, bg=PANEL)
        body.pack(fill="both", expand=True, padx=20)
        self.mode_stripe = tk.Frame(body, height=3, bg=ACCENT)
        self.mode_stripe.pack(fill="x")
        tk.Label(body, text=HELP, font=self.f_small, fg=MUTED, bg=PANEL,
                 anchor="w").pack(fill="x", padx=16, pady=(10, 0))
        pages = tk.Frame(body, bg=PANEL)
        pages.pack(fill="both", expand=True, padx=16, pady=(6, 14))
        pages.rowconfigure(0, weight=1)
        pages.columnconfigure(0, weight=1)
        self.pages = {}
        for mode in ba.MODES:
            page = self.build_page(pages, mode)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[mode] = page

        # actions
        footer = tk.Frame(root, bg=BG)
        footer.pack(fill="x", padx=20, pady=(14, 0))
        self.save_btn = self.button(footer, "SAVE", self.save, primary=True)
        self.save_btn.pack(side="left")
        self.button(footer, "REVERT", self.revert).pack(side="left", padx=(6, 0))
        self.button(footer, "IMPORT…", self.import_config).pack(side="left", padx=(20, 0))
        self.button(footer, "EXPORT…", self.export_config).pack(side="left", padx=(6, 0))
        self.listen_btn = self.button(footer, "START LISTENING", self.toggle_listener)
        self.listen_btn.pack(side="right")

        # options
        opts = tk.Frame(root, bg=BG)
        opts.pack(fill="x", padx=20, pady=(12, 0))
        for text, var, needs_tray in (("Follow keyboard mode", self.follow, False),
                                      ("Minimize to tray", self.min_to_tray, True),
                                      ("Close to tray (X keeps it running)", self.close_to_tray, True)):
            cb = tk.Checkbutton(opts, text=text, variable=var, font=self.f_body, bg=BG, fg=TEXT,
                                selectcolor=FIELD, activebackground=BG, activeforeground=TEXT,
                                disabledforeground=MUTED, highlightthickness=0, bd=0, cursor="hand2")
            cb.pack(side="left", padx=(0, 20))
            if needs_tray and pystray is None:
                cb.config(state="disabled")

        self.status = tk.Label(root, text="", font=self.f_small, fg=MUTED, bg=BG, anchor="w")
        self.status.pack(fill="x", padx=20, pady=(10, 14))
        if ba.hid is None:
            self.listen_btn.config(state="disabled")
            self.status.config(text="hidapi not installed (pip install hidapi)")
        elif pystray is None:
            self.status.config(text="Tray options need: pip install pystray pillow")

    def build_page(self, parent, mode):
        color = MODE_COLORS[mode]
        page = tk.Frame(parent, bg=PANEL)
        page.columnconfigure(1, weight=1)
        row = 0
        for group, keys in (("C KEYS", ba.BUTTONS[:5]), ("M KEYS", ba.BUTTONS[5:])):
            head = tk.Frame(page, bg=PANEL)
            head.grid(row=row, column=0, columnspan=5, sticky="ew", pady=(10 if row else 0, 6))
            tk.Label(head, text=group, font=self.f_head, fg=MUTED, bg=PANEL).pack(side="left")
            tk.Frame(head, bg=BORDER, height=1).pack(side="left", fill="x", expand=True, padx=(10, 0))
            row += 1
            for btn in keys:
                cap = tk.Label(page, text=btn, font=self.f_key, width=4, bg=FIELD, fg=TEXT,
                               highlightthickness=1, highlightbackground=color)
                cap.grid(row=row, column=0, padx=(0, 10), pady=3, sticky="ns")
                self.key_labels[(mode, btn)] = cap
                tk.Entry(page, textvariable=self.vars[mode][btn], font=self.f_body, bg=FIELD, fg=TEXT,
                         insertbackground=TEXT, relief="flat", highlightthickness=1,
                         highlightbackground=BORDER, highlightcolor=color).grid(
                    row=row, column=1, sticky="ew", pady=3, ipady=5, ipadx=4)
                self.button(page, "BROWSE", lambda b=btn: self.browse(mode, b)).grid(
                    row=row, column=2, padx=(8, 0), pady=3, sticky="ns")
                self.button(page, "TEST", lambda b=btn: self.test(mode, b)).grid(
                    row=row, column=3, padx=(4, 0), pady=3, sticky="ns")
                self.button(page, "✕", lambda b=btn: self.vars[mode][b].set(""), width=2).grid(
                    row=row, column=4, padx=(4, 0), pady=3, sticky="ns")
                row += 1
        return page

    def select_mode(self, mode):
        self.shown_mode = mode
        self.pages[mode].tkraise()
        for m, tab in self.mode_tabs.items():
            tab.config(bg=MODE_COLORS[m] if m == mode else PANEL, fg="white" if m == mode else MUTED)
        self.mode_stripe.config(bg=MODE_COLORS[mode])

    def flash(self, mode, btn):
        lbl = self.key_labels[(mode, btn)]
        lbl.config(bg=MODE_COLORS[mode], fg="white")
        self.root.after(300, lambda: lbl.config(bg=FIELD, fg=TEXT))

    # ---------- editing ----------
    def set_dirty(self, dirty):
        self.dirty = dirty
        self.root.title(("* " if dirty else "") + "STRIKE 3 Macro Keys")
        if self.save_btn is not None:
            self.save_btn.config(text="SAVE *" if dirty else "SAVE")
            self.recolor(self.save_btn, *((ACCENT, ACCENT_HOVER) if dirty else (FIELD, BORDER)))

    def current_actions(self):
        return {m: {b: v.get().strip() for b, v in btns.items()} for m, btns in self.vars.items()}

    def set_actions(self, actions):
        for m in ba.MODES:
            for b in ba.BUTTONS:
                self.vars[m][b].set(actions[m][b])

    def browse(self, mode, btn):
        path = filedialog.askopenfilename(
            title=f"Choose what {btn} ({mode}) opens",
            filetypes=[("Programs and shortcuts", "*.exe *.lnk *.bat *.cmd *.url"), ("All files", "*.*")],
        )
        if path:
            self.vars[mode][btn].set(os.path.normpath(path))

    def test(self, mode, btn):
        target = self.vars[mode][btn].get().strip()
        if not target:
            self.status.config(text=f"{mode} {btn} is empty")
            return
        self.flash(mode, btn)
        ba.launch(target)

    def save(self):
        try:
            ba.save_actions(self.current_actions())
        except OSError as e:
            messagebox.showerror("Save failed", str(e))
            return False
        self.set_dirty(False)
        self.status.config(text="Saved to actions.json")
        return True

    def revert(self):
        if self.dirty and not messagebox.askyesno("Revert", "Discard unsaved changes?"):
            return
        self.set_actions(ba.load_actions())
        self.set_dirty(False)
        self.status.config(text="Reverted to actions.json")

    def import_config(self):
        path = filedialog.askopenfilename(title="Import key configuration",
                                          filetypes=[("Key configuration", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                actions = parse_config(json.load(f))
        except (OSError, ValueError) as e:
            messagebox.showerror("Import failed", f"Could not import {os.path.basename(path)}:\n{e}")
            return
        if not messagebox.askyesno("Import", "Replace all key settings (all 3 modes) with this file?"):
            return
        self.set_actions(actions)
        self.set_dirty(True)
        self.status.config(text=f"Imported {os.path.basename(path)} — press SAVE to keep it")

    def export_config(self):
        path = filedialog.asksaveasfilename(title="Export key configuration", defaultextension=".json",
                                            initialfile="strike3_macros.json",
                                            filetypes=[("Key configuration", "*.json")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(ba.complete_actions(self.current_actions()), f, indent=2)
        except OSError as e:
            messagebox.showerror("Export failed", str(e))
            return
        self.status.config(text=f"Exported to {path}")

    def save_settings(self):
        settings = {"follow_mode": self.follow.get(), "minimize_to_tray": self.min_to_tray.get(),
                    "close_to_tray": self.close_to_tray.get()}
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
        except OSError as e:
            self.status.config(text=f"Could not save options: {e}")

    # ---------- listening ----------
    def listening(self):
        return self.thread is not None and self.thread.is_alive()

    def toggle_listener(self):
        if self.listening():
            self.stop_event.set()
            self.listen_btn.config(text="STOPPING…", state="disabled")
        else:
            self.stop_event.clear()
            self.thread = threading.Thread(target=self.listen, daemon=True)
            self.thread.start()

    def listen(self):
        info = ba.find_device()
        if info is None:
            self.q.put(("error", "Keyboard button interface not found"))
            self.q.put(("stopped",))
            return
        dev = ba.hid.device()
        try:
            dev.open_path(info["path"])
            prev = set()
            while not self.stop_event.is_set():
                data = dev.read(64, 100)
                if not data:
                    continue
                mode, pressed = ba.decode(data)
                self.q.put(("mode", mode))
                for btn in pressed - prev:
                    self.q.put(("press", mode, btn))
                prev = pressed
        except (OSError, IOError) as e:
            self.q.put(("error", str(e)))
        finally:
            dev.close()
            self.q.put(("stopped",))

    def poll_queue(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "mode":
                    mode = msg[1]
                    if mode != self.last_mode and mode in self.pages:
                        self.last_mode = mode
                        if self.follow.get():
                            self.select_mode(mode)
                elif kind == "press":
                    _, mode, btn = msg
                    target = self.vars.get(mode, {}).get(btn)
                    target = target.get().strip() if target else ""
                    if (mode, btn) in self.key_labels:
                        self.flash(mode, btn)
                    self.status.config(text=f"{mode} {btn} → {target or '(nothing)'}")
                    if target:
                        ba.launch(target)
                elif kind == "error":
                    self.show_window()
                    messagebox.showerror("Listener", msg[1])
                elif kind == "stopped":
                    self.last_mode = None
                    self.listen_btn.config(state="normal")
                elif kind == "tray":
                    {"show": self.show_window,
                     "toggle": self.toggle_listener,
                     "quit": self.quit_app}[msg[1]]()
        except queue.Empty:
            pass
        except tk.TclError:  # window was destroyed by Quit
            return
        self.refresh_state()
        self.root.after(50, self.poll_queue)

    def refresh_state(self):
        """Update the header light, listen button and tray icon when listening/mode changes."""
        listening = self.listening()
        mode = self.last_mode if listening else None
        if (listening, mode) == self.view_state:
            return
        self.view_state = (listening, mode)
        color = MODE_COLORS.get(mode, ACCENT if listening else IDLE_COLOR)
        text = (f"LISTENING · {mode.upper()} MODE" if mode else
                "LISTENING" if listening else "NOT LISTENING")
        self.dot.itemconfig(self.dot_item, fill=color)
        self.ind_text.config(text=text, fg=TEXT if listening else MUTED)
        self.listen_btn.config(text="STOP LISTENING" if listening else "START LISTENING")
        self.recolor(self.listen_btn, *((ACCENT, ACCENT_HOVER) if listening else (FIELD, BORDER)))
        if self.tray is not None:
            self.tray.icon = make_icon(MODE_COLORS.get(mode, IDLE_COLOR))
            self.tray.title = "STRIKE 3 Macro Keys — " + text.lower()
            self.tray.update_menu()

    # ---------- window / system tray ----------
    def start_tray(self):
        if pystray is None:
            return
        # pystray runs in its own thread; its callbacks only queue requests for the Tk thread.
        menu = pystray.Menu(
            pystray.MenuItem("Show", lambda: self.q.put(("tray", "show")), default=True),
            pystray.MenuItem(
                lambda _: "Stop listening" if self.listening() else "Start listening",
                lambda: self.q.put(("tray", "toggle")),
                enabled=lambda _: ba.hid is not None,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: self.q.put(("tray", "quit"))),
        )
        self.tray = pystray.Icon("strike3_macros", make_icon(IDLE_COLOR), "STRIKE 3 Macro Keys", menu)
        self.tray.run_detached()

    def on_map(self, event):
        if event.widget is self.root and not self.chrome_done:
            self.chrome_done = True
            dark_title_bar(self.root)

    def on_unmap(self, event):
        # Fires for every widget; only react when the main window itself is minimized.
        if (event.widget is self.root and self.root.state() == "iconic"
                and self.min_to_tray.get() and self.tray is not None):
            self.root.withdraw()

    def show_window(self):
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        # Windows only lets the foreground app steal focus; briefly going topmost
        # makes sure the window really comes to the front when another copy asks.
        self.root.attributes("-topmost", True)
        self.root.after(200, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

    def on_close_button(self):
        if self.close_to_tray.get() and self.tray is not None:
            self.root.withdraw()
            if not self.told_about_tray:
                self.told_about_tray = True
                try:
                    self.tray.notify("Still running in the tray. Right-click the icon to quit.",
                                     "STRIKE 3 Macro Keys")
                except Exception:
                    pass
            return
        self.quit_app()

    def quit_app(self):
        if self.dirty:
            self.show_window()
            answer = messagebox.askyesnocancel("Unsaved changes", "Save changes before closing?")
            if answer is None:
                return
            if answer and not self.save():
                return
        self.stop_event.set()
        if self.tray is not None:
            self.tray.stop()
        self.root.destroy()


def dark_title_bar(root):
    """Windows 11: dark title bar with a red border. Silently does nothing elsewhere."""
    if sys.platform != "win32":
        return

    def colorref(hex_color):
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
        return r | (g << 8) | (b << 16)

    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        for attribute, value in ((20, 1),                  # immersive dark mode
                                 (35, colorref(BG)),       # caption colour
                                 (34, colorref(ACCENT))):  # border colour
            v = ctypes.c_int(value)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(v), ctypes.sizeof(v))
    except (AttributeError, OSError):
        pass


def make_icon(color):
    """Draw a small keyboard in the given colour for the tray and window icon."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 14, 62, 50), radius=8, fill=color)
    for row, y in enumerate((20, 30)):
        for x in range(8 + row * 3, 54, 10):
            d.rectangle((x, y, x + 6, y + 6), fill="white")
    d.rectangle((16, 40, 48, 45), fill="white")  # space bar
    return img


def main():
    parser = argparse.ArgumentParser(description="Set and run the Mad Catz STRIKE 3 macro keys.")
    parser.add_argument("--tray", action="store_true",
                        help="start hidden in the system tray and start listening right away")
    parser.add_argument("--version", action="version", version=f"STRIKE 3 Macro Keys {__version__}")
    args = parser.parse_args()

    instance = SingleInstance()
    if instance.already_running:
        # Bring the running copy to the front instead of opening a second one.
        # A --tray start (e.g. at login) leaves the running copy where it is.
        if not args.tray:
            instance.ask_first_copy_to_show()
        return

    root = tk.Tk()
    hide = args.tray and pystray is not None
    app = MacroGui(root, start_hidden=hide)
    instance.watch(lambda: app.q.put(("tray", "show")))
    if args.tray:
        if ba.hid is not None:
            app.toggle_listener()
        if not hide:  # no tray support installed: fall back to a normal minimize
            root.iconify()
    root.mainloop()


if __name__ == "__main__":
    main()
