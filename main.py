from fastapi import FastAPI
import asyncio
from messages import run_bot

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Twitch Chat Bot corriendo con FastAPI 🚀"}

# Iniciar el bot en segundo plano
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())
