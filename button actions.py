import os
import hid

VID = 0x0738
PID = 0x1112
USAGE_PAGE = 0x0009  # Button page

MODE_NAMES = {0x10: "red", 0x20: "blue", 0x40: "green"}

# Fill in what each button should do in each mode.
# Put a path to a program (e.g. r"C:\Program Files\...\app.exe")
# or a web address (e.g. "https://www.youtube.com").
# Leave a button empty ("") to do nothing.
ACTIONS = {
    "red": {
        "C1": "",
        "C2": "",
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
                    os.startfile(target)
            prev = pressed
    except KeyboardInterrupt:
        pass
    finally:
        dev.close()


if __name__ == "__main__":
    main()