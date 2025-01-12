import secrets

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.security.api_key import APIKeyCookie, APIKeyHeader, APIKeyQuery
from starlette.status import HTTP_403_FORBIDDEN

import config

# API_KEY = "1234567asdfgh"

API_KEY = config.parameters.get("api_key")
API_KEY_NAME = "access-token"

api_key_query = APIKeyQuery(name=API_KEY_NAME, auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
api_key_cookie = APIKeyCookie(name=API_KEY_NAME, auto_error=False)


basic_auth = HTTPBasic()


async def get_api_key(
    api_key_query: str = Security(api_key_query),
    api_key_header: str = Security(api_key_header),
    api_key_cookie: str = Security(api_key_cookie),
):
    if api_key_query == API_KEY:
        return api_key_query
    elif api_key_header == API_KEY:
        return api_key_header
    elif api_key_cookie == API_KEY:
        return api_key_cookie
    else:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Could not validate credentials"
        )


def verify_credentials(credentials: HTTPBasicCredentials = Depends(basic_auth)):
    correct_username = secrets.compare_digest(credentials.username, config.USER_NAME)
    correct_password = secrets.compare_digest(credentials.password, config.PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True
