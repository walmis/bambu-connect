from .utils.models import PrinterStatus
import json
import ssl
from typing import Any, Callable, Dict, Optional

import paho.mqtt.client as mqtt


class WatchClient:
    def __init__(self, hostname: str, access_code: str, serial: str):
        self.hostname = hostname
        self.access_code = access_code
        self.serial = serial
        self.client = self.__setup_mqtt_client()
        self.values = {}
        self.printerStatus = None
        self.message_callback = None

    def __setup_mqtt_client(self) -> mqtt.Client:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        client.username_pw_set("bblp", self.access_code)
        client.tls_set(tls_version=ssl.PROTOCOL_TLS, cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        return client
    
    # this dumps all the printer stats, for minor print updates the printer will send them automatically.
    def dump_info(self):
        payload = f'{{"pushing": {{ "sequence_id": 1, "command": "pushall"}}, "user_id":"1234567890"}}'
        self.send_command(payload)
        
    def send_command(self, payload):
        self.client.publish(f"device/{self.serial}/request", payload)

    def send_gcode(self, gcode):
        payload = f'{{"print": {{"command": "gcode_line", "sequence_id": 2006, "param": "{gcode} \n"}}, "user_id":"1234567890"}}'
        self.send_command(payload)

    # this dumps all the printer stats, for minor print updates the printer will send them automatically.
    def dump_info(self):
        payload = f'{{"pushing": {{ "sequence_id": 1, "command": "pushall"}}, "user_id":"1234567890"}}'
        self.send_command(payload)

    # when using this, choose the send to printer option in bambu or cura slicer. Provide the file name (no path)
    def start_print(self, file):
        payload = json.dumps(
            {
                "print": {
                    "sequence_id": 13,
                    "command": "project_file",
                    "param": "Metadata/plate_1.gcode",
                    "subtask_name": f"{file}",
                    "url": f"ftp://{file}",
                    "bed_type": "auto",
                    "timelapse": False,
                    "bed_leveling": True,
                    "flow_cali": False,
                    "vibration_cali": True,
                    "layer_inspect": False,
                    "use_ams": False,
                    "profile_id": "0",
                    "project_id": "0",
                    "subtask_id": "0",
                    "task_id": "0",
                }
            }
        )
        self.send_command(payload)

    def on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, rc: int):
        client.subscribe(f"device/{self.serial}/report")
        if self.on_connect_callback:
            self.on_connect_callback()

    def start(
        self,
        message_callback: Optional[Callable[[PrinterStatus], None]] = None,
        on_connect_callback: Optional[Callable[[], None]] = None,
    ):
        self.message_callback = message_callback
        self.on_connect_callback = on_connect_callback
        self.client.loop_start()

        self.client.connect_async(self.hostname, 8883, 60)

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def on_message(self, client, userdata, msg):
        doc = json.loads(msg.payload)
        try:
            if not doc:
                return

            self.values = dict(self.values, **doc["print"])
            self.printerStatus = PrinterStatus(**self.values)

            if self.message_callback:
                self.message_callback(self.printerStatus)
        except KeyError:
            pass
