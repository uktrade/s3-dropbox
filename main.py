from fastapi import FastAPI, status
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

app = FastAPI()


@app.post("/v1/drop")
async def drop() -> Response:

    def upload():
        pass
    await run_in_threadpool(upload)

    return Response(status_code=status.HTTP_201_CREATED, content=b'')
