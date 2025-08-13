import logging
from unittest import mock
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.db.models.manager import EmptyManager
from rest_framework.exceptions import APIException

from voice_core.users.managers import UserManager
from voice_core.users.models import User


class MockUser:
    """A mock Django User model for testing the manager."""
    pk = 1
    wazo_user_id = None
    wazo_username = None
    wazo_provisioned_at = None
    
    def __init__(self, email, **kwargs):
        self.email = email
        self.__dict__.update(kwargs)
        self.save = MagicMock()
        self.delete = MagicMock()
        self.refresh_from_db = MagicMock()
    
    def __eq__(self, other):
        return self.email == other.email

    @property
    def name(self):
        return self.first_name if hasattr(self, 'first_name') else ''
    
    _meta = MagicMock()
  
def raise_custom_drf_exception(status_code, detail):
    """Mock a custom DRF exception for testing."""
    return APIException(detail=detail, code=status_code)

@patch('voice_core.custom_error_exception.raise_custom_drf_exception', new=raise_custom_drf_exception)
class UserManagerTests(TestCase):
    """Test suite for the custom UserManager."""

    def setUp(self):
        self.user_manager = UserManager()
        self.user_manager.model = MockUser 
        self.user_data = {
            "email": "testuser@example.com",
            "password": "testpassword123",
            "name": "Test User",
            "tenant": "example",
            "first_name": "Test",
        }
        
    @patch('voice_core.users.managers.create_cognito_user')
    @patch('voice_core.users.managers.get_wazo_admin_token')
    @patch('voice_core.users.managers.get_wazo_tenant_uuid')
    @patch('voice_core.users.managers.create_wazo_user')
    @patch('voice_core.users.managers.resolve_tenant_from_email', return_value='example')
    @patch('voice_core.users.managers.send_welcome_msg')
    def test_create_user_success(self, 
                                 mock_send_welcome_msg, 
                                 mock_resolve_tenant, 
                                 mock_create_wazo_user, 
                                 mock_get_wazo_tenant_uuid,
                                 mock_get_wazo_admin_token, 
                                 mock_create_cognito_user):
        """Test the full user creation path with all services succeeding."""
        
        mock_create_cognito_user.return_value = "mock_cognito_sub_123"
        mock_get_wazo_admin_token.return_value = "mock_admin_token"
        mock_get_wazo_tenant_uuid.return_value = "mock_tenant_uuid"
        mock_create_wazo_user.return_value = ["mock_wazo_user_id", "mock_wazo_username"]

        user = self.user_manager._create_user(**self.user_data)
        
        mock_create_cognito_user.assert_called_once_with(self.user_data['email'], self.user_data['password'], self.user_data['name'])
        mock_get_wazo_admin_token.assert_called_once()
        mock_get_wazo_tenant_uuid.assert_called_once_with(self.user_data['tenant'], "mock_admin_token")
        mock_create_wazo_user.assert_called_once_with(mock.ANY, "mock_admin_token", "mock_tenant_uuid")
        mock_send_welcome_msg.assert_called_once()
        
        self.assertEqual(user.email, self.user_data['email'])
        self.assertEqual(user.cognito_sub, "mock_cognito_sub_123")
        self.assertEqual(user.wazo_user_id, "mock_wazo_user_id")
        self.assertEqual(user.wazo_username, "mock_wazo_username")


    @patch('voice_core.users.managers.create_cognito_user', return_value=None)
    @patch.object(UserManager, '_rollback_on_failure')
    def test_create_user_cognito_failure(self, mock_rollback, mock_create_cognito_user):
        """Test failure during Cognito user creation."""
        with self.assertRaisesRegex(APIException, "Failed to create Cognito user"):
            self.user_manager._create_user(**self.user_data)
        
        mock_create_cognito_user.assert_called_once()
        mock_rollback.assert_not_called()


    @patch('voice_core.users.managers.create_cognito_user', return_value="mock_cognito_sub")
    @patch('voice_core.users.managers.get_wazo_admin_token', return_value=None)
    @patch.object(UserManager, '_rollback_on_failure')
    def test_create_user_wazo_token_failure_triggers_rollback(self, 
                                                             mock_rollback, 
                                                             mock_get_wazo_admin_token,
                                                             mock_create_cognito_user):
        """Test failure to get Wazo admin token, ensuring rollback is triggered."""
        with self.assertRaisesRegex(APIException, "Failed to get Wazo admin token"):
            self.user_manager._create_user(**self.user_data)
        
        mock_get_wazo_admin_token.assert_called_once()
        mock_rollback.assert_called_once()


    @patch('voice_core.users.managers.create_cognito_user', return_value="mock_cognito_sub")
    @patch('voice_core.users.managers.get_wazo_admin_token', return_value="mock_admin_token")
    @patch('voice_core.users.managers.get_wazo_tenant_uuid', return_value=None)
    @patch.object(UserManager, '_rollback_on_failure')
    def test_create_user_wazo_tenant_failure_triggers_rollback(self, 
                                                              mock_rollback, 
                                                              mock_get_wazo_tenant_uuid,
                                                              mock_get_wazo_admin_token,
                                                              mock_create_cognito_user):
        """Test failure to get Wazo tenant UUID, ensuring rollback is triggered."""
        with self.assertRaisesRegex(APIException, "Failed to get Wazo tenant UUID"):
            self.user_manager._create_user(**self.user_data)
        
        mock_get_wazo_tenant_uuid.assert_called_once()
        mock_rollback.assert_called_once()


    @patch('voice_core.users.managers.create_cognito_user', return_value="mock_cognito_sub")
    @patch('voice_core.users.managers.get_wazo_admin_token', return_value="mock_admin_token")
    @patch('voice_core.users.managers.get_wazo_tenant_uuid', return_value="mock_tenant_uuid")
    @patch('voice_core.users.managers.create_wazo_user', return_value=[None, None])
    @patch.object(UserManager, '_rollback_on_failure')
    def test_create_user_wazo_creation_failure_triggers_rollback(self, 
                                                                 mock_rollback, 
                                                                 mock_create_wazo_user,
                                                                 mock_get_wazo_tenant_uuid,
                                                                 mock_get_wazo_admin_token,
                                                                 mock_create_cognito_user):
        """Test failure to create the Wazo user, ensuring rollback is triggered."""
        with self.assertRaisesRegex(APIException, "Failed to create Wazo user"):
            self.user_manager._create_user(**self.user_data)
        
        mock_create_wazo_user.assert_called_once()
        mock_rollback.assert_called_once()
        

    @patch('voice_core.users.managers.delete_cognito_user')
    @patch('voice_core.users.managers.delete_wazo_user')
    def test_rollback_on_failure_deletes_from_all_services(self, mock_delete_wazo_user, mock_delete_cognito_user):
        """Test that the rollback function correctly cleans up all services."""
        mock_user = MockUser({
            "email": "testuser@example.com",
            "password": "testpassword123",
            "name": "Test User",
            "tenant": "example",
            "first_name": "Test",
        })
        
        self.user_manager._rollback_on_failure(
            email="testuser@example.com",
            cognito_sub="mock_cognito_sub",
            user=mock_user,
            wazo_user_uuid="mock_wazo_id",
            admin_token="mock_admin_token"
        )
        
        mock_user.delete.assert_called_once()
        mock_delete_cognito_user.assert_called_once_with("testuser@example.com")
        mock_delete_wazo_user.assert_called_once_with("mock_wazo_id", "mock_admin_token")


    def test_create_user_with_no_email_raises_value_error(self):
        """Test that a ValueError is raised if no email is provided."""
        user_data_no_email = self.user_data.copy()
        user_data_no_email['email'] = ""
        with self.assertRaisesRegex(ValueError, "The given email must be set"):
            self.user_manager._create_user(**user_data_no_email)


    def test_create_superuser_sets_fields_correctly(self):
        """Test that create_superuser sets is_staff and is_superuser to True."""
        mock_user = MagicMock()
        with patch.object(self.user_manager, '_create_user', return_value=mock_user) as mock_create_user:
            self.user_manager.create_superuser(**self.user_data)
            
            mock_create_user.assert_called_once()
            call_args, call_kwargs = mock_create_user.call_args
            self.assertTrue(call_kwargs['is_staff'])
            self.assertTrue(call_kwargs['is_superuser'])
