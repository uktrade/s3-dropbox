import contextlib
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
from mypy_boto3_s3.service_resource import Bucket


@pytest.fixture
def app() -> Generator[subprocess.Popen, None, None]:
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


def test_no_auth(app: subprocess.Popen) -> None:
    response = httpx.post('http://127.0.0.1:8888/v1/drop')
    assert response.status_code == 401

def test_no_bearer_auth(app: subprocess.Popen) -> None:
    response = httpx.post('http://127.0.0.1:8888/v1/drop', headers={'authorization': 'my-token'})
    assert response.status_code == 401

def test_bad_bearer_auth(app: subprocess.Popen) -> None:
    response = httpx.post('http://127.0.0.1:8888/v1/drop', headers={'authorization': 'Bearer not-my-token'})
    assert response.status_code == 401

def test_empty_body(app: subprocess.Popen) -> None:
    response = httpx.post('http://127.0.0.1:8888/v1/drop', headers={'authorization': 'Bearer my-token'})
    assert response.status_code == 201

def test_non_empty_body(app: subprocess.Popen, s3_bucket: Bucket) -> None:
    content = uuid4().hex.encode()
    response = httpx.post('http://127.0.0.1:8888/v1/drop', headers={'authorization': 'Bearer my-token'}, content=content)
    assert response.status_code == 201

    objects = list(s3_bucket.objects.all())
    assert len(objects) == 1
    assert objects[0].key.startswith(datetime.now().isoformat()[:10])
    assert objects[0].get()['Body'].read() == content

def test_chunked(app: subprocess.Popen) -> None:
    response = httpx.post('http://127.0.0.1:8888/v1/drop', headers={'authorization': 'Bearer my-token'}, content=(b'-' * 20000,))
    assert response.status_code == 411


def test_non_integer_content_length(app: subprocess.Popen) -> None:
    # Most HTTP clients don't allow sending a non-integer content-length, so we
    # make the request manually

    @contextlib.contextmanager
    def get_sock():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            yield sock
        finally:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()

    with get_sock() as sock:
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


def test_lying_content_length(app: subprocess.Popen) -> None:
    # Most HTTP clients don't allow sending a non-integer content-length, so we
    # make the request manually

    @contextlib.contextmanager
    def get_sock():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            yield sock
        finally:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()

    with get_sock() as sock:
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


def test_too_large_body(app: subprocess.Popen) -> None:
    response = httpx.post('http://127.0.0.1:8888/v1/drop', headers={'authorization': 'Bearer my-token'}, content=b'-' * 20000)
    assert response.status_code == 413
