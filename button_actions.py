import json
import os
import subprocess
import sys

try:
    import hid
except ImportError:  # lets the GUI still open for editing without hidapi
    hid = None

VID = 0x0738
PID = 0x1112
USAGE_PAGE = 0x0009  # Button page

MODE_NAMES = {0x10: "red", 0x20: "blue", 0x40: "green"}
MODES = ["red", "blue", "green"]
BUTTONS = ["C1", "C2", "C3", "C4", "C5", "M1", "M2", "M3", "M4", "M5", "M6", "M7"]

# Actions are stored in actions.json next to this file.
# Edit them with macro_gui.py, or by hand. Each value can be:
#   - a program or shortcut path:      C:\Users\you\Desktop\app.lnk
#   - a quoted program plus arguments: "C:\...\brave.exe" --incognito "https://example.com"
#   - a website:                       https://www.youtube.com
#   - empty "" to do nothing
def app_dir():
    """Folder for actions.json and other settings: next to the .exe when built, else next to this file."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(app_dir(), "actions.json")

# Used to create actions.json the first time.
DEFAULT_ACTIONS = {
    "red": {
        "C1": r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\PuTTY (64-bit)\PuTTY.lnk",
        "C2": r'"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" --incognito "https://example.com"',
        "M1": "https://www.youtube.com",
    },
    "blue": {},
    "green": {},
}


def complete_actions(actions):
    """Return a dict with every mode and button present (missing ones become "")."""
    return {
        mode: {btn: str(actions.get(mode, {}).get(btn, "") or "") for btn in BUTTONS}
        for mode in MODES
    }


def load_actions():
    if not os.path.exists(CONFIG_PATH):
        actions = complete_actions(DEFAULT_ACTIONS)
        save_actions(actions)
        return actions
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return complete_actions(json.load(f))


def save_actions(actions):
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(complete_actions(actions), f, indent=2)
    os.replace(tmp, CONFIG_PATH)


def find_device():
    if hid is None:
        return None
    for d in hid.enumerate(VID, PID):
        if d["usage_page"] == USAGE_PAGE:
            return d
    return None


def decode(data):
    a, b = data[0], data[1]
    mode = MODE_NAMES.get(b & 0xF0, f"unknown({b & 0xF0:02X})")
    pressed = set()
    for i in range(7):
        if a & (1 << i):
            pressed.add(f"M{i + 1}")
    if a & 0x80:
        pressed.add("C1")
    for i, name in enumerate(["C2", "C3", "C4", "C5"]):
        if b & (1 << i):
            pressed.add(name)
    return mode, pressed


def launch(target):
    target = target.strip()
    if not target:
        return
    # Wrap the target in quotes unless it already starts with one.
    # Entries with arguments, like "brave.exe" --incognito ..., are already quoted.
    if not target.startswith('"'):
        target = f'"{target}"'
    # "start" opens shortcuts, programs with arguments, and web addresses.
    # The "" after start is the window title it requires when the target is quoted.
    # CREATE_NO_WINDOW stops a cmd window flashing up when run from the GUI / .exe.
    subprocess.Popen(f'start "" {target}', shell=True,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def main():
    if hid is None:
        print("hidapi is not installed. Run: pip install hidapi")
        return
    info = find_device()
    if info is None:
        print("Button interface not found.")
        return

    actions = load_actions()
    mtime = os.path.getmtime(CONFIG_PATH)

    dev = hid.device()
    dev.open_path(info["path"])
    prev = set()
    print("Running. Press Ctrl+C to stop.")
    try:
        while True:
            data = dev.read(64, 100)
            if not data:
                continue
            # Pick up changes saved from the GUI without restarting.
            try:
                new_mtime = os.path.getmtime(CONFIG_PATH)
                if new_mtime != mtime:
                    actions, mtime = load_actions(), new_mtime
                    print("Reloaded actions.json")
            except (OSError, ValueError) as e:
                print("Could not reload actions.json:", e)
            mode, pressed = decode(data)
            # Act only on buttons that just went down, not on release
            for button in pressed - prev:
                target = actions.get(mode, {}).get(button, "")
                if target:
                    print(mode, button, "->", target)
                    launch(target)
            prev = pressed
    except KeyboardInterrupt:
        pass
    finally:
        dev.close()


if __name__ == "__main__":
    main()
