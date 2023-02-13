from fastapi import FastAPI

app = FastAPI()


@app.get("/v1/drop")
async def root():
    return {"message": "Hello World"}
