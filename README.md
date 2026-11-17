# Mad Catz STRIKE 3 programmable keys for windows 11

Launches programs, websites or commands when you press the extra keys on a Mad Catz STRIKE 3, without the official software.

- Set every `C1`–`C5` and `M1`–`M7` key, in all 3 modes (red, blue, green), from a GUI.
- Runs in the system tray, can start with Windows.
- Import and export configurations.
- Single `.exe`, no Python needed.

## Download

Get `STRIKE3-Macro-Keys.exe` from the [latest release](https://github.com/JamyPut/MadCatz-Reborn/releases/latest), put it in its own folder and run it.

Put it in a folder you can write to (not `Program Files`): it keeps its settings, `actions.json` and `gui_settings.json`, next to the exe.

Windows SmartScreen may warn the first time because the exe isn't signed. Click **More info → Run anyway**.

## Using the app

- One tab per mode (red, blue, green), one row per key (`C1`–`C5`, `M1`–`M7`).
- Type a target, or use **Browse** to pick a program or shortcut. **Test** runs it right away, **✕** clears it.
- **Save** writes everything to `actions.json`. **Revert** goes back to the last save.
- **Import… / Export…** load or save a full configuration (all 3 modes) as a `.json` file, for backups or for switching between setups. An import only takes effect after **Save**.
- **Start listening** makes the keys work. With *Follow keyboard mode* on, the tab switches when you change mode on the keyboard, and the pressed key lights up.
- With *Minimize to tray* on, minimizing hides the window to the system tray and the keys keep working. Click the tray icon to show the window again, or right-click it to start/stop listening or quit. The icon is grey when not listening and takes the colour of the current mode while listening.
- With *Close to tray* on, the X button also hides to the tray instead of quitting. Use **Quit** in the tray menu to exit.
- These options are remembered in `gui_settings.json`.
- Only one copy runs at a time. Starting it again brings the running copy to the front.

### What a key can do

- Program or shortcut: full path, e.g. `C:\Users\you\Desktop\app.lnk`.
- Program with arguments: quote the program path, then add arguments, e.g. `"C:\...\brave.exe" --incognito "https://example.com"`.
- Website: full address starting with `https://`.
- Empty: does nothing.

You can also edit `actions.json` by hand.

### Start with Windows

`--tray` starts the app hidden in the tray and already listening. If it's already running, it does nothing.

1. Press `Win + R`, type `shell:startup` and press Enter.
2. In that folder, right-click → **New → Shortcut**.
3. As the location, enter (with your own path):
   ```
   "C:\path\to\STRIKE3-Macro-Keys.exe" --tray
   ```

## Running from source

Requires Python 3 (tested with 3.12) on Windows.

```
pip install -r requirements.txt
pythonw macro_gui.py
```

`pythonw` starts it without a console window, `--tray` works the same as for the exe. Without `pystray` and `pillow` the GUI still works, but without the tray icon.

For starting with Windows from source, use this as the shortcut location (`where pythonw` shows the path to `pythonw.exe`):

```
"C:\path\to\pythonw.exe" "C:\path\to\macro_gui.py" --tray
```

### Building the .exe

```
pip install -r requirements.txt pyinstaller
python build_exe.py
```

This creates `dist\STRIKE3-Macro-Keys.exe`.

### Without the GUI

```
python button_actions.py
```

Uses the actions in `actions.json` and reloads them when the file changes. Stop with Ctrl+C. Only needs `hidapi`.

## Files

| File | What it does |
| --- | --- |
| `macro_gui.py` | The GUI app. |
| `button_actions.py` | Reads the keys and launches the actions. Also runs on its own, without the GUI. |
| `build_exe.py` | Builds the `.exe` with PyInstaller. |
| `list_hids.py`, `read_hid.py` | Tools used to find the key codes (see below). |

## How the codes were found

1. `list_hids.py` listed the keyboard's HID interfaces. The extra keys use usage page `0009` (Button).
2. `read_hid.py 0009` printed the raw bytes for each press, in each mode (mode 1, mode 2, mode 3).
3. The bits were decoded:
   - Byte 1: `M1`–`M7` are bits 0–6, `C1` is bit 7.
   - Byte 2: high nibble is the mode (`10` red, `20` blue, `40` green), low nibble holds `C2`–`C5`.

## License

[GNU General Public License v3.0](LICENSE).

## Disclaimer

Written with the help of AI (Claude) and tested only on a STRIKE 3 (VID `0738`, PID `1112`) on Windows 11. Not affiliated with Mad Catz. Provided as-is, without warranty. Use at your own risk.
