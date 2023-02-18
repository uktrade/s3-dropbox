import os
import secrets
from datetime import datetime
from uuid import uuid4

import boto3
from fastapi import FastAPI, Request, status
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

app = FastAPI()


try:
    token = os.environ['TOKEN']
except KeyError:
    raise KeyError('The TOKEN environment variable must be set to the Bearer token that will be used to authenticate requests')


try:
    bucket = os.environ['BUCKET']
except KeyError:
    raise KeyError('The BUCKET environment variable must be set with the name of the bucket to upload to')


try:
    region_name = os.environ['AWS_REGION']
except KeyError:
    raise KeyError('The AWS_REGION environment variable must be set with the region of the bucket to upload to')

try:
    endpoint_url = os.environ['S3_ENDPOINT_URL']
except KeyError:
    s3_client = boto3.client('s3', region_name=region_name)
else:
    s3_client = boto3.client('s3', region_name=region_name, endpoint_url=endpoint_url)


@app.post("/v1/drop")
async def drop(request: Request) -> Response:
    try:
        auth = request.headers['authorization']
    except KeyError:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED, content='The authorization header must be present')

    if not auth.startswith('Bearer '):
        return Response(status_code=status.HTTP_401_UNAUTHORIZED, content='The authorization header must start with "Bearer "')

    passed_token = auth.partition(' ')[2].strip()
    if not secrets.compare_digest(passed_token, token):
        return Response(status_code=status.HTTP_401_UNAUTHORIZED, content='The Bearer token is not correct')

    try:
        length = int(request.headers['content-length'])
    except KeyError:
        return Response(status_code=status.HTTP_411_LENGTH_REQUIRED, content=b'The content-length header must be present')

    if length > 10240:
        return Response(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, content=b'The request body must be less 10240 bytes')

    body = await request.body()
    key = f'{datetime.now().isoformat()}-{uuid4()}'

    def upload():
        s3_client.put_object(Bucket=bucket, Key=key, Body=body)
    await run_in_threadpool(upload)

    return Response(status_code=status.HTTP_201_CREATED, content=b'')
