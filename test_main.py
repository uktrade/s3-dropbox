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


def test_main(app):
    response = httpx.post('http://127.0.0.1:8888/v1/drop')
    assert response.status_code == 201
