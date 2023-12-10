from fastapi import FastAPI
from typing import Optional
from schemas import OperationModeEnum, RadioEnum, ConfigureData
import uvicorn
import asyncio

app = FastAPI()

# initial global state
app.simulate_process = None
app.simulate_status = ""

@app.get("/")
def index():
    return {"message": "hello world"}

@app.post("/configure")
def configure(request_body: ConfigureData):
    print(request_body)
    return request_body

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)