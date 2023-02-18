import contextlib
import shlex
import subprocess
import os
import socket
import time

import httpx
import pytest


@pytest.fixture
def app():
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
    with subprocess.Popen(shlex.split(command), env={**os.environ, 'PORT': '8888'}) as p:
        wait_until_connectable(p, 8888)
        yield p
        p.terminate()
        p.wait(timeout=10)    
    p.kill()


def test_empty_body(app):
    response = httpx.post('http://127.0.0.1:8888/v1/drop')
    assert response.status_code == 201


def test_chunked(app):
    response = httpx.post('http://127.0.0.1:8888/v1/drop', content=(b'-' * 20000,))
    assert response.status_code == 411


def test_bad_content_length(app):
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
            b'content-length: bad\r\n'
            b'\r\n'
        )
        raw_response = sock.recv(1024)

    assert raw_response.startswith(b'HTTP/1.1 400 ')


def test_too_large_body(app):
    response = httpx.post('http://127.0.0.1:8888/v1/drop', content=b'-' * 20000)
    assert response.status_code == 413
