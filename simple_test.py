from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Lifespan starting")
    yield
    print("Lifespan shutting down")

app = FastAPI(lifespan=lifespan)

@app.get("/test")
def test():
    return {"ok": True}