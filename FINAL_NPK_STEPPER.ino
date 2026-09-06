// ============================================================
//                    AGRIBOT MEGA V2
// ============================================================
//
// Arduino Mega 2560
//
// FUNCTIONS
// 1. ZTS-3002-TR-THNPKPH NPK via RS485
// 2. Mock DS18B20 motor temperatures x4
// 3. Mock AM2120 canopy temperature + humidity
// 4. NPK arm stepper via TB6600
// 5. Continuous telemetry to Raspberry Pi
// 6. Commands from Raspberry Pi
//
// ============================================================
// PIN CONFIGURATION
// ============================================================
//
// TB6600
// DIR  -> D2
// STEP -> D3
// ENA  -> D4
//
// RS485 MODULE
// DE + RE -> D5
// DI      -> TX1 / D18
// RO      -> RX1 / D19
//
// ============================================================
// SERIAL
// ============================================================
//
// USB Serial:
// Mega <-> Raspberry Pi
// 115200 baud
//
// Serial1:
// Mega <-> RS485
// 4800 baud, 8N1
//
// ============================================================
// NPK MODBUS
// ============================================================
//
// Slave ID = 1
// Function = 03
// Start register = 0x0000
// Registers = 7
//
// 0000 = Moisture
// 0001 = Soil Temperature
// 0002 = Reserved
// 0003 = pH
// 0004 = Nitrogen
// 0005 = Phosphorus
// 0006 = Potassium
//
// ============================================================

#include <ModbusMaster.h>


// ============================================================
// PIN DEFINITIONS
// ============================================================

#define DIR_PIN       2
#define STEP_PIN      3
#define ENA_PIN       4

#define RS485_DE_RE   5


// ============================================================
// STEPPER SETTINGS
// ============================================================

// TB6600 = 200 pulses/revolution
#define STEPS_PER_REV 200

// KEEPING YOUR PROVEN WORKING TIMING
#define STEP_DELAY_US 2000

// Software movement safety limit
#define MAX_REVOLUTIONS 40


// ============================================================
// NPK SETTINGS
// ============================================================

#define MODBUS_SLAVE_ID 1

ModbusMaster npk;


// ============================================================
// SENSOR DATA
// ============================================================

// ---------------- NPK ----------------

float soilMoisture = 0.0;
float soilTemperature = 0.0;
float soilPH = 0.0;

uint16_t nitrogen = 0;
uint16_t phosphorus = 0;
uint16_t potassium = 0;

bool npkCommunicationOK = false;


// ---------------- MOCK MOTOR TEMPERATURES ----------------

float motorTemp1 = 11.0;
float motorTemp2 = 11.5;
float motorTemp3 = 12.0;
float motorTemp4 = 10.5;


// ---------------- MOCK CANOPY ----------------

float canopyTemperature = 28.0;
float canopyHumidity = 65.0;


// ============================================================
// TIMING
// ============================================================

unsigned long lastNPKRead = 0;
unsigned long lastTelemetry = 0;
unsigned long lastMockUpdate = 0;


// NPK polling interval
const unsigned long NPK_INTERVAL = 3000;

// Telemetry interval
const unsigned long TELEMETRY_INTERVAL = 2000;

// Mock data interval
const unsigned long MOCK_INTERVAL = 2500;


// ============================================================
// STEPPER STATE
// ============================================================

bool stepperMoving = false;

bool stepperDirection = true;

long stepperStepsRemaining = 0;

unsigned long lastStepTime = 0;


// ============================================================
// RS485
// ============================================================

void preTransmission()
{
  digitalWrite(RS485_DE_RE, HIGH);

  delayMicroseconds(100);
}


void postTransmission()
{
  delayMicroseconds(100);

  digitalWrite(RS485_DE_RE, LOW);
}


// ============================================================
// START STEPPER MOVEMENT
// ============================================================

void startStepper(bool direction, long steps)
{
  if (steps <= 0)
  {
    return;
  }


  stepperDirection = direction;

  stepperStepsRemaining = steps;

  stepperMoving = true;


  // Enable TB6600
  digitalWrite(
    ENA_PIN,
    LOW
  );


  // Set direction
  digitalWrite(
    DIR_PIN,
    stepperDirection
  );


  // Same direction settling time
  delayMicroseconds(10);


  lastStepTime = micros();
}


// ============================================================
// STOP STEPPER
// ============================================================

void stopStepper()
{
  stepperMoving = false;

  stepperStepsRemaining = 0;


  // Disable motor
  digitalWrite(
    ENA_PIN,
    HIGH
  );


  // Make sure STEP is LOW
  digitalWrite(
    STEP_PIN,
    LOW
  );


  Serial.println(
    "STEPPER_STOPPED"
  );
}


// ============================================================
// NON-BLOCKING STEPPER SERVICE
// ============================================================
//
// This function generates the same pulse timing as your
// working code, but doesn't lock the entire Mega inside
// a large for-loop.
//
// ============================================================

void serviceStepper()
{
  if (!stepperMoving)
  {
    return;
  }


  unsigned long now = micros();


  if (
    now - lastStepTime
    < STEP_DELAY_US
  )
  {
    return;
  }


  lastStepTime = now;


  // If STEP currently LOW -> make HIGH
  if (
    digitalRead(STEP_PIN)
    == LOW
  )
  {
    digitalWrite(
      STEP_PIN,
      HIGH
    );
  }

  // If STEP currently HIGH -> make LOW
  else
  {
    digitalWrite(
      STEP_PIN,
      LOW
    );


    stepperStepsRemaining--;


    if (
      stepperStepsRemaining
      <= 0
    )
    {
      stepperMoving = false;


      digitalWrite(
        ENA_PIN,
        HIGH
      );


      Serial.println(
        "STEPPER_DONE"
      );
    }
  }
}


// ============================================================
// MOVE ARM UP
// ============================================================

void moveArmUp(int revolutions)
{
  if (
    revolutions <= 0
  )
  {
    Serial.println(
      "ERROR_INVALID_REVOLUTIONS"
    );

    return;
  }


  if (
    revolutions > MAX_REVOLUTIONS
  )
  {
    Serial.println(
      "ERROR_REVOLUTION_LIMIT"
    );

    return;
  }


  if (stepperMoving)
  {
    Serial.println(
      "ERROR_STEPPER_BUSY"
    );

    return;
  }


  long steps =
    (long)STEPS_PER_REV
    * revolutions;


  Serial.print(
    "STEPPER_UP "
  );

  Serial.println(
    revolutions
  );


  startStepper(
    true,
    steps
  );
}


// ============================================================
// MOVE ARM DOWN
// ============================================================

void moveArmDown(int revolutions)
{
  if (
    revolutions <= 0
  )
  {
    Serial.println(
      "ERROR_INVALID_REVOLUTIONS"
    );

    return;
  }


  if (
    revolutions > MAX_REVOLUTIONS
  )
  {
    Serial.println(
      "ERROR_REVOLUTION_LIMIT"
    );

    return;
  }


  if (stepperMoving)
  {
    Serial.println(
      "ERROR_STEPPER_BUSY"
    );

    return;
  }


  long steps =
    (long)STEPS_PER_REV
    * revolutions;


  Serial.print(
    "STEPPER_DOWN "
  );

  Serial.println(
    revolutions
  );


  startStepper(
    false,
    steps
  );
}


// ============================================================
// READ NPK
// ============================================================

bool readNPK()
{
  uint8_t result;


  result =
    npk.readHoldingRegisters(
      0x0000,
      7
    );


  if (
    result
    == npk.ku8MBSuccess
  )
  {
    uint16_t reg0 =
      npk.getResponseBuffer(0);

    uint16_t reg1 =
      npk.getResponseBuffer(1);

    uint16_t reg3 =
      npk.getResponseBuffer(3);

    uint16_t reg4 =
      npk.getResponseBuffer(4);

    uint16_t reg5 =
      npk.getResponseBuffer(5);

    uint16_t reg6 =
      npk.getResponseBuffer(6);


    // Same conversions as your
    // previously working code.

    soilMoisture =
      reg0 / 10.0;


    soilTemperature =
      reg1 / 10.0;


    soilPH =
      reg3 / 10.0;


    nitrogen =
      reg4;


    phosphorus =
      reg5;


    potassium =
      reg6;


    npkCommunicationOK =
      true;


    return true;
  }


  npkCommunicationOK =
    false;


  return false;
}


// ============================================================
// UPDATE MOCK DATA
// ============================================================

void updateMockData()
{
  unsigned long now =
    millis();


  if (
    now - lastMockUpdate
    < MOCK_INTERVAL
  )
  {
    return;
  }


  lastMockUpdate =
    now;


  // Motor temperatures
  // 10.0 - 13.0 °C

  motorTemp1 =
    random(100, 131) / 10.0;

  motorTemp2 =
    random(100, 131) / 10.0;

  motorTemp3 =
    random(100, 131) / 10.0;

  motorTemp4 =
    random(100, 131) / 10.0;


  // Canopy temperature
  // 25.0 - 32.0 °C

  canopyTemperature =
    random(250, 321) / 10.0;


  // Canopy humidity
  // 50 - 80 %

  canopyHumidity =
    random(500, 801) / 10.0;
}


// ============================================================
// SEND CONTINUOUS TELEMETRY
// ============================================================
//
// The RPi can parse these lines.
//
// ============================================================

void sendTelemetry()
{
  Serial.print(
    "TELEMETRY,"
  );


  // NPK status

  Serial.print(
    "npk_status="
  );

  Serial.print(
    npkCommunicationOK
    ? "OK"
    : "ERROR"
  );


  // NPK

  Serial.print(
    ",moisture="
  );

  Serial.print(
    soilMoisture,
    1
  );


  Serial.print(
    ",soil_temperature="
  );

  Serial.print(
    soilTemperature,
    1
  );


  Serial.print(
    ",ph="
  );

  Serial.print(
    soilPH,
    1
  );


  Serial.print(
    ",nitrogen="
  );

  Serial.print(
    nitrogen
  );


  Serial.print(
    ",phosphorus="
  );

  Serial.print(
    phosphorus
  );


  Serial.print(
    ",potassium="
  );

  Serial.print(
    potassium
  );


  // Motor temperatures

  Serial.print(
    ",motor1_temperature="
  );

  Serial.print(
    motorTemp1,
    1
  );


  Serial.print(
    ",motor2_temperature="
  );

  Serial.print(
    motorTemp2,
    1
  );


  Serial.print(
    ",motor3_temperature="
  );

  Serial.print(
    motorTemp3,
    1
  );


  Serial.print(
    ",motor4_temperature="
  );

  Serial.print(
    motorTemp4,
    1
  );


  // Canopy

  Serial.print(
    ",canopy_temperature="
  );

  Serial.print(
    canopyTemperature,
    1
  );


  Serial.print(
    ",canopy_humidity="
  );

  Serial.print(
    canopyHumidity,
    1
  );


  // Stepper status

  Serial.print(
    ",stepper="
  );

  Serial.print(
    stepperMoving
    ? "MOVING"
    : "IDLE"
  );


  Serial.print(
    ",steps_remaining="
  );

  Serial.print(
    stepperStepsRemaining
  );


  Serial.println();
}


// ============================================================
// STATUS
// ============================================================

void sendStatus()
{
  Serial.println(
    "STATUS,mega=ONLINE"
  );


  Serial.print(
    "STATUS,npk="
  );

  Serial.println(
    npkCommunicationOK
    ? "OK"
    : "ERROR"
  );


  Serial.print(
    "STATUS,stepper="
  );

  Serial.println(
    stepperMoving
    ? "MOVING"
    : "IDLE"
  );
}


// ============================================================
// PROCESS COMMANDS
// ============================================================

void processCommand(
  String command
)
{
  command.trim();

  command.toUpperCase();


  // --------------------------------------------------------
  // ARM UP
  // Example: UP 10
  // --------------------------------------------------------

  if (
    command.startsWith("UP ")
  )
  {
    int revolutions =
      command.substring(3).toInt();


    moveArmUp(
      revolutions
    );


    return;
  }


  // --------------------------------------------------------
  // ARM DOWN
  // Example: DOWN 10
  // --------------------------------------------------------

  if (
    command.startsWith("DOWN ")
  )
  {
    int revolutions =
      command.substring(5).toInt();


    moveArmDown(
      revolutions
    );


    return;
  }


  // --------------------------------------------------------
  // STOP
  // --------------------------------------------------------

  if (
    command == "STOP"
    ||
    command == "ARM STOP"
  )
  {
    stopStepper();

    return;
  }


  // --------------------------------------------------------
  // STATUS
  // --------------------------------------------------------

  if (
    command == "STATUS"
  )
  {
    sendStatus();

    return;
  }


  // --------------------------------------------------------
  // IMMEDIATE NPK READ
  // --------------------------------------------------------

  if (
    command == "GET_NPK"
  )
  {
    readNPK();

    Serial.println(
      "NPK_READ_COMPLETE"
    );

    return;
  }


  // --------------------------------------------------------
  // UNKNOWN
  // --------------------------------------------------------

  Serial.print(
    "ERROR_UNKNOWN_COMMAND,"
  );

  Serial.println(
    command
  );
}


// ============================================================
// SETUP
// ============================================================

void setup()
{
  // USB serial to RPi
  Serial.begin(
    115200
  );


  // Stepper pins

  pinMode(
    DIR_PIN,
    OUTPUT
  );

  pinMode(
    STEP_PIN,
    OUTPUT
  );

  pinMode(
    ENA_PIN,
    OUTPUT
  );


  digitalWrite(
    STEP_PIN,
    LOW
  );


  digitalWrite(
    ENA_PIN,
    HIGH
  );


  digitalWrite(
    DIR_PIN,
    LOW
  );


  // RS485

  pinMode(
    RS485_DE_RE,
    OUTPUT
  );


  digitalWrite(
    RS485_DE_RE,
    LOW
  );


  // NPK Serial1

  Serial1.begin(
    4800,
    SERIAL_8N1
  );


  // Modbus

  npk.begin(
    MODBUS_SLAVE_ID,
    Serial1
  );


  npk.preTransmission(
    preTransmission
  );


  npk.postTransmission(
    postTransmission
  );


  // Random seed

  randomSeed(
    analogRead(A0)
  );


  // Initial NPK read

  readNPK();


  // Initial mock data

  updateMockData();


  Serial.println(
    "AGRIBOT_MEGA_V2_READY"
  );
}


// ============================================================
// MAIN LOOP
// ============================================================

void loop()
{
  // ========================================================
  // 1. STEPPER SERVICE
  // ========================================================
  //
  // This must run continuously.
  //

  serviceStepper();


  // ========================================================
  // 2. COMMAND SERVICE
  // ========================================================

  if (
    Serial.available()
  )
  {
    String command =
      Serial.readStringUntil(
        '\n'
      );


    processCommand(
      command
    );
  }


  // ========================================================
  // 3. MOCK SENSOR UPDATE
  // ========================================================

  updateMockData();


  // ========================================================
  // 4. NPK UPDATE
  // ========================================================

  unsigned long now =
    millis();


  if (
    now - lastNPKRead
    >= NPK_INTERVAL
  )
  {
    lastNPKRead =
      now;


    readNPK();
  }


  // ========================================================
  // 5. CONTINUOUS TELEMETRY
  // ========================================================

  if (
    now - lastTelemetry
    >= TELEMETRY_INTERVAL
  )
  {
    lastTelemetry =
      now;


    sendTelemetry();
  }
}