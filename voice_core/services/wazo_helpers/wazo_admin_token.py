from django.core.cache import caches
import requests
from requests.auth import HTTPBasicAuth
from config.settings.base import (
    WAZO_ADMIN_PASSWORD,
    WAZO_ADMIN_USERNAME,
    WAZO_API_URL,
    WAZO_TOKEN_EXPIRATION,
)

import logging
logger = logging.getLogger(__name__)

# Cache key for Wazo admin token
WAZO_TOKEN_CACHE_KEY = 'wazo_admin_token'
_cache_timeout = int(WAZO_TOKEN_EXPIRATION) # default timeout


def get_wazo_admin_token() -> str:
    """
    Get Wazo admin token with Redis caching.
    If cached token is valid, returns it. Otherwise, creates a new token and caches it in Redis.
    """
    # Try to get cached token first
    cached_token = get_cached_wazo_admin_token_from_cache()
    if cached_token:
        logger.info("Get Token from redis cache")
        return cached_token
    
    # If no valid cached token, create a new one
    logger.info("No valid cached Wazo admin token found in Redis, creating new token ...... ")
    new_token_uuid = create_wazo_admin_token()
    
    # Cache the new token in Redis
    logger.info(f"Created New Admin Token: {new_token_uuid}")
    set_cached_wazo_admin_token(new_token_uuid)
    
    return new_token_uuid

def get_cached_wazo_admin_token_from_cache() -> str: 
    """
    Get the cached Wazo admin token using Redis cache.
    Returns the token if cached, None otherwise.
    """
    wazo_cache = caches['wazo_tokens']
    cached_token = wazo_cache.get(WAZO_TOKEN_CACHE_KEY)
    if cached_token:
        logger.info(f"Returning cached Wazo admin token from Redis")
        logger.debug("Returning cached Wazo admin token from Redis")
        return cached_token
    else:
        logger.debug("No cached Wazo admin token found in Redis")
        return None

def create_wazo_admin_token() -> str: 
    """
    Create a new Wazo Admin token using a POST request to the Wazo API.
    """
    wazo_admin_username = str(WAZO_ADMIN_USERNAME)
    wazo_admin_password = str(WAZO_ADMIN_PASSWORD)
    wazo_api_url = WAZO_API_URL
    wazo_token_expiration = int(WAZO_TOKEN_EXPIRATION)


    url = f"{wazo_api_url}/api/auth/0.1/token"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "expiration": wazo_token_expiration
    }
    
    logger.info(f"Creating Wazo admin token for admin: {wazo_admin_username}")
    try:
        response = requests.post(
            url,
            headers=headers,
            auth=HTTPBasicAuth(wazo_admin_username, wazo_admin_password),
            json=payload,
            verify=False  # -k in curl disables SSL verification
        )
        if response.status_code == 200:
            data = response.json()
            new_token_uuid = data["data"]["token"]
            logger.info(f"New Wazo admin token for admin: {new_token_uuid}")
            return new_token_uuid
        else:
            print(f"Error at Wazo.py {response.status_code}: {response.text}")
            return None
        
    except Exception as e:
        logger.error(f"Failed to create Wazo admin token: {e}")
        raise
    
def set_cached_wazo_admin_token(token: str) -> None:
    """
    Cache the Wazo admin token using Redis cache.
    """
    wazo_cache = caches['wazo_tokens']
    wazo_cache.set(WAZO_TOKEN_CACHE_KEY, token, _cache_timeout)
    logger.debug("Wazo admin token cached successfully in Redis")

def clear_wazo_admin_token_cache() -> None:
    """
    Clear the cached Wazo admin token from Redis.
    """
    wazo_cache = caches['wazo_tokens']
    wazo_cache.delete(WAZO_TOKEN_CACHE_KEY)
    logger.debug("Wazo admin token cache cleared from Redis")
