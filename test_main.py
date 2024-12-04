import os
import hashlib
import re
import subprocess
from base64 import b64encode
from datetime import datetime
from typing import Generator, Tuple
from uuid import uuid4

import boto3
import pytest
from freezegun import freeze_time
from mypy_boto3_s3.service_resource import Bucket

from main import lambda_handler
from create_token import create_token


@pytest.fixture
def s3_bucket() -> Generator[Bucket, None, None]:
    session = boto3.Session(
        aws_access_key_id='AKIAIDIDIDIDIDIDIDID',
        aws_secret_access_key='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    )
    _s3_bucket = session.resource('s3', endpoint_url='http://127.0.0.1:9000/').Bucket('my-bucket')
    _s3_bucket.objects.delete()
    yield _s3_bucket
    _s3_bucket.objects.delete()


@pytest.fixture
def token():
    token_client, token_server = create_token()
    return token_client, token_server


@pytest.fixture
def environment_variables(monkeypatch, token):
    token_client, token_server = token
    monkeypatch.setenv('AUTH_TOKEN', token_server)
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'AKIAIDIDIDIDIDIDIDID')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
    monkeypatch.setenv('AWS_REGION', 'us-east-1')
    monkeypatch.setenv('BUCKET', 'my-bucket')
    monkeypatch.setenv('S3_ENDPOINT_URL', 'http://127.0.0.1:9000/')
    monkeypatch.setenv('CDN_TOKEN_HTTP_HEADER_NAME', 'x-cdn-authorisation')
    monkeypatch.setenv('CDN_TOKEN', b64encode(hashlib.sha256('cdn_header_value'.encode()).digest()).decode())


def test_no_auth(environment_variables) -> None:
    response = lambda_handler({}, None)
    assert response['statusCode'] == 401


def test_no_bearer_auth(environment_variables) -> None:
    response = lambda_handler({
        "headers": {
            "authorization": "my-token",
            "x-cdn-authorisation": "Bearer cdn_header_value"
        },
    }, None)
    assert response['statusCode'] == 401


def test_bad_bearer_auth(environment_variables) -> None:
    response = lambda_handler({
        "headers": {
            "authorization": "Bearer not-my-token",
            "x-cdn-authorisation": "Bearer cdn_header_value"
        },
    }, None)
    assert response['statusCode'] == 401


def test_no_cdn_header(environment_variables) -> None:
    response = lambda_handler({
        "headers": {
            "authorization": "my-token",
        },
    }, None)
    assert response['statusCode'] == 401


def test_get_fails(token, environment_variables) -> None:
    token_client, token_server = token
    response = lambda_handler({
        "headers": {
            "authorization": f'Bearer {token_client}',
            "x-cdn-authorisation": "Bearer cdn_header_value"
        },
    }, None)
    assert response['statusCode'] == 405


def test_too_large_body(token, environment_variables) -> None:
    token_client, token_server = token
    response = lambda_handler({
        "headers": {
            "authorization": f'Bearer {token_client}',
            "content-length": "20000",
            "x-cdn-authorisation": "Bearer cdn_header_value"
        },
        "requestContext": {
            "http": {
                "method": "POST",
            },
        },
    }, None)
    assert response['statusCode'] == 413


def test_empty_body(token, environment_variables) -> None:
    token_client, token_server = token
    response = lambda_handler({
        "headers": {
            "authorization": f'Bearer {token_client}',
            "content-length": "0",
            "x-cdn-authorisation": "Bearer cdn_header_value"
        },
        "requestContext": {
            "http": {
                "method": "POST",
            },
        },
        "isBase64Encoded": True,
        "body": "",
    }, None)
    assert response['statusCode'] == 202


def test_no_body(token, environment_variables) -> None:
    token_client, token_server = token
    response = lambda_handler({
        "headers": {
            "authorization": f'Bearer {token_client}',
            "content-length": "0",
            "x-cdn-authorisation": "Bearer cdn_header_value"
        },
        "requestContext": {
            "http": {
                "method": "POST",
            },
        },
    }, None)
    assert response['statusCode'] == 400


def test_no_content_length(token, environment_variables) -> None:
    token_client, token_server = token
    response = lambda_handler({
        "headers": {
            "authorization": f'Bearer {token_client}',
            "x-cdn-authorisation": "Bearer cdn_header_value"
        },
        "requestContext": {
            "http": {
                "method": "POST",
            },
        },
    }, None)
    assert response['statusCode'] == 411


def test_body_non_base64_encoding(token, environment_variables, s3_bucket) -> None:
    token_client, token_server = token
    content = uuid4().hex.encode()
    content_encoded = b64encode(content).decode()
    response = lambda_handler({
        "headers": {
            "authorization": f'Bearer {token_client}',
            "content-length": "0",
            "x-cdn-authorisation": "Bearer cdn_header_value"
        },
        "requestContext": {
            "http": {
                "method": "POST",
            },
        },
        "isBase64Encoded": False,
        "body": "Something non-base64-encoded",
    }, None)
    assert response['statusCode'] == 202

    objects = list(s3_bucket.objects.all())
    assert len(objects) == 1
    assert objects[0].key.startswith(datetime.now().isoformat()[:10])
    assert objects[0].get()['Body'].read() == b'Something non-base64-encoded'


def test_non_empty_body(token, environment_variables, s3_bucket) -> None:
    token_client, token_server = token
    content = uuid4().hex.encode()
    content_encoded = b64encode(content).decode()
    response = lambda_handler({
        "headers": {
            "authorization": f'Bearer {token_client}',
            "content-length": str(len(content)),
            "x-cdn-authorisation": "Bearer cdn_header_value"
        },
        "requestContext": {
            "http": {
                "method": "POST",
            },
        },
        "isBase64Encoded": True,
        "body": content_encoded,
    }, None)
    assert response['statusCode'] == 202

    objects = list(s3_bucket.objects.all())
    assert len(objects) == 1
    assert objects[0].key.startswith(datetime.now().isoformat()[:10])
    assert objects[0].get()['Body'].read() == content


def test_multiple_requests_at_the_same_time(token, environment_variables, s3_bucket) -> None:
    # Makes sure that even if we send payloads at the exact same moment, they both get saved
    # to the bucket

    token_client, token_server = token

    with freeze_time():
        now = datetime.now()
        content = uuid4().hex.encode()
        content_encoded = b64encode(content).decode()
        response = lambda_handler({
            "headers": {
                "authorization": f'Bearer {token_client}',
                "content-length": str(len(content)),
                "x-cdn-authorisation": "Bearer cdn_header_value"
            },
            "requestContext": {
                "http": {
                    "method": "POST",
                },
            },
            "isBase64Encoded": True,
            "body": content_encoded,
        }, None)
        assert response['statusCode'] == 202
        response = lambda_handler({
            "headers": {
                "authorization": f'Bearer {token_client}',
                "content-length": str(len(content)),
                "x-cdn-authorisation": "Bearer cdn_header_value"
            },
            "requestContext": {
                "http": {
                    "method": "POST",
                },
            },
            "isBase64Encoded": True,
            "body": content_encoded,
        }, None)
        assert response['statusCode'] == 202

    objects = list(s3_bucket.objects.all())
    assert len(objects) == 2
    assert objects[0].key.startswith(now.isoformat())
    assert objects[0].get()['Body'].read() == content
    assert objects[1].key.startswith(now.isoformat())
    assert objects[1].get()['Body'].read() == content


def test_create_token():
    stdout = subprocess.run(['python', 'create_token.py'], stdout=subprocess.PIPE).stdout
    assert re.match(rb'.*Client token \(plain text\):\s+\S{86}', stdout)
    assert re.match(rb'.*Server token \(hashed client token\):\s+\S{44}', stdout, re.DOTALL)
