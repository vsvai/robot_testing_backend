import json
import sys
import paho.mqtt.publish as publish

DEVICE_ID = sys.argv[1]
BROKER    = "65.2.178.186"
TOPIC     = f"devices/{DEVICE_ID}/ota"

payload = {
        "cmd":  "update",
        "url": "http://65.2.78.186/ota_stuff/firmware/test.bin"
        }

publish.single(TOPIC, json.dumps(payload), hostname=BROKER)
print("OTA trigger sent")
