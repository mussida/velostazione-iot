#!/usr/bin/env python3
import serial
import requests
import loging
import time
import sys
import signal


SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200
SERIAL_TIMEOUT = 1.0

BACKEND_URL = "http://192.168.1.52:8000/api/core/iot/events"
HTTP_TIMEOUT = 5.0

DEVICE_KEYS = {
    12: "e037ba73d57ab53532cece85d419663f44d15d175093e0f73345b71008c5b7d5",
}

def parse_line(line: str):
    line = line.strip()
    if not line:
        return None
    
    if " " in line:
        first_token = line.split(" ", 1)[0]
    else:
        first_token = line

    if not first_token.startswith("node="):
        return None

    parts = first_token.split(";")
    data = {}
    for p in parts:
        if "=" not in p:
            continue
        key, value = p.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        data[key] = value

    if "node" not in data or "seq" not in data or "ev" not in data:
        print(f"Unvalid line: {line}")
        return None
    try:
        data["node"] = int(data["node"])
        data["seq"] = int(data["seq"])
        print(f"Parsed data: {data}")
    except ValueError:
        return None
        
    return data


def build_payload(parsed: dict) -> dict:
    node_id = parsed["node"]
    seq = parsed["seq"]
    event_type = parsed["ev"].strip().lower()

    payload = {
        "node_id": node_id,
        "seq": seq,
        "event_type": event_type,
    }
    if event_type == "rfid_scan" and "uid" in parsed:
        payload["rfid_uid"] = parsed["uid"]

    return payload

def main():
    logging.info(f"Seriale {SERIAL_PORT} a {BAUD_RATE} baud")
    try:
        ser = serial.Serial(
            SERIAL_PORT,
            BAUD_RATE,
            timeout=SERIAL_TIMEOUT
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


    while True:
        try:
            raw_bytes = ser.readline()
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)
            continue

        if not raw_bytes:
            continue

        try:
            raw = raw_bytes.decode(errors="ignore").strip()
        except Exception as e:
            print(f"Error: {e}")
            continue

        if not raw:
            continue

        parsed = parse_line(raw)
        if not parsed:
            continue

        node_id = parsed["node"]
        device_key = DEVICE_KEYS.get(node_id)
        if not device_key:
            print(f"No key for node_id={node_id}.")
            continue

        payload = build_payload(parsed)
        headers = {
            "Content-Type": "application/json",
            "X-Device-Key": device_key,
        }

        try:
            resp = requests.post(
                BACKEND_URL,
                json=payload,
                headers=headers,
                timeout=HTTP_TIMEOUT,
            )
        except requests.RequestException as e:
            print(f"Error sending HTTP request: {e}")

def handle_signal(signum, frame):
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    try:
        main()
    except KeyboardInterrupt:
        print("Exiting...")