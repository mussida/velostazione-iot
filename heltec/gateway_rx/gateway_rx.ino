#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>

const int PIN_LORA_CS    = 8;
const int PIN_LORA_DIO1  = 14;
const int PIN_LORA_RESET = 12;
const int PIN_LORA_BUSY  = 13;

const int PIN_LORA_SCK   = 9;
const int PIN_LORA_MISO  = 11;
const int PIN_LORA_MOSI  = 10;

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

void setup() {
  Serial.begin(115200);
  delay(2000);

  loraSPI.begin(PIN_LORA_SCK, PIN_LORA_MISO, PIN_LORA_MOSI, PIN_LORA_CS);

  int state = radio.begin(
    FREQUENZA,
    BANDWIDTH,
    SPREADING_FACTOR,
    CODING_RATE,
    SYNC_WORD,
    POTENZA
  );

  if (state != RADIOLIB_ERR_NONE) {
    Serial.println(F("ERROR LoRa"));
    exit(0);
  }

  radio.setCRC(true);
  Serial.println(F("RX LoRa ready"));
}

void loop() {
  String msg;
  int state = radio.receive(msg);

  if (state == RADIOLIB_ERR_NONE) {
    float rssi = radio.getRSSI();
    Serial.print(msg);
    Serial.print(" RSSI=");
    Serial.println(rssi);
  }
}
