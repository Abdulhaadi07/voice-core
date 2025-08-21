import pytest
from unittest.mock import patch, MagicMock
import requests
from voice_core.services.wazo_helpers.wazo_admin_token import (
    get_wazo_admin_token,
    get_cached_wazo_admin_token_from_cache,
    create_wazo_admin_token,
    set_cached_wazo_admin_token,
    clear_wazo_admin_token_cache,
)

@pytest.fixture
def mock_cache():
    with patch("voice_core.services.wazo_helpers.wazo_admin_token.caches") as mock_caches:
        mock_cache_instance = MagicMock()
        mock_caches.__getitem__.return_value = mock_cache_instance
        yield mock_cache_instance

@pytest.fixture
def mock_requests_post():
    with patch("voice_core.services.wazo_helpers.wazo_admin_token.requests.post") as mock_post:
        yield mock_post


def test_get_cached_wazo_admin_token_from_cache_cache_hit(mock_cache):
    mock_cache.get.return_value = "cached-token-123"
    token = get_cached_wazo_admin_token_from_cache()
    assert token == "cached-token-123"
    mock_cache.get.assert_called_once_with("wazo_admin_token")

def test_get_cached_wazo_admin_token_from_cache_cache_miss(mock_cache):
    mock_cache.get.return_value = None
    token = get_cached_wazo_admin_token_from_cache()
    assert token is None

def test_create_wazo_admin_token_success(mock_requests_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"token": "new-token-456"}}
    mock_requests_post.return_value = mock_response

    token = create_wazo_admin_token()
    assert token == "new-token-456"
    mock_requests_post.assert_called_once()

def test_create_wazo_admin_token_failure_status(mock_requests_post):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_requests_post.return_value = mock_response

    token = create_wazo_admin_token()
    assert token is None

def test_create_wazo_admin_token_raises_on_exception(mock_requests_post):
    mock_requests_post.side_effect = Exception("Network failure")

    with pytest.raises(Exception) as excinfo:
        create_wazo_admin_token()
    assert "Network failure" in str(excinfo.value)

def test_set_cached_wazo_admin_token_calls_cache_set(mock_cache):
    set_cached_wazo_admin_token("some-token")
    mock_cache.set.assert_called_once()
    args, kwargs = mock_cache.set.call_args
    assert args[0] == "wazo_admin_token"
    assert args[1] == "some-token"

def test_clear_wazo_admin_token_cache_calls_cache_delete(mock_cache):
    clear_wazo_admin_token_cache()
    mock_cache.delete.assert_called_once_with("wazo_admin_token")

@patch("voice_core.services.wazo_helpers.wazo_admin_token.get_cached_wazo_admin_token_from_cache")
@patch("voice_core.services.wazo_helpers.wazo_admin_token.create_wazo_admin_token")
@patch("voice_core.services.wazo_helpers.wazo_admin_token.set_cached_wazo_admin_token")
def test_get_wazo_admin_token_cache_hit_returns_token(mock_set_cache, mock_create_token, mock_get_cache):
    # Cached token exists
    mock_get_cache.return_value = "cached-token-789"
    token = get_wazo_admin_token()
    assert token == "cached-token-789"
    mock_create_token.assert_not_called()
    mock_set_cache.assert_not_called()

@patch("voice_core.services.wazo_helpers.wazo_admin_token.get_cached_wazo_admin_token_from_cache")
@patch("voice_core.services.wazo_helpers.wazo_admin_token.create_wazo_admin_token")
@patch("voice_core.services.wazo_helpers.wazo_admin_token.set_cached_wazo_admin_token")
def test_get_wazo_admin_token_cache_miss_creates_and_caches_token(mock_set_cache, mock_create_token, mock_get_cache):
    # No cached token, create new
    mock_get_cache.return_value = None
    mock_create_token.return_value = "new-token-abc"
    
    token = get_wazo_admin_token()
    assert token == "new-token-abc"
    mock_create_token.assert_called_once()
    mock_set_cache.assert_called_once_with("new-token-abc")
