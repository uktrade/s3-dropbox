import hashlib
import os
import secrets
from base64 import b64encode, b64decode
from datetime import datetime
from uuid import uuid4

import boto3


def lambda_handler(event, context):
    s3_client = boto3.client('s3', endpoint_url=os.environ.get('S3_ENDPOINT_URL'))

    method = event.get("requestContext", {}).get("http", {}).get("method")
    headers = event.get("headers", {})
    content_length = headers.get("content-length")
    body = event.get("body")

    for token_name, token_value, token_hashed in (
        (os.environ['CDN_TOKEN_HTTP_HEADER_NAME'], headers.get(os.environ['CDN_TOKEN_HTTP_HEADER_NAME']), os.environ['CDN_TOKEN']),
        ("authorization", headers.get("authorization"), os.environ['AUTH_TOKEN']),
    ):
        if token_value is None:
            return {
                'statusCode': 401,
                'body': f'The {token_name} header must be present',
            }

        if not token_value.startswith('Bearer '):
            return {
                'statusCode': 401,
                'body': f'The {token_name} header must start with "Bearer "',
            }

        if not secrets.compare_digest(
            token_hashed.encode(),
            b64encode(hashlib.sha256(token_value.partition(' ')[2].strip().encode()).digest()),
        ):
            return {
                'statusCode': 401,
                'body': f'The Bearer token in {token_name} is not correct',
            }

    if method != 'POST':
        return {
            'statusCode': 405,
            'body': 'Only POST is supported',
        }

    if content_length is None:
        return {
            'statusCode': 411,
            'body': 'The content-length header must be present',
        }

    if int(content_length) > 10240:
        return {
            'statusCode': 413,
            'body': 'The request body must be less 10240 bytes',
        }

    if body is None:
        return {
            'statusCode': 400,
            'body': 'There must be a request body',
        }

    body_bytes = \
        b64decode(body) if event.get('isBase64Encoded') else \
        body.encode('utf-8')
    
    key = f'{datetime.now().isoformat()}-{uuid4()}'
    s3_client.put_object(Bucket=os.environ['BUCKET'], Key=key, Body=body_bytes)

    return {
        'statusCode': 202,
        'headers': {
            "Content-Type": "text/plain",
        },
        'body': '',
    }
