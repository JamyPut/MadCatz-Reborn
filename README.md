# Mad Catz STRIKE 3 Extra Key Actions

Launches programs or websites when you press the extra keys on a Mad Catz STRIKE 3, without the official software.

## How the codes were found

1. `list_hid.py` listed the keyboard's HID interfaces. The extra keys use usage page `0009` (Button).
2. `read_hid.py` printed the raw bytes for each press, in each mode (red, blue, green).
3. The bits were decoded:
   - Byte 1: `M1`–`M7` are bits 0–6, `C1` is bit 7.
   - Byte 2: high nibble is the mode (`10` red, `20` blue, `40` green), low nibble holds `C2`–`C5`.

## Adding actions

Edit `ACTIONS` in `button_actions.py`, one entry per button per mode:

```python
"red": {
    "C1": r"C:\Users\you\Desktop\app.lnk",
    "M1": "https://www.youtube.com",
},
```

- Program or shortcut: full path with `r` in front.
- Program with arguments: quote the program path, then add arguments.
- Website: full address starting with `https://`.
- Empty `""`: does nothing.

## Running

```
cd %USERPROFILE%\Desktop
python button_actions.py
```

- `cd` changes to your Desktop folder.
- `python` runs the script.

Requires Python 3 and `pip install hid`. Stop with Ctrl+C.

## Disclaimer

Written with the help of an AI assistant (Claude) and tested only on a STRIKE 3 (VID `0738`, PID `1112`) on Windows 11. Not affiliated with Mad Catz. Provided as-is, without warranty. Use at your own risk.
