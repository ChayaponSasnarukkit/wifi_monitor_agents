from fastapi import FastAPI, HTTPException
from typing import Optional
from schemas import ConfigureClientData, ConfigureAccessPointData
from utils.generate_configure_scripts import generate_client_script, generate_ap_script
from utils.run_subprocess import run_subprocess, is_client_config_active, is_ap_config_active
import uvicorn
from contextlib import asynccontextmanager
import asyncio


app = FastAPI()

@app.on_event("startup")
async def startup_event():
    # initial global variable
    app.simulate_process = None
    app.simulate_status = ""
    app.writing_configure_lock = asyncio.Lock()
    # Clean up the ML models and release the resources

@app.get("/")
def index():
    return {"message": "hello world"}

@app.post("/configure/client")
async def configure_client(request_body: ConfigureClientData):
    # ตรวจสอบว่ามีกำลังรัน simulate_process อยู่หรือไม่
    if app.simulate_process is not None:
        raise HTTPException(400, "simulate_process is running")
    
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
    # ตรวจสอบว่ามีกำลังรัน simulate_process อยู่หรือไม่
    if app.simulate_process is not None:
        raise HTTPException(400, "simulate_process is running")
    
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
    
    # polling check if wifi is connected with timeout 10 sec
    cnt = 0
    while cnt < 30:
        if await is_ap_config_active(request_body):
            return {"message": "wifi is connected"}
        await asyncio.sleep(5)
        cnt += 1
    raise HTTPException(400, "Take too much time to enable wifi (AP is not sending ssid broadcast)")

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