
from __future__ import annotations
import json, logging, os, sqlite3, threading, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
import numpy as np
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
try:
    import cv2
except ImportError: cv2 = None
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError: pass
try: from soil_classifier import SoilClassifier
except Exception: SoilClassifier = None
try: from ultralytics import YOLO
except ImportError: YOLO = None
try: import RPi.GPIO as GPIO
except ImportError: GPIO = None

BASE_DIR=Path(__file__).resolve().parent
SIMULATION=os.getenv("SIMULATION_MODE","true").lower() in {"1","true","yes","on"} or GPIO is None
DB_PATH=Path(os.getenv("DATABASE_PATH",str(BASE_DIR/"agrivaidya.sqlite3")))
app=Flask(__name__); CORS(app)
logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"),format="%(asctime)s %(levelname)s %(message)s")
log=logging.getLogger("agrivaidya")
MODES={"MANUAL","AUTO","MAINTENANCE","EMERGENCY_STOP"}; DRONE_MODES={"GUIDED","LOITER","ALT_HOLD","STABILIZE","RTL","LAND"}
lock=threading.RLock(); estop=threading.Event()
MODE="MANUAL"; pump_state=False; robot_command="stop"; latest_disease="None"
PINS={"left_in1":17,"left_in2":18,"right_in1":27,"right_in2":22,"pump":int(os.getenv("PUMP_GPIO","24"))}
SERVO_MIN=float(os.getenv("CAMERA_SERVO_MIN","0")); SERVO_MAX=float(os.getenv("CAMERA_SERVO_MAX","180"))
ARM_MAX_STEPS=int(os.getenv("NPK_ARM_MAX_STEPS","5000")); ARM_MAX_SPEED=int(os.getenv("NPK_ARM_MAX_SPEED","2000"))
FALLBACK={"battery":12.6,"solar_voltage":None,"tank":50.0,"temp":25.0,"humidity":60.0,"motor_temp":{"motor_1":22.5,"motor_2":22.7,"motor_3":22.6,"motor_4":22.8},"gps":{"lat":20.5937,"lon":78.9629},"npk":{"N":40,"P":30,"K":35,"nitrogen":40,"phosphorus":30,"potassium":35,"ph":6.5,"ec":1.2,"moisture":45,"soil_temperature":23.0}}
sensor_data=json.loads(json.dumps(FALLBACK))
sensor_sources={"motor_temperature":"simulation","npk":"simulation","gps":"simulation","tank":"simulation","battery":"simulation","solar":"unavailable","am2120":"simulation"}
connections={"backend":"connected","pixhawk":"simulation","gps":"simulation","rc_receiver":"simulation","npk_sensor":"simulation","ds18b20":"simulation","am2120":"simulation","ultrasonic":"simulation","camera_top":"unavailable","camera_bottom":"unavailable","camera_drone":"unavailable","pump_controller":"simulation","npk_arm":"simulation","ai_model":"unavailable","soil_classifier":"unavailable"}
arm_lock=threading.RLock(); arm_cancel=threading.Event(); arm={"moving":False,"direction":None,"steps_remaining":0,"position":0,"simulation":SIMULATION}
mission_lock=threading.RLock(); mission_cancel=threading.Event(); mission={"running":False,"paused":False,"stopped":True,"mission_name":None,"progress":0,"current_gps":FALLBACK["gps"].copy(),"start_time":None}

def iso(): return datetime.now(timezone.utc).isoformat()
def db_init():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(DB_PATH) as db: db.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY,timestamp TEXT,event_type TEXT,message TEXT,severity TEXT,mode TEXT,latitude REAL,longitude REAL)")
def event(kind,message,severity="info"):
    try:
        g=sensor_data["gps"]
        with sqlite3.connect(DB_PATH) as db: db.execute("INSERT INTO logs VALUES(NULL,?,?,?,?,?,?,?)",(iso(),kind,message,severity,MODE,g.get("lat"),g.get("lon")))
    except Exception: log.exception("log persistence failed")
def ok(data=None,message="Operation completed",status=200): return jsonify({"success":True,"data":data or {},"message":message}),status
def fail(message,code="ERROR",status=400): return jsonify({"success":False,"error":message,"code":code}),status
def gpio(pins,values):
    if GPIO:
        try: GPIO.output(pins,values)
        except Exception: log.exception("GPIO error")
def stop_drive():
    global robot_command
    gpio([PINS["left_in1"],PINS["left_in2"],PINS["right_in1"],PINS["right_in2"]],0)
    with lock: robot_command="stop"
def drive(command):
    global robot_command
    with lock:
        if estop.is_set(): return False,"Emergency stop is active"
        if MODE not in MODES-{"EMERGENCY_STOP"}: return False,"Robot commands are disabled in the current mode"
        robot_command=command
    if command=="stop": stop_drive()
    elif command=="forward": gpio([PINS["left_in1"],PINS["right_in1"]],[1,1])
    elif command=="backward": gpio([PINS["left_in2"],PINS["right_in2"]],[1,1])
    elif command=="left": gpio(PINS["left_in2"],1); gpio(PINS["right_in1"],1)
    elif command=="right": gpio(PINS["left_in1"],1); gpio(PINS["right_in2"],1)
    event("robot_command",command); return True,None
def pump(enabled):
    global pump_state
    with lock:
        if enabled and estop.is_set(): return False,"Emergency stop is active"
        pump_state=bool(enabled)
    gpio(PINS["pump"],int(enabled)); event("pump_command","on" if enabled else "off"); return True,None
def stop_arm():
    arm_cancel.set()
    with arm_lock: arm.update(moving=False,direction=None,steps_remaining=0)
def activate_estop():
    global MODE
    with lock: MODE="EMERGENCY_STOP"; estop.set()
    stop_drive(); pump(False); stop_arm(); mission_cancel.set(); event("emergency_stop","Emergency stop activated","critical")
def clear_estop(mode):
    global MODE
    with lock: estop.clear(); MODE=mode
    event("emergency_stop_clear",f"mode={mode}")
def move_arm(direction,steps,speed):
    if estop.is_set(): raise ValueError("Emergency stop is active")
    if direction not in (-1,1): raise ValueError("direction must be -1 or 1")
    if isinstance(steps,bool) or not isinstance(steps,(int,float)) or int(steps)!=steps or not 1<=int(steps)<=ARM_MAX_STEPS: raise ValueError(f"steps must be an integer from 1 to {ARM_MAX_STEPS}")
    if isinstance(speed,bool) or not isinstance(speed,(int,float)) or int(speed)!=speed or not 1<=int(speed)<=ARM_MAX_SPEED: raise ValueError(f"speed must be an integer from 1 to {ARM_MAX_SPEED}")
    with arm_lock:
        if arm["moving"]: return False
        arm_cancel.clear(); arm.update(moving=True,direction=direction,steps_remaining=int(steps))
    def work():
        for _ in range(int(steps)):
            if arm_cancel.is_set() or estop.is_set(): break
            time.sleep(1/max(1,int(speed)))
            with arm_lock: arm["position"]+=direction; arm["steps_remaining"]-=1
        with arm_lock: arm.update(moving=False,direction=None,steps_remaining=0)
    threading.Thread(target=work,daemon=True,name="npk-arm").start(); event("npk_arm_command",f"direction={direction},steps={steps},speed={speed}"); return True
def arm_status():
    with arm_lock: return dict(arm)
def decode(file):
    if not file or not file.filename or cv2 is None: return None
    raw=file.read(); return cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR) if raw else None
def sensor_worker():
    while True: time.sleep(2)
def mission_worker():
    while not mission_cancel.is_set():
        with mission_lock:
            if mission["running"] and not mission["paused"]:
                mission["progress"]=min(100,mission["progress"]+1); mission["current_gps"]=sensor_data["gps"].copy()
                if mission["progress"]>=100: mission.update(running=False,stopped=True)
        time.sleep(1)
def model_load():
    path=Path(os.getenv("DISEASE_MODEL_PATH",str(BASE_DIR/"best.pt")))
    if not YOLO or not path.exists(): return None
    try: return YOLO(str(path))
    except Exception: log.exception("disease model unavailable"); return None
disease_model=model_load(); connections["ai_model"]="connected" if disease_model else ("simulation" if SIMULATION else "unavailable")
soil_classifier=None
if SoilClassifier:
    try: soil_classifier=SoilClassifier()
    except Exception: log.exception("soil classifier unavailable")
connections["soil_classifier"]="connected" if soil_classifier else ("simulation" if SIMULATION else "unavailable")
db_init()

@app.route("/")
def index(): return send_from_directory(BASE_DIR,"index.html")
@app.route("/logo.jpeg")
def logo(): return send_from_directory(BASE_DIR,"logo.jpeg")
@app.route("/css/<path:name>")
def css(name): return send_from_directory(BASE_DIR/"css",name)
@app.route("/js/<path:name>")
def js(name): return send_from_directory(BASE_DIR/"js",name)
@app.route("/data/<path:name>")
def asset(name): return send_from_directory(BASE_DIR/"data",name)
@app.route("/health")
def health(): return jsonify({"status":"connected","overall":"emergency_stop" if estop.is_set() else "ok","connections":connections,"simulation":SIMULATION})
@app.route("/data")
def data():
    with lock: mode,pump_now=MODE,pump_state
    motors=sensor_data["motor_temp"]
    return jsonify({"mode":mode,"battery":sensor_data["battery"],"solar_voltage":sensor_data["solar_voltage"],"tank":sensor_data["tank"],"temp":sensor_data["temp"],"humidity":sensor_data["humidity"],"motor_temp":motors["motor_1"],"motor_temperatures":motors,"gps":sensor_data["gps"],"npk":sensor_data["npk"],"npk_arm":arm_status(),"sensor_sources":sensor_sources,"disease":latest_disease,"pump":pump_now,"connections":connections})
weather_cache={"key":None,"expires":0,"data":None}
@app.route("/weather")
def weather():
    g=sensor_data["gps"]; key=(round(g["lat"],4),round(g["lon"],4))
    if weather_cache["key"]==key and weather_cache["expires"]>time.time(): return jsonify(weather_cache["data"])
    try:
        q=urlencode({"latitude":key[0],"longitude":key[1],"current":"temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m","timezone":"auto"})
        with urlopen("https://api.open-meteo.com/v1/forecast?"+q,timeout=5) as r: raw=json.load(r)
        c=raw.get("current",{}); result={"available":True,"timezone":raw.get("timezone"),"time":c.get("time"),"temperature":c.get("temperature_2m"),"apparent_temperature":c.get("apparent_temperature"),"humidity":c.get("relative_humidity_2m"),"wind_speed":c.get("wind_speed_10m"),"weather_code":c.get("weather_code")}; weather_cache.update(key=key,expires=time.time()+600,data=result); return jsonify(result)
    except Exception: log.exception("weather unavailable"); return jsonify({"available":False,"error":"Weather service unavailable"}),503

def robot_route(c):
    success,msg=drive(c)
    return ok({"simulation":SIMULATION,"command":c},f"{'Simulated ' if SIMULATION else ''}robot {c} command") if success else fail(msg,"EMERGENCY_STOP" if estop.is_set() else "CONTROL_REJECTED",409)
for c in ("forward","backward","left","right","stop"): app.add_url_rule("/robot/"+c,"robot_"+c,lambda c=c:robot_route(c))
@app.route("/spray/on")
def spray_on():
    s,m=pump(True); return ok({"simulation":SIMULATION,"pump":True},"Pump on") if s else fail(m,"EMERGENCY_STOP",409)
@app.route("/spray/off")
def spray_off(): pump(False); return ok({"simulation":SIMULATION,"pump":False},"Pump off")
@app.route("/mode/<name>")
def mode(name):
    global MODE
    name=name.upper()
    if name not in MODES: return fail("Invalid operating mode","INVALID_MODE",400)
    if name=="EMERGENCY_STOP": activate_estop()
    elif estop.is_set(): clear_estop(name)
    else:
        with lock: MODE=name
        event("mode_change",name)
    return ok({"mode":MODE,"emergency_stop":estop.is_set()},f"Mode set to {MODE}")
@app.route("/api/npk-arm/status")
def npk_status(): return jsonify(arm_status())
@app.route("/api/npk-arm/move",methods=["POST"])
def npk_move():
    p=request.get_json(silent=True) or {}
    if any(k not in p for k in ("steps","speed","direction")): return fail("steps, speed, and direction are required","INVALID_ARM_REQUEST",400)
    try: started=move_arm(p["direction"],p["steps"],p["speed"])
    except ValueError as e: return fail(str(e),"INVALID_ARM_REQUEST",422)
    return fail("NPK arm is already moving","ARM_BUSY",409) if not started else ok(arm_status(),"NPK arm movement queued",202)
@app.route("/api/npk-arm/stop",methods=["POST"])
def npk_stop(): stop_arm(); return ok(arm_status(),"NPK arm stopped")
@app.route("/camera/top")
@app.route("/camera/bottom")
@app.route("/camera/drone")
def camera(): return fail("Configured robot camera source is unavailable","CAMERA_UNAVAILABLE",503)
@app.route("/camera/top/servo")
def servo():
    try: angle=float(request.args["angle"])
    except (KeyError,TypeError,ValueError): return fail("angle must be numeric","INVALID_ANGLE",400)
    if not SERVO_MIN<=angle<=SERVO_MAX: return fail("angle is outside configured safety limits","INVALID_ANGLE",422)
    return ok({"angle":angle,"simulation":SIMULATION},"Camera servo moved")
def drone(): return {"connected":SIMULATION,"simulation":SIMULATION,"armed":False,"mode":"STABILIZE","altitude":0,"battery_remaining":100,"latitude":sensor_data["gps"]["lat"],"longitude":sensor_data["gps"]["lon"]}
@app.route("/drone/status")
def drone_status(): return jsonify(drone())
@app.route("/drone/telemetry")
def telemetry(): return jsonify(drone())
@app.route("/drone/arm",methods=["POST"])
def drone_arm(): return fail("Emergency stop is active","EMERGENCY_STOP",409) if estop.is_set() else ok({**drone(),"armed":True},"Drone armed (simulation)")
@app.route("/drone/disarm",methods=["POST"])
def drone_disarm(): return ok(drone(),"Drone disarmed")
@app.route("/drone/takeoff",methods=["POST"])
def takeoff():
    if estop.is_set(): return fail("Emergency stop is active","EMERGENCY_STOP",409)
    a=(request.get_json(silent=True) or {}).get("altitude",10); limit=float(os.getenv("DRONE_MAX_ALTITUDE","30"))
    if isinstance(a,bool) or not isinstance(a,(int,float)) or not 0<float(a)<=limit: return fail("altitude is outside configured safety limits","INVALID_ALTITUDE",422)
    return ok({"altitude":float(a),"simulation":SIMULATION},"Drone takeoff accepted")
@app.route("/drone/land",methods=["POST"])
def land(): return ok({"simulation":SIMULATION},"Drone landing accepted")
@app.route("/drone/mode/<name>",methods=["POST"])
def drone_mode(name):
    name=name.upper()
    if name not in DRONE_MODES: return fail("Invalid drone mode","INVALID_DRONE_MODE",400)
    if estop.is_set() and name not in {"LAND","RTL"}: return fail("Emergency stop is active","EMERGENCY_STOP",409)
    return ok({"mode":name,"simulation":SIMULATION},"Drone mode accepted")
@app.route("/disease/predict",methods=["POST"])
def disease():
    image=decode(request.files.get("image"))
    if image is None: return fail("A valid image upload is required","INVALID_IMAGE",400)
    if disease_model is None: return fail("Disease model is unavailable","MODEL_UNAVAILABLE",503)
    try:
        r=disease_model.predict(source=image,verbose=False)[0]; i=int(r.probs.top1); conf=float(r.probs.top1conf); names=getattr(r,"names",{}); label=names.get(i,str(i)); return jsonify({"disease":label,"confidence":round(conf*100,1),"severity":"high" if conf>=.8 else "moderate","recommendation":"Follow local agricultural guidance and the product label."})
    except Exception: log.exception("disease prediction failed"); return fail("Disease prediction failed","PREDICTION_FAILED",500)
@app.route("/soil/predict",methods=["POST"])
def soil():
    image=decode(request.files.get("image"))
    if image is None: return fail("A valid image upload is required","INVALID_IMAGE",400)
    if soil_classifier is None: return fail("Soil classifier is unavailable","CLASSIFIER_UNAVAILABLE",503)
    try: return jsonify(soil_classifier.predict(image))
    except Exception: log.exception("soil prediction failed"); return fail("Soil prediction failed","PREDICTION_FAILED",500)
@app.route("/logs")
def logs():
    with sqlite3.connect(DB_PATH) as db: rows=db.execute("SELECT timestamp,event_type,message,severity,mode,latitude,longitude FROM logs ORDER BY id DESC LIMIT 500").fetchall()
    keys=("timestamp","event_type","message","severity","mode","latitude","longitude"); return jsonify({"logs":[dict(zip(keys,r)) for r in rows]})
@app.route("/mission/start",methods=["POST"])
def mission_start():
    if estop.is_set(): return fail("Emergency stop is active","EMERGENCY_STOP",409)
    p=request.get_json(silent=True) or {}
    with mission_lock: mission.update(running=True,paused=False,stopped=False,mission_name=p.get("mission_name","Field mission"),progress=0,start_time=iso()); mission_cancel.clear()
    event("mission_start",mission["mission_name"]); return ok(mission.copy(),"Mission started",202)
@app.route("/mission/pause",methods=["POST"])
def mission_pause():
    with mission_lock: mission["paused"]=True
    event("mission_pause","Mission paused"); return ok(mission.copy(),"Mission paused")
@app.route("/mission/stop",methods=["POST"])
def mission_stop_route():
    with mission_lock: mission.update(running=False,paused=False,stopped=True)
    mission_cancel.set(); stop_drive(); pump(False); event("mission_stop","Mission stopped"); return ok(mission.copy(),"Mission stopped")
@app.route("/mission/status")
def mission_status():
    with mission_lock: return jsonify(mission.copy())
@app.errorhandler(Exception)
def unhandled(exc): log.exception("unhandled API error"); return fail("Internal server error","INTERNAL_ERROR",500)
if __name__=="__main__":
    threading.Thread(target=sensor_worker,daemon=True).start(); threading.Thread(target=mission_worker,daemon=True).start(); app.run(host=os.getenv("FLASK_HOST","0.0.0.0"),port=int(os.getenv("FLASK_PORT","5000")),debug=False)
