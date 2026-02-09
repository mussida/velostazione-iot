#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>
#include <MFRC522.h>

const int ID_STALLO = 12;

const int PIN_LORA_CS    = 8;   
const int PIN_LORA_DIO1  = 14;  
const int PIN_LORA_RESET = 12;  
const int PIN_LORA_BUSY  = 13;  

const int PIN_LORA_SCK   = 9;
const int PIN_LORA_MISO  = 11;
const int PIN_LORA_MOSI  = 10;

const int PIN_RFID_SCK   = 36;
const int PIN_RFID_MOSI  = 35;
const int PIN_RFID_MISO  = 34;
const int PIN_RFID_SS    = 33;
const int PIN_RFID_RST   = 21;

const int PIN_BUZZER = 45;

const float FREQUENZA        = 868.0;
const float BANDWIDTH        = 125.0;
const int   SPREADING_FACTOR = 9;
const int   CODING_RATE      = 7;
const int   SYNC_WORD        = 0x34;
const int   POTENZA          = 14;

SPIClass loraSPI(HSPI);

SX1262 radio = new Module(
  PIN_LORA_CS,
  PIN_LORA_DIO1,
  PIN_LORA_RESET,
  PIN_LORA_BUSY,
  loraSPI
);

MFRC522 rfid(PIN_RFID_SS, PIN_RFID_RST);

unsigned int seq = 0;

String lastUidHex = "";
bool lastTagPresent = false;
unsigned long lastTagMillis = 0;
const unsigned long TAG_COOLDOWN_MS = 2000;

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

void initLoRa() {
  loraSPI.begin(PIN_LORA_SCK, PIN_LORA_MISO, PIN_LORA_MOSI, PIN_LORA_CS);
  int state = radio.begin(
    FREQUENZA,
    BANDWIDTH,
    SPREADING_FACTOR,
    CODING_RATE,
    SYNC_WORD,
    POTENZA
  );

  if (state == RADIOLIB_ERR_NONE) {
    Serial.println(F("LoRa OK"));
  } else {
    Serial.println(F("ERROR LoRa."));
    beepLong(); 
    exit(0);
  }

  radio.setCRC(true);
  radio.setCurrentLimit(140);
  Serial.println(F("TX LoRa ready \n"));
}

bool sendLoRaMessage(String msg) {
  Serial.println(msg);

  int state = radio.transmit(msg);

  if (state == RADIOLIB_ERR_NONE) {
    seq++;
    return true;
  } else {
    Serial.print(F("ERROR TX: "));
    Serial.println(state);
    return false;
  }
}

void sendRfidScanEvent(const String &uidHex) {
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

void initRFID() {
  SPI.begin(PIN_RFID_SCK, PIN_RFID_MISO, PIN_RFID_MOSI, PIN_RFID_SS);

  rfid.PCD_Init();
  delay(50);

  byte v = rfid.PCD_ReadRegister(rfid.VersionReg);
  if (v == 0x00 || v == 0xFF) {
    beepLong();
  } else {
    beepShort();
  }
}

bool checkRfidAndSendIfNeeded() {
  if (!rfid.PICC_IsNewCardPresent()) {
    if (lastTagPresent) {
      lastTagPresent = false;
      lastUidHex = "";
    }
    return false;
  }

  if (!rfid.PICC_ReadCardSerial()) {
    return false;
  }

  String uidHex = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) {
      uidHex += '0';
    }
    uidHex += String(rfid.uid.uidByte[i], HEX);
  }
  uidHex.toUpperCase();

  unsigned long now = millis();
  bool isNewUid = (uidHex != lastUidHex);
  bool shouldSend = false;

  if (isNewUid) {
    shouldSend = true;
  } else {
    if (!lastTagPresent) {
      shouldSend = true;
    }
  }

  lastTagPresent = true;
  lastUidHex = uidHex;
  lastTagMillis = now;

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();

  if (shouldSend) {
    sendRfidScanEvent(uidHex);
  }

  return shouldSend;
}

void setup() {
  Serial.begin(115200);
  delay(2000);

  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);

  beepShort();

  initLoRa();
  initRFID();
}

void loop() {
  checkRfidAndSendIfNeeded();
  delay(50);
}
