import shlex
import subprocess
import os
import socket
import time
from datetime import datetime
from typing import Generator
from uuid import uuid4

import boto3
import httpx
import pytest
from fastapi.testclient import TestClient
from freezegun import freeze_time
from mypy_boto3_s3.service_resource import Bucket

from main import app, get_settings, Settings


@pytest.fixture
def app_process() -> Generator[subprocess.Popen, None, None]:
    def wait_until_connectable(p, port, max_attempts=1000):
        for i in range(0, max_attempts):
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.1):
                    break
            except (OSError, ConnectionRefusedError):
                p.poll()
                if p.returncode is not None or i == max_attempts - 1:
                    raise

                time.sleep(0.01)

    with open('Procfile', 'r') as f:
        lines = [line.partition(':') for line in f.readlines()]

    command = next((command for (name, _, command) in lines if command if name == 'web'))
    with subprocess.Popen(shlex.split(command), env={
            **os.environ,
            'PORT': '8888',
            'S3_ENDPOINT_URL': 'http://127.0.0.1:9000/',
            'AWS_ACCESS_KEY_ID': 'AKIAIDIDIDIDIDIDIDID',
            'AWS_SECRET_ACCESS_KEY': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
            'AWS_REGION': 'us-east-1',
            'BUCKET': 'my-bucket',
            'TOKEN': 'my-token',
        }) as p:
        wait_until_connectable(p, 8888)
        yield p
        p.terminate()
        p.wait(timeout=10)    
    p.kill()


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
def sock() -> Generator[socket.socket, None, None]:
    # Most HTTP clients don't allow sending a bad content-length, so we
    # make the request manually

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    yield sock
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    sock.close()


def test_no_auth(app_process: subprocess.Popen) -> None:
    response = httpx.post('http://127.0.0.1:8888/v1/drop')
    assert response.status_code == 401


def test_no_bearer_auth(app_process: subprocess.Popen) -> None:
    response = httpx.post('http://127.0.0.1:8888/v1/drop', headers={'authorization': 'my-token'})
    assert response.status_code == 401


def test_bad_bearer_auth(app_process: subprocess.Popen) -> None:
    response = httpx.post('http://127.0.0.1:8888/v1/drop', headers={'authorization': 'Bearer not-my-token'})
    assert response.status_code == 401


def test_empty_body(app_process: subprocess.Popen) -> None:
    response = httpx.post('http://127.0.0.1:8888/v1/drop', headers={'authorization': 'Bearer my-token'})
    assert response.status_code == 201


def test_too_large_body(app_process: subprocess.Popen) -> None:
    response = httpx.post('http://127.0.0.1:8888/v1/drop', headers={'authorization': 'Bearer my-token'}, content=b'-' * 20000)
    assert response.status_code == 413


def test_non_empty_body(app_process: subprocess.Popen, s3_bucket: Bucket) -> None:
    content = uuid4().hex.encode()
    response = httpx.post('http://127.0.0.1:8888/v1/drop', headers={'authorization': 'Bearer my-token'}, content=content)
    assert response.status_code == 201

    objects = list(s3_bucket.objects.all())
    assert len(objects) == 1
    assert objects[0].key.startswith(datetime.now().isoformat()[:10])
    assert objects[0].get()['Body'].read() == content


def test_chunked(app_process: subprocess.Popen) -> None:
    response = httpx.post('http://127.0.0.1:8888/v1/drop', headers={'authorization': 'Bearer my-token'}, content=(b'-' * 20000,))
    assert response.status_code == 411


def test_non_integer_content_length(app_process: subprocess.Popen, sock: socket.socket) -> None:
    sock.connect(('127.0.0.1', 8888))
    sock.sendall(
        b'POST /v1/drop HTTP/1.1\r\n'
        b'host: example.com\r\n'
        b'token: Bearer my-token\r\n'
        b'content-length: bad\r\n'
        b'\r\n'
    )
    raw_response = sock.recv(1024)

    assert raw_response.startswith(b'HTTP/1.1 400 ')


def test_lying_content_length(app_process: subprocess.Popen, sock: socket.socket) -> None:
    sock.connect(('127.0.0.1', 8888))
    sock.sendall(
        b'POST /v1/drop HTTP/1.1\r\n'
        b'host: example.com\r\n'
        b'token: Bearer my-token\r\n'
        b'content-length: 3\r\n'
        b'\r\n'
        b'1234'
    )
    raw_response = sock.recv(1024)

    assert raw_response.startswith(b'HTTP/1.1 400 ')


def test_multiple_requests_at_the_same_time(s3_bucket: Bucket, monkeypatch) -> None:
    # We usually avoid mocking/patching or anything that assumes the server is FastAPI, or even Python
    # However, for this test we want to force multiple requests to happen at the exact same time, and
    # there is no known way of doing this without assuming more about the internals of the server and
    # overriding them

    async def settings_not_from_environment_variables():
        return Settings(token='my-token', aws_region='us-east-1', s3_endpoint_url='http://127.0.0.1:9000/', bucket='my-bucket')

    app.dependency_overrides[get_settings] = settings_not_from_environment_variables

    # boto3 users environment variables directly, so we can't use FastAPIs usual mechanism of overriding settings
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'AKIAIDIDIDIDIDIDIDID')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
    client = TestClient(app)

    with freeze_time():
        now = datetime.now()
        response = client.post('http://127.0.0.1:8888/v1/drop', headers={'authorization': 'Bearer my-token'}, content=b'-')
        response = client.post('http://127.0.0.1:8888/v1/drop', headers={'authorization': 'Bearer my-token'}, content=b'-')
        assert response.status_code == 201

    objects = list(s3_bucket.objects.all())
    assert len(objects) == 2
    assert objects[0].key.startswith(now.isoformat())
    assert objects[0].get()['Body'].read() == b'-'
    assert objects[1].key.startswith(now.isoformat())
    assert objects[1].get()['Body'].read() == b'-'
