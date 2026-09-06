#define STEP_PIN 3
#define DIR_PIN 4
#define EN_PIN 5

void setup() {

  Serial.begin(9600);

  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(EN_PIN, OUTPUT);

  // Enable driver
  digitalWrite(EN_PIN, LOW);

  Serial.println("================================");
  Serial.println("     AgriBot STEPPER TEST");
  Serial.println("================================");
  Serial.println("Starting test...");
}

void loop() {

  // =========================
  // CLOCKWISE
  // =========================

  Serial.println("Direction: FORWARD");

  digitalWrite(DIR_PIN, HIGH);

  for (int i = 0; i < 200; i++) {

    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(1000);

    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(1000);
  }

  delay(1000);


  // =========================
  // ANTICLOCKWISE
  // =========================

  Serial.println("Direction: REVERSE");

  digitalWrite(DIR_PIN, LOW);

  for (int i = 0; i < 200; i++) {

    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(1000);

    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(1000);
  }

  delay(1000);
}