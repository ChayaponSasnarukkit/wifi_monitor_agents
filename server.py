from fastapi import FastAPI, HTTPException, Request
from typing import Optional
from schemas import ConfigureClientData, ConfigureAccessPointData, SimulateScenarioData, RadioEnum
from utils.generate_configure_scripts import generate_client_script, generate_ap_script
from utils.run_subprocess import run_subprocess, is_client_config_active, is_ap_config_active, run_simulation_processes, polling_ap_state
import uvicorn
from contextlib import asynccontextmanager
import asyncio
import time, socket, subprocess, select, threading


app = FastAPI()

web_simulation_process = None
file_simulation_process = None

def blocking_udp_read(event):
    cnt = 0
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    control_ip = subprocess.run(["uci", "get", "network.lan.ipaddr"], capture_output=True, text=True).stdout
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.bind(("", 8808))
    udp_socket.setblocking(0)
    while True:
        # thread will be block until data available 
        readable, _, _ = select.select([udp_socket], [], [], 5)
        if readable:
            data, addr = udp_socket.recvfrom(1024)
            time_stamp = float(data.decode())
            print(time.time()-time_stamp)
            # if cnt%3 == 0:
            time.clock_settime_ns(time.CLOCK_REALTIME, int(time_stamp*10**9))
            #     cnt = 0
            # cnt += 1
        if event.is_set():
            return
    
@app.on_event("startup")
async def startup_event():
    # initial global variable
    app.my_event = threading.Event()
    loop = asyncio.get_running_loop()
    app.udp_socket_thread = loop.run_in_executor(None, blocking_udp_read, app.my_event)
    
    global web_simulation_process; global file_simulation_process
    web_simulation_process = await asyncio.create_subprocess_shell("python -u ./simulation/server/web_application.py")
    file_simulation_process = await asyncio.create_subprocess_shell("python -u ./simulation/server/file_transfer.py")
    app.ap_state = "not_ready_to_use"
    app.simulate_task: asyncio.Task = None
    app.simulate_status = ""
    app.read_ptr = 0
    app.writing_configure_lock = asyncio.Lock()
    app.active_radio = None
    app.monitor_data = {"Tx-Power": [], "Signal": [], "Noise": [], "BitRate": []}
    
@app.on_event("shutdown")
async def shutdown_event():
    app.my_event.set()
    web_simulation_process.terminate()
    file_simulation_process.terminate()

def testing(request: Request):
    request.app.simulate_status = "WOW!!, It actually work"
@app.get("/")
def index(request: Request):
    # testing(request)
    return {"message": f"{app.simulate_status}"}

@app.post("/sync_clock/{time_stamp}")
async def sync_clock(time_stamp):
    print(time_stamp, time.time())
    time.clock_settime_ns(time.CLOCK_REALTIME, int(float(time_stamp)*10**9))

@app.post("/configure/client")
async def configure_client(request_body: ConfigureClientData):
    # ตรวจสอบว่ามีกำลังรัน simulate_task อยู่หรือไม่
    if app.simulate_task is not None:
        raise HTTPException(400, "simulate_task is running")
    
    # ตรวจสอบว่า ConfigureClientData ที่ได้มากำลังใช้งานอยู่หรือป่าว ถ้าใช้งานอยู่แล้วให้ตอบกลับไปเลยว่าพร้อมใช้งาน
    if await is_client_config_active(request_body):
        app.active_radio = request_body.radio
        return {"message": "wifi is connected"}
    
    # หากไม่จะต้องแก้ configuration
    # acquire the lock
    async with app.writing_configure_lock:
    # critical section
        # reset the configuration
        await run_subprocess("cp ./default_config/wireless /etc/config/wireless")
        # configure the new configuration
        await run_subprocess(generate_client_script(request_body))
    # lock is released automatically...
    
    # polling check if wifi is connected with timeout 10 sec
    cnt = 0
    while cnt < 20:
        if await is_client_config_active(request_body):
            app.active_radio = request_body.radio
            return {"message": "wifi is connected"}
        await asyncio.sleep(1)
        cnt += 1
    print("raise Take too much time to connect wifi")
    raise HTTPException(400, "Take too much time to connect wifi")


@app.post("/configure/ap")
async def configure_ap(request: Request, request_body: ConfigureAccessPointData):
    # ตรวจสอบว่ามีกำลังรัน simulate_task อยู่หรือไม่
    if app.simulate_task is not None:
        raise HTTPException(400, "simulate_task is running")
    
    # ตรวจสอบว่า ConfigureClientData ที่ได้มากำลังใช้งานอยู่หรือป่าว ถ้าใช้งานอยู่แล้วให้ตอบกลับไปเลยว่าพร้อมใช้งาน
    if await is_ap_config_active(request_body):
        app.active_radio = request_body.radio
        app.ap_state = "ready_to_use"
        return {"message": "wifi is connected"}
    
    # หากไม่จะต้องแก้ configuration
    # acquire the lock
    async with app.writing_configure_lock:
    # critical section
        # reset the configuration
        await run_subprocess("cp ./default_config/wireless /etc/config/wireless")
        # configure the new configuration
        await run_subprocess(generate_ap_script(request_body))
        app.ap_state = "not_ready_to_use [in process of apply config]"
    # lock is released automatically...
    
    asyncio.create_task(polling_ap_state(request, request_body))
    return {"message": f"configured, wait for configuration to be apply"}

@app.get("/configure/ap/state")
async def get_ap_status(ssid: str, radio: RadioEnum, tx_power: int):
    params = ConfigureAccessPointData(radio=radio, ssid=ssid, tx_power=tx_power)
    if await is_ap_config_active(params):
        app.active_radio = radio
        return "ready_to_use"
    else:
        return "not_ready_to_use"

@app.post("/simulation/run")
async def schedule_run_simulation_task(request_body: SimulateScenarioData, request: Request):
    # NOTE: this is not safe when many request was send to modify app.simulate_task while other is running
    #       to solve this problem (assuming no only run 1 scenario at the time)
    #           1. modify this code for checking before create any task (no need to lock because all of the operation are all synchonus)
    #           2. client(caller) must make sure before send the request
    #       (if you want to run multiple(make sure for same configure) then modify app.simulate_task to be the list)
    request_body = request_body.my_validator()
    if app.active_radio is None:
        raise HTTPException(400, "Please configure the wifi before start simulation")
    if app.simulate_task is not None:
        raise HTTPException(400, "other simulate_task is running")
    # reset old state data from old simulation
    app.simulate_status = ""
    app.read_ptr = 0
    app.monitor_data = {"Tx-Power": [], "Signal": [], "Noise": [], "BitRate": []}
    # schedule the new task
    app.simulate_task = asyncio.create_task(run_simulation_processes(request_body, request))
    return {"message": f"simulation task has been scheduled"}


@app.post("/simulation/cancel")
async def schedule_run_cancel_task(request: Request):
    # NOTE: this is not safe when many request was send to modify app.simulate_task while other is running
    #       to solve this problem (assuming no only run 1 scenario at the time)
    #           1. modify this code for checking before create any task (no need to lock because all of the operation are all synchonus)
    #           2. client(caller) must make sure before send the request
    #       (if you want to run multiple(make sure for same configure) then modify app.simulate_task to be the list)
    start = time.time()
    if app.simulate_task is None:
        return {"message": "there is no simulate_task running"}
    app.simulate_task.cancel()
    try:
        await app.simulate_task
    except asyncio.CancelledError:
        print(f"cancelled {time.time()-start}")
    return {"message": f"simulation task has been cancelled"}

@app.get("/simulation/state")
def get_simulation_status():
    data = {
        "state": "finish" if app.simulate_task is None else "running",
        "new_state_message": app.simulate_status[app.read_ptr:] if len(app.simulate_status)-1 >= app.read_ptr else ""
    }
    app.read_ptr = len(app.simulate_status)
    return data

@app.get("/simulation/monitor")
def get_simulation_monitor_data():
    return app.monitor_data

@app.get("/configure/client/get_configure_script")
def get_client_configure_script(request_body: ConfigureClientData):
    print(request_body)
    return generate_client_script(request_body)

@app.post("/configure/ap/get_configure_script")
def get_ap_configure_script(request_body: ConfigureAccessPointData):
    print(request_body)
    return generate_ap_script(request_body)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)