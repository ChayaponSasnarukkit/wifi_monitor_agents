from fastapi import FastAPI
from typing import Optional
from schemas import ConfigureClientData, ConfigureAccessPointData
from utils.generate_configure_scripts import generate_client_script, generate_ap_script
import uvicorn
import asyncio

app = FastAPI()

# initial global state
app.simulate_process = None
app.simulate_status = ""

@app.get("/")
def index():
    return {"message": "hello world"}

@app.post("/configure/client")
def configure(request_body: ConfigureClientData):
    print(request_body)
    return generate_client_script(request_body)

@app.post("/configure/ap")
def configure(request_body: ConfigureAccessPointData):
    print(request_body)
    return generate_ap_script(request_body)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)