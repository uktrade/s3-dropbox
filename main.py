import os
import secrets
from datetime import datetime
from functools import lru_cache
from typing import Optional
from uuid import uuid4

import boto3
from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import Response
from pydantic import BaseSettings, SecretStr
from starlette.concurrency import run_in_threadpool


class Settings(BaseSettings):
    token: SecretStr
    bucket: str
    aws_region: str
    s3_endpoint_url: Optional[str]

@lru_cache()
def get_settings():
    return Settings()

@lru_cache()
def get_s3_client(s3_endpoint_url: Optional[str], aws_region: str):
    if s3_endpoint_url is not None:
        s3_client = boto3.client('s3', region_name=aws_region, endpoint_url=s3_endpoint_url)
    else:
        s3_client = boto3.client('s3', region_name=aws_region)

    return s3_client

app = FastAPI()


@app.post("/v1/drop")
async def drop(request: Request, settings: Settings = Depends(get_settings)) -> Response:
    s3_client = get_s3_client(settings.s3_endpoint_url, settings.aws_region)

    try:
        auth = request.headers['authorization']
    except KeyError:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED, content='The authorization header must be present')

    if not auth.startswith('Bearer '):
        return Response(status_code=status.HTTP_401_UNAUTHORIZED, content='The authorization header must start with "Bearer "')

    passed_token = auth.partition(' ')[2].strip()
    if not secrets.compare_digest(passed_token, settings.token.get_secret_value()):
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
        s3_client.put_object(Bucket=settings.bucket, Key=key, Body=body)
    await run_in_threadpool(upload)

    return Response(status_code=status.HTTP_201_CREATED, content=b'')
