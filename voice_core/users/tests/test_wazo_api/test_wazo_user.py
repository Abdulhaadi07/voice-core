import pytest
from unittest.mock import patch, MagicMock
from voice_core.users.wazo_helpers.wazo_user import (
    create_wazo_user,
    generate_valid_password,
    delete_wazo_user,
)
import uuid
import string

class DummyUser:
    first_name = "John"
    last_name = "Doe"
    name = "johndoe"
    email = "john@example.com"

@patch("voice_core.users.wazo_helpers.wazo_user.requests.post")
def test_create_wazo_user_success(mock_post):
    fake_uuid = str(uuid.uuid4())
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"uuid": fake_uuid, "username": "johndoe"}
    mock_post.return_value = mock_response

    user = DummyUser()
    admin_token = "fake-token"
    tenant_uuid = uuid.uuid4()

    result = create_wazo_user(user, admin_token, tenant_uuid)

    assert isinstance(result, list)
    assert isinstance(result[0], uuid.UUID)
    assert result[0] == uuid.UUID(fake_uuid)
    assert result[1] == "johndoe"
    mock_post.assert_called_once()


@patch("voice_core.users.wazo_helpers.wazo_user.requests.post")
def test_create_wazo_user_failure_status(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad request"
    mock_post.return_value = mock_response

    user = DummyUser()
    admin_token = "fake-token"
    tenant_uuid = uuid.uuid4()

    result = create_wazo_user(user, admin_token, tenant_uuid)
    assert result is None

@patch("voice_core.users.wazo_helpers.wazo_user.requests.post")
def test_create_wazo_user_exception(mock_post):
    mock_post.side_effect = Exception("Connection error")

    user = DummyUser()
    admin_token = "fake-token"
    tenant_uuid = uuid.uuid4()

    with pytest.raises(Exception):
        create_wazo_user(user, admin_token, tenant_uuid)

    mock_post.assert_called_once()

def test_generate_valid_password_length_and_content():
    pwd = generate_valid_password(12)
    
    assert len(pwd) == 12
    assert any(c.isupper() for c in pwd)
    assert any(c.isdigit() for c in pwd)
    assert any(c in string.punctuation for c in pwd)


@patch("voice_core.users.wazo_helpers.wazo_user.requests.delete")
def test_delete_wazo_user_success(mock_delete):
    mock_response = MagicMock()
    mock_response.status_code = 204
    mock_delete.return_value = mock_response

    result = delete_wazo_user(uuid.uuid4(), "fake-token")
    assert result is True
    mock_delete.assert_called_once()

@patch("voice_core.users.wazo_helpers.wazo_user.requests.delete")
def test_delete_wazo_user_failure_status(mock_delete):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad request"
    mock_delete.return_value = mock_response

    result = delete_wazo_user(uuid.uuid4(), "fake-token")
    assert result is False

@patch("voice_core.users.wazo_helpers.wazo_user.requests.delete")
def test_delete_wazo_user_exception_returns_false(mock_delete):
    mock_delete.side_effect = Exception("Connection error")

    result = delete_wazo_user(uuid.uuid4(), "fake-token")
    assert result is False
