# s3-dropbox [![Proof](https://github.com/uktrade/s3-dropbox/actions/workflows/test.yml/badge.svg)](https://github.com/uktrade/s3-dropbox/actions/workflows/test.yml)

A bearer token authenticated dropbox that drops its payloads into an S3 bucket.

This is a simple application: it is for fairly low concurrency situations, and many use cases would require an additional layer of security, for example an IP address filter, to run in front of this. Payloads are expected to be small: streaming is not used.


## Running type checking and tests

Python requirements must be installed and a local S3-like service started:

```bash
pip install -r requirements-dev.txt
./start-services
````

Then to run type checking:

```bash
mypy .
````

Then to run the tests:

```bash
pytest
````

Or to run the tests with more verbose output:

```bash
pytest -s
````


## Confguration

Configuration is via environment variables

- `PORT`

  The port the application listens on for HTTP requests

- `BUCKET`

  The S3 bucket name to upload files to

- `AWS_REGION`

  The region of the S3 bucket

- `AWS_ACCESS_KEY_ID` & `AWS_SECRET_ACCESS_KEY`

  The access key used to authenticate with S3 to put objects. This must have `s3:PutObject` permissions

- `S3_ENDPOINT_URL`

  The endpoint of S3 or the S3-compatible service. If using AWS S3, this is usually not required.


## Testing strategy

The tests do not depend on what server is running, or even if the server is a Python. This is deliberate so another server could be swapped out, and if the tests pass, this would give confidence that there will be no user-facing break of behaviour.
