import subprocess
import hid

VID = 0x0738
PID = 0x1112
USAGE_PAGE = 0x0009  # Button page

MODE_NAMES = {0x10: "red", 0x20: "blue", 0x40: "green"}

# Fill in what each button should do in each mode.
# Write paths with an r in front of the quotes, e.g. r"C:\Program Files\..."
# You can add arguments after the program path, e.g.
#   r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" --incognito "https://example.com"
# Leave a button empty ("") to do nothing.
ACTIONS = {
    "red": {
        "C1": r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\PuTTY (64-bit)\PuTTY.lnk",
        "C2": r'"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" --incognito "https://example.com"',
        "C3": "",
        "C4": "",
        "C5": "",
        "M1": "https://www.youtube.com",
        "M2": "",
        "M3": "",
        "M4": "",
        "M5": "",
        "M6": "",
        "M7": "",
    },
    "blue": {},
    "green": {},
}


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
    # Wrap the target in quotes unless it already starts with one.
    # Entries with arguments, like "brave.exe" --incognito ..., are already quoted.
    if not target.startswith('"'):
        target = f'"{target}"'
    # "start" opens shortcuts, programs with arguments, and web addresses.
    # The "" after start is the window title it requires when the target is quoted.
    subprocess.Popen(f'start "" {target}', shell=True)


def main():
    info = None
    for d in hid.enumerate(VID, PID):
        if d["usage_page"] == USAGE_PAGE:
            info = d
            break
    if info is None:
        print("Button interface not found.")
        return

    dev = hid.device()
    dev.open_path(info["path"])
    prev = set()
    print("Running. Press Ctrl+C to stop.")
    try:
        while True:
            data = dev.read(64, 100)
            if not data:
                continue
            mode, pressed = decode(data)
            # Act only on buttons that just went down, not on release
            for button in pressed - prev:
                target = ACTIONS.get(mode, {}).get(button, "")
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