import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"Global exception: {exc}")
    return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/test")
def test():
    try:
        print("Test endpoint called!")
        return {"message": "Hello World"}
    except Exception as e:
        print(f"Exception in test endpoint: {e}")
        raise


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8084)
