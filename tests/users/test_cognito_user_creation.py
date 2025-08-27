import pytest
from unittest.mock import (
    patch, 
    MagicMock,
)
from botocore.exceptions import ClientError
from rest_framework.exceptions import ValidationError
from voice_core.users.registration.cognito import (
    create_cognito_user, 
    delete_cognito_user,
)


class MockInvalidPasswordException(ClientError):
    def __init__(self, *args, **kwargs):
        super().__init__({'Error': {'Code': 'InvalidPasswordException', 'Message': 'Password too weak'}}, 'SignUp')

class MockUsernameExistsException(ClientError):
    def __init__(self, *args, **kwargs):
        super().__init__({'Error': {'Code': 'UsernameExistsException', 'Message': 'User already exists'}}, 'SignUp')

class MockUserNotFoundException(ClientError):
    def __init__(self, *args, **kwargs):
        super().__init__({'Error': {'Code': 'UserNotFoundException', 'Message': 'User not found'}}, 'AdminGetUser')


@pytest.fixture(autouse=True)
def mock_client():
    """
    Patches the boto3 client to avoid real Cognito calls using an autouse fixture.
    This fixture will be automatically used by all tests in this file.
    """
    mock_client = MagicMock()
    mock_client.exceptions.InvalidPasswordException = MockInvalidPasswordException
    mock_client.exceptions.UsernameExistsException = MockUsernameExistsException
    mock_client.exceptions.UserNotFoundException = MockUserNotFoundException

    with patch("voice_core.users.registration.cognito.client", mock_client):
        yield mock_client


@patch("time.sleep", return_value=None)
def test_create_cognito_user_success(mock_sleep, mock_client):
    mock_client.sign_up.return_value = {"UserSub": "12345"}
    mock_client.admin_confirm_sign_up.return_value = {}

    user_sub = create_cognito_user("test@example.com", "ValidPassw0rd!", "Test User")

    assert user_sub == "12345"
    mock_client.sign_up.assert_called_once()
    mock_client.admin_confirm_sign_up.assert_called_once()
    mock_sleep.assert_not_called()


def test_create_cognito_user_invalid_password(mock_client):
    mock_client.sign_up.side_effect = mock_client.exceptions.InvalidPasswordException()

    with patch("voice_core.users.registration.cognito.delete_cognito_user", MagicMock()) as mock_delete:
        with pytest.raises(ValidationError) as exc:
            create_cognito_user("test@example.com", "weak", "Test User")

        assert "password" in str(exc.value)
        mock_delete.assert_not_called()


def test_create_cognito_user_username_exists(mock_client):
    mock_client.sign_up.side_effect = mock_client.exceptions.UsernameExistsException()

    with patch("voice_core.users.registration.cognito.delete_cognito_user", MagicMock()) as mock_delete:
        with pytest.raises(ValidationError) as exc:
            create_cognito_user("test@example.com", "Password123!", "Test User")

        assert "A user with this email already exists" in str(exc.value)
        mock_delete.assert_not_called()


@patch("voice_core.users.registration.cognito.client")
@patch("time.sleep", return_value=None)
def test_create_cognito_user_confirm_with_retries_success(mock_sleep, mock_client):
    mock_client.sign_up.return_value = {"UserSub": "12345"}
    mock_client.admin_confirm_sign_up.side_effect = [
        ClientError({"Error": {"Message": "Confirm failed"}}, "AdminConfirmSignUp"),
        ClientError({"Error": {"Message": "Confirm failed"}}, "AdminConfirmSignUp"),
        {},
    ]

    user_sub = create_cognito_user("test@example.com", "ValidPassw0rd!", "Test User")

    assert user_sub == "12345"
    mock_client.sign_up.assert_called_once()
    assert mock_client.admin_confirm_sign_up.call_count == 3
    assert mock_sleep.call_count == 2


@patch("voice_core.users.registration.cognito.client")
def test_delete_cognito_user_success(mock_client):
    mock_client.admin_get_user.return_value = {"Username": "test@example.com"}
    mock_client.admin_delete_user.return_value = {}

    result = delete_cognito_user("test@example.com")

    assert result is True
    mock_client.admin_get_user.assert_called_once()
    mock_client.admin_delete_user.assert_called_once()


def test_create_cognito_user_generic_client_error(mock_client):
    mock_client.sign_up.side_effect = ClientError(
        {"Error": {"Message": "Something went wrong"}}, "SignUp"
    )
    with patch("voice_core.users.registration.cognito.delete_cognito_user", MagicMock()) as mock_delete:
        with pytest.raises(Exception) as exc:
            create_cognito_user("test@example.com", "Password123!", "Test User")
        assert "Failed to create Cognito user" in str(exc.value), str(exc.value)
        mock_delete.assert_not_called()


@patch("voice_core.users.registration.cognito.client")
@patch("time.sleep", return_value=None)
def test_create_cognito_user_confirm_failure_with_cleanup(mock_sleep, mock_client):

    mock_client.sign_up.return_value = {"UserSub": "12345"}
    mock_client.admin_confirm_sign_up.side_effect = ClientError(
        {"Error": {"Message": "Confirmation failed"}}, "AdminConfirmSignUp"
    )
    with patch("voice_core.users.registration.cognito.delete_cognito_user", MagicMock()) as mock_delete:
        with pytest.raises(Exception) as exc:
            create_cognito_user("test@example.com", "ValidPassw0rd!", "Test User")
        assert "Failed to confirm Cognito user" in str(exc.value), str(exc.value)
        mock_client.sign_up.assert_called_once()
        assert mock_client.admin_confirm_sign_up.call_count == 10
        mock_delete.assert_called_once_with("test@example.com")
        assert mock_sleep.call_count == 9


@patch("voice_core.users.registration.cognito.client")
def test_delete_cognito_user_not_found(mock_client):
    # Raise the correct exception instance
    mock_client.admin_get_user.side_effect = MockUserNotFoundException()
    mock_client.admin_delete_user.reset_mock()
    result = delete_cognito_user("test@example.com")
    assert result is True
    mock_client.admin_get_user.assert_called_once()
    assert mock_client.admin_delete_user.call_count == 0, f"admin_delete_user called {mock_client.admin_delete_user.call_count} times"
