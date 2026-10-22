import hid

for d in hid.enumerate():
    print(
        f"VID={d['vendor_id']:04X}  PID={d['product_id']:04X}  "
        f"usage_page={d['usage_page']:04X}  usage={d['usage']:04X}  "
        f"{d['product_string']}"
    )