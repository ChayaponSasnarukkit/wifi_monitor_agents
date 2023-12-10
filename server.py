from fastapi import FastAPI
from typing import Optional
import uvicorn
import asyncio

app = FastAPI()

@app.get("/")
def index():
    return {"message": "hello world"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)