"""Build STRIKE3-Macro-Keys.exe with PyInstaller.

    pip install pyinstaller hidapi pystray pillow
    python build_exe.py

The result is dist/STRIKE3-Macro-Keys.exe. It keeps actions.json and gui_settings.json
in the same folder as the .exe, so put it in a folder you can write to.
"""
import os
import subprocess
import sys

from PIL import Image

import macro_gui

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "STRIKE3-Macro-Keys"


def main():
    os.chdir(HERE)
    os.makedirs("build", exist_ok=True)
    icon_path = os.path.join("build", "icon.ico")
    # Draw the icon larger so it stays sharp in Explorer, then let Pillow make the sizes.
    big = macro_gui.make_icon(macro_gui.ACCENT).resize((256, 256), Image.LANCZOS)
    big.save(icon_path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    subprocess.run([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",
        "--windowed",                      # no console window
        "--name", NAME,
        "--icon", icon_path,
        "--hidden-import", "pystray._win32",  # pystray picks its backend at runtime
        "macro_gui.py",
    ], check=True)
    print(f"\nBuilt {os.path.join(HERE, 'dist', NAME + '.exe')}")


if __name__ == "__main__":
    main()
