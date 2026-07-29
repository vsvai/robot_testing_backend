import sys
import requests

DEV_FILE = "device.txt"

if len(sys.argv) != 3:
    print("Usage: python ota.py firmware.bin MAC")
    sys.exit()

bin_path = sys.argv[1]
target_mac = sys.argv[2]#.lower()

ip = None

with open(DEV_FILE) as f:
    for line in reversed(f.readlines()):
        _,mac, addr = line.strip().split(",")
        if mac == target_mac:
            ip = addr
            break


if not ip:
    print("MAC not found")
    sys.exit(1)


url = f"http://{ip}/ota"

with open(bin_path, "rb") as fw:
    r = requests.post(
                url,
                files = {"file": fw},
                timeout = 30
            )

if r.status_code == 200:
    print("OTA SUCCESS")
else:
    print("OTA FAILED: ", r.text)
