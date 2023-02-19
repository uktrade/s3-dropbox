import base64
import hashlib
import secrets


def create_token():
    token_client = secrets.token_urlsafe(64)
    salt = secrets.token_urlsafe(64)
    n = 16384
    r = 8
    p = 1
    dklen = 64
    hashed_and_salted_bytes = hashlib.scrypt(token_client.encode('ascii'), salt=salt.encode('ascii'), n=n, r=r, p=p, dklen=dklen)
    hashed_and_salted = base64.b64encode(hashed_and_salted_bytes).decode('ascii')

    return token_client, f'{n}|{r}|{p}|{dklen}|{salt}|{hashed_and_salted}'


if __name__ == '__main__':
    token_client, token_server = create_token()
    print(f'Plain text Bearer token to give to client: {token_client}')
    print(f'TOKEN to store in server:                  {token_server}')
