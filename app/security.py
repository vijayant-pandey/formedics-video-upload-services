from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
import os
from json import loads


api_key_header = APIKeyHeader(name='X-API-Key', auto_error=False)
FM_API_KEYS = os.environ.get('FM_API_SERVICES_KEYS', '{}')
FM_API_KEYS = loads(FM_API_KEYS, strict=False)

EXTERNAL_APP_KEYS = FM_API_KEYS.get('external', {})
EXTERNAL_APP_KEYS = [v for k,v in EXTERNAL_APP_KEYS.items()]

INTERNAL_APP_KEYS = FM_API_KEYS.get('internal', {})
INTERNAL_APP_KEYS = [v for k,v in INTERNAL_APP_KEYS.items()]

ITERABLE_APP_KEYS = FM_API_KEYS.get('iterable', {})
ITERABLE_APP_KEYS = [v for k,v in ITERABLE_APP_KEYS.items()]

AI_APP_KEYS = FM_API_KEYS.get('ai', {})
AI_APP_KEYS = [v for k,v in AI_APP_KEYS.items()]

BACKEND_ONLY_KEYS = FM_API_KEYS.get('backend', {})
BACKEND_ONLY_KEYS = [v for k,v in BACKEND_ONLY_KEYS.items()]

def api_key_validator(valid_keys: set):
    def validate_key(api_key: str=Security(api_key_header)):
        if api_key and api_key in valid_keys:
            return api_key
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail='Invalid or missing API Key'
        )
    return validate_key

EXTERNAL_APP_API_KEY_VALIDATOR = api_key_validator(set(EXTERNAL_APP_KEYS))
INTERNAL_APP_API_KEY_VALIDATOR = api_key_validator(set(INTERNAL_APP_KEYS))
ITERABLE_APP_API_KEY_VALIDATOR = api_key_validator(set(ITERABLE_APP_KEYS))
AI_APP_API_KEY_VALIDATOR = api_key_validator(set(AI_APP_KEYS))
BACKEND_SERVICES_KEY_VALIDATOR = api_key_validator(set(BACKEND_ONLY_KEYS))
