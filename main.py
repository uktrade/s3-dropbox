import base64
import hashlib
import os
import secrets
from datetime import datetime
from functools import lru_cache
from typing import Optional
from uuid import uuid4

import boto3
from fastapi import Depends, FastAPI, Header, Request, status
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


@app.post("/v1/drop", response_class=Response, status_code=202,
    description="Accepts a raw binary blob to be dropped into the pre-configured S3 bucket",
    responses={
        202: {"description": "A successful drop", "content": {"text/plain": {}}},
        401: {"description": "The Bearer token is not passed or is incorrect", "content": {"text/plain": {}}},
        411: {"description": "The content-length header has not been passed, for example if chunked encoding has been used", "content": {"text/plain": {}}},
        413: {"description": "The body is too long. The maximum is 10240 bytes", "content": {"text/plain": {}}},
    },
)
async def drop(
        request: Request,
        authorization: None | str = Header(default=None, description="Must be in 'Bearer _token_' format, where _token_ is the pre-configured bearer token"),
        content_length: None | str = Header(default=None, description="The length of the body, which must be less than or equal to 10240"),
        settings: Settings = Depends(get_settings),
    ) -> Response:
    s3_client = get_s3_client(settings.s3_endpoint_url, settings.aws_region)

    if authorization is None:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED, content='The authorization header must be present')

    if not authorization.startswith('Bearer '):
        return Response(status_code=status.HTTP_401_UNAUTHORIZED, content='The authorization header must start with "Bearer "')

    if not secrets.compare_digest(
        settings.token.get_secret_value().encode(),
        base64.b64encode(hashlib.sha256(authorization.partition(' ')[2].strip().encode()).digest()),
    ):
        return Response(status_code=status.HTTP_401_UNAUTHORIZED, content='The Bearer token is not correct')

    if content_length is None:
        return Response(status_code=status.HTTP_411_LENGTH_REQUIRED, content=b'The content-length header must be present')

    if int(content_length) > 10240:
        return Response(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, content=b'The request body must be less 10240 bytes')

    body = await request.body()
    key = f'{datetime.now().isoformat()}-{uuid4()}'

    def upload():
        s3_client.put_object(Bucket=settings.bucket, Key=key, Body=body)
    await run_in_threadpool(upload)

    return Response(status_code=status.HTTP_202_ACCEPTED, content=b'', media_type='text/plain')
