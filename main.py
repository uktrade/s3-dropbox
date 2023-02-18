from fastapi import FastAPI, Request, status
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

app = FastAPI()


@app.post("/v1/drop")
async def drop(request: Request) -> Response:
    try:
        length = int(request.headers['content-length'])
    except KeyError:
        return Response(status_code=status.HTTP_411_LENGTH_REQUIRED, content=b'The content-length header must be present')

    if length > 10240:
        return Response(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, content=b'The request body must be less 10240 bytes')

    def upload():
        pass
    await run_in_threadpool(upload)

    return Response(status_code=status.HTTP_201_CREATED, content=b'')
