#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>
#include <MFRC522.h>

// Configurazione nodo
// ID del nodo stallo (match con LoRaDevice.node_id nel backend)
const int ID_STALLO = 12;

// PIN LoRa SX1262 (Heltec WiFi LoRa 32 v3)
const int PIN_LORA_CS    = 8;   
const int PIN_LORA_DIO1  = 14;  
const int PIN_LORA_RESET = 12;  
const int PIN_LORA_BUSY  = 13;  

const int PIN_LORA_SCK   = 9;
const int PIN_LORA_MISO  = 11;
const int PIN_LORA_MOSI  = 10;

// PIN RC522 (come da cablaggio Heltec - RC522)
const int PIN_RFID_SCK   = 36;
const int PIN_RFID_MOSI  = 35;
const int PIN_RFID_MISO  = 34;
const int PIN_RFID_SS    = 33;
const int PIN_RFID_RST   = 21;

// BUZZER (attivo 3.3V)
const int PIN_BUZZER = 45;

// Parametri LoRa (identici al gateway)
const float FREQUENZA        = 868.0;
const float BANDWIDTH        = 125.0;
const int   SPREADING_FACTOR = 9;
const int   CODING_RATE      = 7;
const int   SYNC_WORD        = 0x34;
const int   POTENZA          = 14;

// OGGETTI GLOBALI
// Bus SPI dedicato a LoRa 
SPIClass loraSPI(HSPI);

// RadioLib SX1262 collegato al bus SPI dedicato
SX1262 radio = new Module(
  PIN_LORA_CS,
  PIN_LORA_DIO1,
  PIN_LORA_RESET,
  PIN_LORA_BUSY,
  loraSPI
);

// RC522 usa il bus SPI "globale"
MFRC522 rfid(PIN_RFID_SS, PIN_RFID_RST);


// STATO INTERNO
unsigned int seq = 0;  // sequence number per dedup nel backend

// Anti-spam RFID
String lastUidHex = "";
bool lastTagPresent = false;
unsigned long lastTagMillis = 0;
const unsigned long TAG_COOLDOWN_MS = 2000;  // opzionale

// FUNZIONI BUZZER
void beep(unsigned int durationMs = 80) {
  digitalWrite(PIN_BUZZER, HIGH);
  delay(durationMs);
  digitalWrite(PIN_BUZZER, LOW);
}

void beepShort() {
  beep(80);
}

void beepDouble() {
  for (int i = 0; i < 2; i++) {
    beep(60);
    delay(80);
  }
}

void beepLong() {
  beep(300);
}

// FUNZIONI LoRa
void initLoRa() {
  Serial.println(F("Configuro SPI per LoRa..."));

  // Bus SPI dedicato a LoRa
  loraSPI.begin(PIN_LORA_SCK, PIN_LORA_MISO, PIN_LORA_MOSI, PIN_LORA_CS);

  Serial.println(F("Inizializzo LoRa..."));
  int state = radio.begin(
    FREQUENZA,
    BANDWIDTH,
    SPREADING_FACTOR,
    CODING_RATE,
    SYNC_WORD,
    POTENZA
  );

  Serial.print(F("radio.begin() -> "));
  Serial.println(state);

  if (state == RADIOLIB_ERR_NONE) {
    Serial.println(F("LoRa OK"));
  } else {
    Serial.println(F("ERRORE LoRa."));
    beepLong();  // beep lungo di errore
    while (true) {
      delay(1000);
    }
  }

  radio.setCRC(true);
  radio.setCurrentLimit(140);
  Serial.println(F("TX LoRa pronto\n"));
}

bool sendLoRaMessage(String msg) {
  Serial.print(F("TX → "));
  Serial.println(msg);

  int state = radio.transmit(msg);

  if (state == RADIOLIB_ERR_NONE) {
    Serial.println(F("Inviato\n"));
    seq++;
    return true;
  } else {
    Serial.print(F("ERRORE TX: "));
    Serial.println(state);
    // opzionale: beepLong(); // se voglio segnalare errore di TX
    return false;
  }
}

// Costruisce e invia un evento rfid_scan
void sendRfidScanEvent(const String &uidHex) {
  // node=12;seq=NN;ev=rfid_scan;uid=D4484306
  String msg = "node=" + String(ID_STALLO) +
               ";seq=" + String(seq) +
               ";ev=rfid_scan;uid=" + uidHex;

  bool ok = sendLoRaMessage(msg);
  if (ok) {
    beepShort();
  } else {
    beepLong();
  }
}

// FUNZIONI RFID
void initRFID() {
  Serial.println(F("Inizializzo RC522"));

  SPI.begin(PIN_RFID_SCK, PIN_RFID_MISO, PIN_RFID_MOSI, PIN_RFID_SS);

  rfid.PCD_Init();
  delay(50);

  byte v = rfid.PCD_ReadRegister(rfid.VersionReg);
  Serial.print(F("RC522 VersionReg: 0x"));
  Serial.println(v, HEX);

  if (v == 0x00 || v == 0xFF) {
    Serial.println(F("RC522 non risponde."));
    beepLong();
  } else {
    Serial.println(F("RC522 OK."));
    beepShort();
  }
}

// Controlla se c'è un tag nuovo e, se serve, invia rfid_scan
bool checkRfidAndSendIfNeeded() {
  // 1) Nessuna nuova carta - gestisco eventuale rimozione e basta
  if (!rfid.PICC_IsNewCardPresent()) {
    if (lastTagPresent) {
      Serial.println(F("Tag rimosso."));
      lastTagPresent = false;
      lastUidHex = "";
      // opzionale: beepDouble() per indicare rimozione
    }
    return false;
  }

  // 2) Carta presente: provo a leggere il seriale
  if (!rfid.PICC_ReadCardSerial()) {
    return false;
  }

  // 3) Converto UID in stringa HEX maiuscola senza spazi
  String uidHex = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) {
      uidHex += '0';
    }
    uidHex += String(rfid.uid.uidByte[i], HEX);
  }
  uidHex.toUpperCase();

  Serial.print(F("UID HEX letto: "));
  Serial.println(uidHex);

  unsigned long now = millis();
  bool isNewUid = (uidHex != lastUidHex);
  bool shouldSend = false;

  if (isNewUid) {
    // Cambiato tag - evento nuovo
    Serial.println(F("Nuovo UID, invio evento rfid_scan."));
    shouldSend = true;
  } else {
    // Stesso UID
    if (!lastTagPresent) {
      Serial.println(F("Stesso UID ma nuovo appoggio, invio evento."));
      shouldSend = true;
    } else {
      // Tag già presente: non reinvio in continuazione
      if (now - lastTagMillis > TAG_COOLDOWN_MS) {
        Serial.println(F("Cooldown scaduto, ma non reinvio (anti-spam)."));
      } else {
        Serial.println(F("Evento RFID ignorato."));
      }
    }
  }

  // 4) Aggiorno stato interno presenza tag
  lastTagPresent = true;
  lastUidHex = uidHex;
  lastTagMillis = now;

  // 5) Termino comunicazione con la carta
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();

  // 6) Se devo, invio evento
  if (shouldSend) {
    sendRfidScanEvent(uidHex);
  }

  return shouldSend;
}

// SETUP & LOOP
void setup() {
  Serial.begin(115200);
  delay(2000);

  // Buzzer
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);

  Serial.println(F("NODO STALLO - TX LoRa + RC522 + BUZZER"));
  Serial.print(F("ID STALLO = "));
  Serial.println(ID_STALLO);

  beepShort();

  initLoRa();
  initRFID();

  Serial.println(F("Setup completato.\n"));
}

void loop() {
  // Leggo il lettore RFID e invio rfid_scan se c'è un nuovo tap
  checkRfidAndSendIfNeeded();

  delay(50);
}
