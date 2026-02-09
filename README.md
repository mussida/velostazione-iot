# Velostazione IoT

Repository dedicata alla componente **IoT** del progetto *Velostazione di Bologna*.  
Contiene il codice dei nodi LoRa installati sugli stalli e i servizi Python eseguiti sulla postazione desk basata su Raspberry Pi.

Questa repository è separata dai repository del **backend Django** e del **frontend Angular**, al fine di mantenere distinta la logica applicativa dalla parte hardware e di integrazione edge.

---

## Architettura generale

Il sistema IoT è composto da tre elementi principali:

1. **Nodi di stallo**
   - basati su scheda Heltec / ESP32 con radio LoRa SX1262;
   - leggono i tag RFID delle biciclette tramite RC522;
   - inviano eventi LoRa verso il gateway centrale.

2. **Gateway LoRa**
   - una scheda Heltec configurata in modalità RX;
   - collegata via USB al Raspberry Pi;
   - riceve i messaggi LoRa e li inoltra via HTTP al backend.

3. **Postazione di desk (Raspberry Pi)**
   - esegue i servizi Python:
     - gateway LoRa → HTTP;
     - API per la lettura dei tag RFID al desk;
   - funge da punto di integrazione tra mondo fisico e backend applicativo.

---

## Struttura della repository

```text
velostazione-iot/
├── README.md
├── heltec/
│   ├── nodo_stallo/
│   │   └── nodo_stallo.ino
│   └── gateway_rx/
│       └── gateway_rx.ino
├── raspberry/
│   ├── gateway_lora_to_http/
│   │   └── gateway_lora_to_http.py
│   └── desk_rfid_api/
│       └── desk_rfid_api.py
└── docs/
```

---

## Heltec WiFi LoRa 32 v3

La cartella `Heltec/` contiene il codice eseguito sui microcontrollori del sistema IoT.

In particolare include:
- Il codice del **nodo di stallo**, responsabile della lettura RFID, del feedback locale tramite buzzer e dell’invio degli eventi via LoRa;
- Il codice del **gateway LoRa RX**, che riceve i messaggi radio e li espone sulla porta seriale verso il Raspberry Pi.

Gli eventi generati dai nodi sono messaggi testuali a payload minimale, ad esempio:  
`node=12;seq=NN;ev=rfid_scan;uid=52182D06`

Il campo `seq` è un contatore incrementale utilizzato dal backend per la deduplicazione degli eventi.

---

## Servizi su Raspberry Pi

La cartella `raspberry/` raccoglie i servizi Python eseguiti sulla postazione di desk basata su Raspberry Pi.

I servizi svolgono due funzioni distinte:
- Inoltro degli eventi LoRa al backend tramite HTTP;
- Lettura dei tag RFID al desk operatore tramite API locale.

---

## Avvio dei servizi

### Gateway LoRa → HTTP

```bash
cd raspberry/gateway_lora_to_http
python3 -m venv venv
source venv/bin/activate
python3 gateway_lora_to_http.py
```

Il servizio apre la porta seriale della Heltec configurata come gateway RX e inoltra gli eventi al backend Django.

### API Desk RFID

```bash
cd raspberry/desk_rfid_api
python3 -m venv venv
source venv/bin/activate
pip install flask flask-cors mfrc522 RPi.GPIO
python3 desk_rfid_api.py
```

## Integrazione con il backend
Gli eventi provenienti dai nodi di stallo vengono inviati al backend Django tramite l’endpoint: `POST /api/core/iot/events`
Il backend associa ogni evento al dispositivo sorgente e allo stallo logico corrispondente, classificandone l’esito (ad esempio `ok`, `mismatch`, `unknown_rfid`). La deduplicazione degli eventi è basata sulla coppia `(device, seq)`.

