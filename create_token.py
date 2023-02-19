import base64
import hashlib
import secrets


def create_token():
    # For a completely random long token (as opposed to a password), we don't
    # need a salt or key derivation function. But we do only store a sha256 of
    # the token on the server to mitigate the impact of the server's environment
    # leaking - it would be very difficult to derive the token from its sha256
    token_client = secrets.token_urlsafe(64)
    return token_client, base64.b64encode(hashlib.sha256(token_client.encode()).digest()).decode()


if __name__ == '__main__':
    token_client, token_server = create_token()
    print(f'Plain text Bearer token to give to client: {token_client}')
    print(f'TOKEN to store in server:                  {token_server}')
