from fastapi import FastAPI, HTTPException, Request
from typing import Optional
from schemas import ConfigureClientData, ConfigureAccessPointData, SimulateScenarioData
from utils.generate_configure_scripts import generate_client_script, generate_ap_script, generate_scripts_for_run_simulation
from utils.run_subprocess import run_subprocess, is_client_config_active, is_ap_config_active, run_simulation_processes
import uvicorn
from contextlib import asynccontextmanager
import asyncio
import time


app = FastAPI()

@app.on_event("startup")
async def startup_event():
    # initial global variable
    app.simulate_task: asyncio.Task = None
    app.simulate_status = ""
    app.writing_configure_lock = asyncio.Lock()
    # Clean up the ML models and release the resources

def testing(request: Request):
    request.app.simulate_status = "WOW!!, It actually work"
@app.get("/")
def index(request: Request):
    # testing(request)
    return {"message": f"{app.simulate_status}"}

@app.post("/configure/client")
async def configure_client(request_body: ConfigureClientData):
    # ตรวจสอบว่ามีกำลังรัน simulate_task อยู่หรือไม่
    if app.simulate_task is not None:
        raise HTTPException(400, "simulate_task is running")
    
    # ตรวจสอบว่า ConfigureClientData ที่ได้มากำลังใช้งานอยู่หรือป่าว ถ้าใช้งานอยู่แล้วให้ตอบกลับไปเลยว่าพร้อมใช้งาน
    if await is_client_config_active(request_body):
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
    while cnt < 10:
        if await is_client_config_active(request_body):
            return {"message": "wifi is connected"}
        await asyncio.sleep(1)
        cnt += 1
    raise HTTPException(400, "Take too much time to connect wifi")


@app.post("/configure/ap")
async def configure_ap(request_body: ConfigureAccessPointData):
    # ตรวจสอบว่ามีกำลังรัน simulate_task อยู่หรือไม่
    if app.simulate_task is not None:
        raise HTTPException(400, "simulate_task is running")
    
    # ตรวจสอบว่า ConfigureClientData ที่ได้มากำลังใช้งานอยู่หรือป่าว ถ้าใช้งานอยู่แล้วให้ตอบกลับไปเลยว่าพร้อมใช้งาน
    if await is_ap_config_active(request_body):
        return {"message": "wifi is connected"}
    
    # หากไม่จะต้องแก้ configuration
    # acquire the lock
    async with app.writing_configure_lock:
    # critical section
        # reset the configuration
        await run_subprocess("cp ./default_config/wireless /etc/config/wireless")
        # configure the new configuration
        await run_subprocess(generate_ap_script(request_body))
    # lock is released automatically...
    
    # wait for TX packet be reset (take around 10 sec)
    await asyncio.sleep(10)
    # polling check if wifi is connected with timeout 150 sec
    cnt = 0
    while cnt < 30:
        if await is_ap_config_active(request_body):
            return {"message": "wifi is connected"}
        await asyncio.sleep(5)
        cnt += 1
    raise HTTPException(400, "Take too much time to enable wifi (AP is not sending ssid broadcast)")

@app.post("/simulation/run")
async def schedule_run_simulation_task(request_body: SimulateScenarioData, request: Request):
    # NOTE: this is not safe when many request was send to modify app.simulate_task while other is running
    #       to solve this problem (assuming no only run 1 scenario at the time)
    #           1. modify this code for checking before create any task (no need to lock because all of the operation are all synchonus)
    #           2. client(caller) must make sure before send the request
    #       (if you want to run multiple(make sure for same configure) then modify app.simulate_task to be the list)
    scripts = generate_scripts_for_run_simulation(request_body)
    if app.simulate_task is not None:
        raise HTTPException(400, "other simulate_task is running")
    app.simulate_status = ""
    app.simulate_task = asyncio.create_task(run_simulation_processes(scripts, request))
    return {"message": f"simulation task has been scheduled"}


@app.post("/simulation/cancel")
async def schedule_run_cancel_task(request_body: SimulateScenarioData, request: Request):
    # NOTE: this is not safe when many request was send to modify app.simulate_task while other is running
    #       to solve this problem (assuming no only run 1 scenario at the time)
    #           1. modify this code for checking before create any task (no need to lock because all of the operation are all synchonus)
    #           2. client(caller) must make sure before send the request
    #       (if you want to run multiple(make sure for same configure) then modify app.simulate_task to be the list)
    start = time.time()
    if app.simulate_task is None:
        raise HTTPException(400, "there is no simulate_task running")
    app.simulate_task.cancel()
    try:
        await app.simulate_task
    except asyncio.CancelledError:
        print(f"cancelled {time.time()-start}")
        app.simulate_task = None
    return {"message": f"simulation task has been cancelled"}

@app.post("/configure/client/get_configure_script")
def get_client_configure_script(request_body: ConfigureClientData):
    print(request_body)
    return generate_client_script(request_body)

@app.post("/configure/ap/get_configure_script")
def get_ap_configure_script(request_body: ConfigureAccessPointData):
    print(request_body)
    return generate_ap_script(request_body)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)