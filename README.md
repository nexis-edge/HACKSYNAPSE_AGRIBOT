# AgriVaidya

Flask field-operations backend for the AgriBot. It preserves the existing  frontend API and defaults to safe simulation when hardware is absent.

## Windows development

Use Python 3.10+.

    py -3 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    Copy-Item .env.example .env
    python app.py

Open http://localhost:5000. Keep SIMULATION_MODE=true. The server never opens the development computer webcam.

Run tests: python -m pytest -q

## Raspberry Pi deployment

Install Python 3.10+, git, libopencv-dev, and the system packages needed by selected camera, serial, I2C, 1-Wire, and GPIO libraries. Create a virtual environment, install requirements.txt, then install optional hardware packages appropriate for the Pi. Enable I2C/1-Wire and grant the service access to serial/GPIO devices. Configure PIXHAWK_CONNECTION_STRING, NPK_SERIAL_PORT, calibrated GPIO values, model paths, and camera sources in .env. Set SIMULATION_MODE=false only after bench testing.

Run python app.py, or use a system service with this folder as WorkingDirectory and the virtualenv Python as ExecStart.

## Hardware notes

Pixhawk is the low-level controller for real navigation; RC/manual control remains the safety override. The NPK Modbus register map is intentionally not invented and must be supplied before live reads. Battery and solar ADC calibration, ultrasonic tank dimensions, endstops, camera RTSP sources, pump interface, and servo limits require wiring-specific configuration.

## Troubleshooting

Pixhawk unavailable: check PIXHAWK_CONNECTION_STRING, permissions, cable, and heartbeat; use simulation.
NPK unavailable: check RS485 direction control, port permissions, slave ID, baudrate, and provide the verified register map.
Camera unavailable: configure a robot source; no host webcam fallback exists.
GPIO unavailable: use SIMULATION_MODE=true.
Model unavailable: verify DISEASE_MODEL_PATH and optional ultralytics; disease returns 503.
Serial permission errors: add the service account to the serial group.
Simulation mode: values are marked with sensor_sources and connection statuses.

## API curl examples

Set BASE=http://localhost:5000.

    curl $BASE/health
    curl $BASE/data
    curl $BASE/weather
    curl $BASE/robot/forward
    curl $BASE/robot/backward
    curl $BASE/robot/left
    curl $BASE/robot/right
    curl $BASE/robot/stop
    curl $BASE/spray/on
    curl $BASE/spray/off
    curl $BASE/mode/MANUAL
    curl $BASE/mode/AUTO
    curl $BASE/mode/MAINTENANCE
    curl $BASE/mode/EMERGENCY_STOP
    curl $BASE/api/npk-arm/status
    curl -X POST $BASE/api/npk-arm/move -H "Content-Type: application/json" -d '{"steps":200,"speed":400,"direction":1}'
    curl -X POST $BASE/api/npk-arm/stop
    curl $BASE/camera/top
    curl $BASE/camera/bottom
    curl $BASE/camera/drone
    curl "$BASE/camera/top/servo?angle=90"
    curl -X POST $BASE/drone/arm
    curl -X POST $BASE/drone/disarm
    curl -X POST $BASE/drone/takeoff -H "Content-Type: application/json" -d '{"altitude":5}'
    curl -X POST $BASE/drone/land
    curl -X POST $BASE/drone/mode/GUIDED
    curl $BASE/drone/telemetry
    curl $BASE/drone/status
    curl -F image=@plant.jpg $BASE/disease/predict
    curl -F image=@soil.jpg $BASE/soil/predict
    curl $BASE/logs
    curl -X POST $BASE/mission/start -H "Content-Type: application/json" -d '{"mission_name":"Demo"}'
    curl -X POST $BASE/mission/pause
    curl -X POST $BASE/mission/stop
    curl $BASE/mission/status

Emergency stop:

    curl $BASE/mode/EMERGENCY_STOP
    curl $BASE/robot/forward
    curl $BASE/spray/on
    curl -X POST $BASE/drone/takeoff -H "Content-Type: application/json" -d '{"altitude":5}'
    curl $BASE/mode/MANUAL

## Compatibility report

Frontend files and IDs were preserved. Existing routes and /data telemetry fields remain available. Structured JSON was added for control responses. SQLite logs and mission routes were added. Duplicate drone routes, hard-coded serial connections, unsafe clamping, and single-frame autonomous pump activation were removed.

## Hardware vs simulation

| Feature | Simulation | Hardware |
|---|---|---|
| Robot drive/pump | State-only | GPIO or Pixhawk integration required |
| NPK arm | Background bounded worker | Configure driver GPIO and endstops |
| Sensors/GPS | Marked fallback values | Add verified drivers/calibration |
| Cameras | Clean unavailable response | Configure robot-only sources |
| Drone | Safe simulated telemetry | Add configured MAVLink service |
| AI/soil | Model/classifier dependent | Install optional ML packages/models |
| Mission/logging | Background mission + SQLite | Connect worker to Pixhawk |

## Known limitations

This implementation provides the safe simulation contract and service boundaries. Live Pixhawk MAVLink, RC arbitration/telemetry, verified NPK Modbus decoding, physical sensor polling, camera workers, and confirmed multi-frame disease stop-and-treat orchestration require robot wiring and verified protocols/configuration. No unsafe hardware assumptions are made.

