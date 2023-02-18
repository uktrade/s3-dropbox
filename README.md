# s3-dropbox [![Proof](https://github.com/uktrade/s3-dropbox/actions/workflows/test.yml/badge.svg)](https://github.com/uktrade/s3-dropbox/actions/workflows/test.yml)

A bearer token authenticated dropbox that drops its payloads into an S3 bucket.

This is a simple application: it is for fairly low concurrency situations, and an additional layer of security in front is expected to run in front of this application, for example an IP address filter.


## Running tests

Python requirements must be installed and a local S3-like service started:

```bash
pip install -r requirements-dev.txt
./start-services
````

Then to run the tests:

```bash
pytest
````

Or to run the tests with more verbose output:

```bash
pytest -s
````


## Testing strategy

The tests do not depend on what server is running, or even if the server is a Python. This is deliberate so another server could be swapped out, and if the tests pass, this would give confidence that there will be no user-facing break of behaviour.
