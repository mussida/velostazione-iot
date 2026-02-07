#!/usr/bin/env python3
import serial
import requests
import logging
import time
import sys
import signal

# CONFIGURAZIONE

# Porta seriale su cui è collegata la Heltec GATEWAY (RX LoRa)
SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200
SERIAL_TIMEOUT = 1.0

# Endpoint backend Django
BACKEND_URL = "http://192.168.1.52:8000/api/core/iot/events"
HTTP_TIMEOUT = 5.0

# Mappatura node_id - X-Device-Key
DEVICE_KEYS = {
    12: "e037ba73d57ab53532cece85d419663f44d15d175093e0f73345b71008c5b7d5",
}

# LOGGING
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


# FUNZIONI DI PARSING
def parse_line(line: str):
    """
    Esempi di linea attesa in seriale (dalla Heltec RX):
      node=12;seq=25;ev=occupied
      node=12;seq=30;ev=rfid_scan;uid=ABCD1234
    """
    line = line.strip()
    if not line:
        return None

    # Prendo solo tutto fino al primo spazio (per evitare RSSI ecc)
    if " " in line:
        first_token = line.split(" ", 1)[0]
    else:
        first_token = line

    if not first_token.startswith("node="):
        # Non è una linea del nostro protocollo
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

    # Campi minimi obbligatori
    if "node" not in data or "seq" not in data or "ev" not in data:
        logging.warning(f"Linea non valida (mancano campi base): {line}")
        return None

    # node e seq devono essere numerici
    try:
        data["node"] = int(data["node"])
        data["seq"] = int(data["seq"])
    except ValueError:
        logging.warning(f"node o seq non numerici: {line}")
        return None

    return data


def build_payload(parsed: dict) -> dict:
    """
    Costruisce il payload JSON da mandare al backend.

    Struttura tipica:

      {
        "node_id": 12,
        "seq": 30,
        "event_type": "rfid_scan",
        "rfid_uid": "ABCD1234"  # solo se presente
      }
    """
    node_id = parsed["node"]
    seq = parsed["seq"]
    event_type = parsed["ev"].strip().lower()

    payload = {
        "node_id": node_id,
        "seq": seq,
        "event_type": event_type,
    }

    # Campo opzionale per eventi RFID
    if event_type == "rfid_scan" and "uid" in parsed:
        payload["rfid_uid"] = parsed["uid"]

    return payload


# MAIN
def main():
    logging.info(f"Seriale {SERIAL_PORT} a {BAUD_RATE} baud")
    try:
        ser = serial.Serial(
            SERIAL_PORT,
            BAUD_RATE,
            timeout=SERIAL_TIMEOUT
        )
    except Exception as e:
        logging.error(f"Impossibile aprire la seriale {SERIAL_PORT}: {e}")
        sys.exit(1)

    logging.info("Gateway LoRa e HTTP avviato, in ascolto...")

    while True:
        try:
            raw_bytes = ser.readline()
        except Exception as e:
            logging.error(f"Errore lettura seriale: {e}")
            time.sleep(1)
            continue

        if not raw_bytes:
            continue

        try:
            raw = raw_bytes.decode(errors="ignore").strip()
        except Exception as e:
            logging.error(f"Errore decodifica linea: {e}")
            continue

        if not raw:
            continue

        logging.info(f"RX seriale: {raw}")
        parsed = parse_line(raw)
        if not parsed:
            # linea non riconosciuta come protocollo del mio sistema
            continue

        node_id = parsed["node"]
        device_key = DEVICE_KEYS.get(node_id)
        if not device_key:
            logging.warning(f"Nessuna API key configurata per node_id={node_id}, salto.")
            continue

        payload = build_payload(parsed)
        headers = {
            "Content-Type": "application/json",
            "X-Device-Key": device_key,
        }

        try:
            logging.info(f"→ POST {BACKEND_URL} payload={payload}")
            resp = requests.post(
                BACKEND_URL,
                json=payload,
                headers=headers,
                timeout=HTTP_TIMEOUT,
            )
            logging.info(f"← HTTP {resp.status_code}")

            # Provo a leggere eventuale JSON di risposta
            try:
                logging.info(f"   Response JSON: {resp.json()}")
            except ValueError:
                logging.info(f"   Response text: {resp.text}")

        except requests.RequestException as e:
            logging.error(f"Errore HTTP verso backend: {e}")
            time.sleep(1)


def handle_signal(signum, frame):
    logging.info(f"Segnale {signum} ricevuto, chiudo il gateway.")
    sys.exit(0)


if __name__ == "__main__":
    # Gestione chiusura pulita con Ctrl+C o kill
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        main()
    except KeyboardInterrupt:
        logging.info("Terminazione richiesta dall'utente.")