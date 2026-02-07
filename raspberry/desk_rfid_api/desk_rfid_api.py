#!/usr/bin/env python3
import time
import signal
import sys

from flask import Flask, jsonify
from flask_cors import CORS
from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO

# CONFIGURAZIONE
API_PORT = 5001

ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://192.168.1.51:4200",
    "http://192.168.1.52:4200",
]

BUZZER_PIN = 12


# SETUP - HARDWARE
app = Flask(__name__)
CORS(app, origins=ALLOWED_ORIGINS)

# Lettore RFID desk
reader = SimpleMFRC522()

# Stato globale GPIO
gpio_initialized = False

def init_gpio():
    global gpio_initialized
    if gpio_initialized:
        return

    current_mode = GPIO.getmode()
    if current_mode is None:
        GPIO.setmode(GPIO.BOARD)
    else:
        print(f"GPIO mode già impostato ({current_mode}), non lo cambio.")

    GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
    gpio_initialized = True
    print(f"GPIO inizializzati (BUZZER_PIN = pin {BUZZER_PIN} in BOARD mode)")


def beep(pattern: str = "short"):
    """
    pattern:
      - "short": un beep breve
      - "double": due beep brevi
      - "long": beep più lungo (per errori)
    """
    if not gpio_initialized:
        return

    if pattern == "short":
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        time.sleep(0.08)
        GPIO.output(BUZZER_PIN, GPIO.LOW)

    elif pattern == "double":
        for _ in range(2):
            GPIO.output(BUZZER_PIN, GPIO.HIGH)
            time.sleep(0.08)
            GPIO.output(BUZZER_PIN, GPIO.LOW)
            time.sleep(0.06)

    elif pattern == "long":
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        time.sleep(0.3)
        GPIO.output(BUZZER_PIN, GPIO.LOW)


def cleanup_and_exit(*args):
    print("Pulizia GPIO e uscita")
    try:
        GPIO.cleanup()
    except Exception:
        pass
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup_and_exit)
signal.signal(signal.SIGTERM, cleanup_and_exit)


# ENDPOINTS
@app.route("/health", methods=["GET"])
def health():
    """Semplice endpoint di health-check."""
    return jsonify({"status": "ok"}), 200


@app.route("/api/rfid/read-once", methods=["GET"])
def read_once():
    """
    Lettura BLOCCANTE di un singolo tag RFID.

    Flusso:
      - beep corto all'inizio (pronto)
      - attende che l'utente appoggi un tag
      - alla lettura: beep doppio e restituisce UID HEX (normalizzato)
    """
    init_gpio() 
    try:
        print("[read-once] In attesa di un tag RFID...")

        beep("short")

        # Blocca finché non viene letto un tag
        uid_int, text = reader.read()

        # UID completo in HEX
        uid_hex_full = format(uid_int, "X").upper()
        uid_hex = uid_hex_full[:8]

        print(f"Tag letto: UID_INT={uid_int} UID_HEX_FULL={uid_hex_full} UID_HEX_USED={uid_hex}")

        # beep di conferma (tag letto correttamente)
        beep("double")

        return jsonify({
            "uid_hex": uid_hex
        }), 200

    except Exception as e:
        print(f"Errore durante la lettura RFID: {e}")
        beep("long")
        return jsonify({
            "detail": str(e)
        }), 500


# MAIN
if __name__ == "__main__":
    print("Desk RFID API avviata (buzzer + RC522)")
    print(f"Ascolto su http://0.0.0.0:{API_PORT}")
    init_gpio()
    try:
        app.run(host="0.0.0.0", port=API_PORT)
    finally:
        cleanup_and_exit()
