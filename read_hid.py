import sys
import hid

VID = 0x0738
PID = 0x1112
wanted_page = int(sys.argv[1], 16)

for info in hid.enumerate(VID, PID):
    if info['usage_page'] == wanted_page:
        dev = hid.device()
        dev.open_path(info['path'])
        print(f"Listening on usage page {wanted_page:04X}. Press the extra keys. Ctrl+C to stop.")
        try:
            while True:
                data = dev.read(64, 100)
                if data:
                    print(' '.join(f'{b:02X}' for b in data))
        except KeyboardInterrupt:
            pass
        finally:
            dev.close()
        break
else:
    print("No interface found for that usage page.")