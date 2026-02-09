#!/usr/bin/env python3
import time
import signal
import sys
from enum import Enum

from flask import Flask, jsonify
from flask_cors import CORS
from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO

API_PORT = 5001

ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://192.168.1.51:4200",
    "http://192.168.1.52:4200",
]

BUZZER_PIN = 12


app = Flask(__name__)
CORS(app, origins=ALLOWED_ORIGINS)

reader = SimpleMFRC522()

gpio_initialized = False
class Pattern(Enum):
    SHORT = "short"
    DOUBLE = "double"
    LONG = "long"
    
def init_gpio():
    global gpio_initialized
    if gpio_initialized:
        return

    current_mode = GPIO.getmode()
    if current_mode is None:
        GPIO.setmode(GPIO.BOARD)

    GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
    gpio_initialized = True

def beep(pattern: Pattern):
    if not gpio_initialized:
        return

    if pattern == Pattern.SHORT:
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        time.sleep(0.08)
        GPIO.output(BUZZER_PIN, GPIO.LOW)

    elif pattern == Pattern.DOUBLE:
        for _ in range(2):
            GPIO.output(BUZZER_PIN, GPIO.HIGH)
            time.sleep(0.08)
            GPIO.output(BUZZER_PIN, GPIO.LOW)
            time.sleep(0.06)

    elif pattern == Pattern.LONG:
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        time.sleep(0.3)
        GPIO.output(BUZZER_PIN, GPIO.LOW)


def cleanup_and_exit(*args):
    try:
        GPIO.cleanup()
    except Exception:
        pass
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup_and_exit)
signal.signal(signal.SIGTERM, cleanup_and_exit)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/api/rfid/read-once", methods=["GET"])
def read_once():
    init_gpio() 
    try:
        beep("short")
        uid_int, text = reader.read()
        uid_hex_full = format(uid_int, "X").upper()
        uid_hex = uid_hex_full[:8]

        beep("double")

        return jsonify({
            "uid_hex": uid_hex
        }), 200

    except Exception as e:
        beep("long")
        return jsonify({
            "detail": str(e)
        }), 500


if __name__ == "__main__":
    init_gpio()
    try:
        print(f"Listening on http://0.0.0.0:{API_PORT}")  
        app.run(host="0.0.0.0", port=API_PORT)
    finally:
        cleanup_and_exit()
