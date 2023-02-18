# s3-dropbox [![Proof](https://github.com/uktrade/s3-dropbox/actions/workflows/test.yml/badge.svg)](https://github.com/uktrade/s3-dropbox/actions/workflows/test.yml)

A simple bearer token authenticated dropbox that drops its payloads into an S3 bucket


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
