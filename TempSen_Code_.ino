#include <OneWire.h>
#include <DallasTemperature.h>

#define ONE_WIRE_BUS 2
#define MAX_SENSORS 4

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

DeviceAddress sensorAddress[MAX_SENSORS];

int sensorCount = 0;

void setup() {

  Serial.begin(9600);

  Serial.println();
  Serial.println("================================");
  Serial.println("   AgriBot DS18B20 TEST");
  Serial.println("================================");

  sensors.begin();

  sensorCount = sensors.getDeviceCount();

  Serial.print("Sensors detected: ");
  Serial.println(sensorCount);

  if (sensorCount == 0) {
    Serial.println("ERROR: No DS18B20 sensors detected!");
    Serial.println("Check wiring and 4.7K resistor.");
    return;
  }

  if (sensorCount > MAX_SENSORS) {
    sensorCount = MAX_SENSORS;
  }

  Serial.println();
  Serial.println("Sensor Addresses:");
  Serial.println("----------------------------");

  for (int i = 0; i < sensorCount; i++) {

    if (sensors.getAddress(sensorAddress[i], i)) {

      Serial.print("Sensor ");
      Serial.print(i + 1);
      Serial.print(": ");

      printAddress(sensorAddress[i]);

      Serial.println();
    }
  }

  Serial.println();
  Serial.println("Starting temperature test...");
  Serial.println();
}


void loop() {

  if (sensorCount == 0) {
    delay(2000);
    return;
  }

  sensors.requestTemperatures();

  Serial.println("----------------------------");

  for (int i = 0; i < sensorCount; i++) {

    float temperature =
      sensors.getTempC(sensorAddress[i]);

    Serial.print("Sensor ");
    Serial.print(i + 1);
    Serial.print(": ");

    if (temperature == DEVICE_DISCONNECTED_C) {

      Serial.println("DISCONNECTED");

    } else {

      Serial.print(temperature, 2);
      Serial.println(" °C");
    }
  }

  Serial.println("----------------------------");

  delay(2000);
}


// Print DS18B20 unique address
void printAddress(DeviceAddress address) {

  for (uint8_t i = 0; i < 8; i++) {

    if (address[i] < 16)
      Serial.print("0");

    Serial.print(address[i], HEX);

    if (i < 7)
      Serial.print(":");
  }
}