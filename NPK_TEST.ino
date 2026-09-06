#include <SoftwareSerial.h>

#define RE_DE 2
#define RX_PIN 10
#define TX_PIN 11

SoftwareSerial rs485(RX_PIN, TX_PIN);

// Common NPK sensor Modbus address
#define SENSOR_ID 0x01

void setup() {
  Serial.begin(9600);
  rs485.begin(9600);

  pinMode(RE_DE, OUTPUT);
  digitalWrite(RE_DE, LOW);

  Serial.println("================================");
  Serial.println(" AgriBot NPK Sensor Test");
  Serial.println("================================");
  Serial.println("Place sensor in soil...");
  Serial.println();
}

void loop() {

  uint16_t nitrogen  = readRegister(0x001E);
  uint16_t phosphorus = readRegister(0x001F);
  uint16_t potassium = readRegister(0x0020);

  Serial.println("----------------------------");

  if (nitrogen != 65535)
    Serial.print("Nitrogen (N): ");
  if (nitrogen != 65535)
    Serial.print(nitrogen);
  else
    Serial.print("N: ERROR");

  Serial.println(" mg/kg");

  if (phosphorus != 65535) {
    Serial.print("Phosphorus (P): ");
    Serial.print(phosphorus);
    Serial.println(" mg/kg");
  } else {
    Serial.println("Phosphorus (P): ERROR");
  }

  if (potassium != 65535) {
    Serial.print("Potassium (K): ");
    Serial.print(potassium);
    Serial.println(" mg/kg");
  } else {
    Serial.println("Potassium (K): ERROR");
  }

  delay(2000);
}


// =====================================
// Read one Modbus holding register
// =====================================

uint16_t readRegister(uint16_t reg) {

  byte request[8];

  request[0] = SENSOR_ID;
  request[1] = 0x03;
  request[2] = highByte(reg);
  request[3] = lowByte(reg);
  request[4] = 0x00;
  request[5] = 0x01;

  uint16_t crc = modbusCRC(request, 6);

  request[6] = lowByte(crc);
  request[7] = highByte(crc);

  while (rs485.available())
    rs485.read();

  // Transmit mode
  digitalWrite(RE_DE, HIGH);
  delay(2);

  rs485.write(request, 8);
  rs485.flush();

  // Receive mode
  digitalWrite(RE_DE, LOW);

  unsigned long timeout = millis();

  byte response[7];
  int index = 0;

  while (millis() - timeout < 500) {

    if (rs485.available()) {

      response[index++] = rs485.read();

      if (index >= 7)
        break;
    }
  }

  if (index != 7)
    return 65535;

  // Check CRC
  uint16_t receivedCRC =
    response[5] | (response[6] << 8);

  uint16_t calculatedCRC =
    modbusCRC(response, 5);

  if (receivedCRC != calculatedCRC)
    return 65535;

  // Check sensor ID and function
  if (response[0] != SENSOR_ID ||
      response[1] != 0x03)
    return 65535;

  uint16_t value =
    (response[3] << 8) | response[4];

  return value;
}


// =====================================
// Modbus CRC16
// =====================================

uint16_t modbusCRC(byte *data, byte length) {

  uint16_t crc = 0xFFFF;

  for (byte i = 0; i < length; i++) {

    crc ^= data[i];

    for (byte j = 0; j < 8; j++) {

      if (crc & 0x0001)
        crc = (crc >> 1) ^ 0xA001;
      else
        crc >>= 1;
    }
  }

  return crc;
}