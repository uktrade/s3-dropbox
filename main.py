from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

app = FastAPI()


@app.get("/v1/drop")
async def root():
    return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "Hello World"})
