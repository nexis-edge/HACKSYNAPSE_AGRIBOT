#include "DHT.h"

#define DHTPIN 5
#define DHTTYPE DHT22

DHT am2120(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(9600);

  Serial.println("================================");
  Serial.println("       AM2120 SENSOR TEST");
  Serial.println("================================");

  am2120.begin();

  delay(2000);
}

void loop() {

  float humidity = am2120.readHumidity();
  float temperature = am2120.readTemperature();

  if (isnan(humidity) || isnan(temperature)) {
    Serial.println("ERROR: AM2120 read failed!");
    Serial.println("Check VCC, GND, DATA and pull-up resistor.");
    Serial.println();
    delay(2000);
    return;
  }

  Serial.print("Temperature: ");
  Serial.print(temperature, 2);
  Serial.println(" °C");

  Serial.print("Humidity:    ");
  Serial.print(humidity, 2);
  Serial.println(" %RH");

  Serial.println("----------------------------");

  delay(2000);
}