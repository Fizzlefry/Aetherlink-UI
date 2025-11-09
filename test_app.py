from fastapi import FastAPI

app = FastAPI()

@app.get("/test")
def test():
    return {"message": "Hello World"}

@app.get("/federation/predict")
def federation_predict():
    return {"risk": 0.1, "peers": {"fresh": [], "at_risk": [], "stale": []}}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8011)