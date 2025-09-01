import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from rest_framework.exceptions import ValidationError

from voice_core.services.voicemail.update_voicemail import set_voicemail_as_read


class DummyTenant:
    def __init__(self, wazo_tenant_uuid="tenant-uuid-123"):
        self.id = 1
        self.name = "Test Tenant"
        self.wazo_tenant_uuid = wazo_tenant_uuid


class DummyUser:
    def __init__(self, user_id=2):
        self.id = user_id
        self.name = "John Doe"
        self.email = "john@example.com"
        self.wazo_user_id = "user-uuid-123"


class DummyVoicemailAssignment:
    def __init__(self, voicemail_id=123, user=None):
        self.voicemail_id = voicemail_id
        self.user = user
        self.voicemail_pin = 1234


class TestSetVoicemailAsRead:
    @patch("voice_core.services.voicemail.update_voicemail.update_voicemail_as_read")
    @patch("voice_core.services.voicemail.update_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.update_voicemail.VoicemailAssignment")
    def test_set_voicemail_as_read_success_default_folder(self, mock_vm_assignment, mock_get_token, mock_update_wazo):
        # Setup mocks
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        
        expected_result = {"status": "updated", "folder_id": 2}
        mock_update_wazo.return_value = expected_result
        
        # Setup test data
        tenant = DummyTenant()
        user = DummyUser()
        voicemail_id = 123
        message_id = "msg-456"
        
        # Execute
        result = set_voicemail_as_read(tenant, user, voicemail_id, message_id)
        
        # Assertions
        assert result == expected_result
        
        # Verify calls
        mock_get_token.assert_called_once()
        mock_vm_assignment.objects.get.assert_called_once_with(user=user, voicemail_id=voicemail_id)
        mock_update_wazo.assert_called_once_with(
            admin_token="admin-token-123",
            voicemail_id=voicemail_id,
            message_id=message_id,
            folder_id=2,  # Default folder
        )

    @patch("voice_core.services.voicemail.update_voicemail.update_voicemail_as_read")
    @patch("voice_core.services.voicemail.update_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.update_voicemail.VoicemailAssignment")
    def test_set_voicemail_as_read_success_custom_folder(self, mock_vm_assignment, mock_get_token, mock_update_wazo):
        # Setup mocks
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        
        expected_result = {"status": "updated", "folder_id": 1}
        mock_update_wazo.return_value = expected_result
        
        # Setup test data
        tenant = DummyTenant()
        user = DummyUser()
        voicemail_id = 123
        message_id = "msg-456"
        folder_id = 1  # Custom folder (inbox)
        
        # Execute
        result = set_voicemail_as_read(tenant, user, voicemail_id, message_id, folder_id)
        
        # Assertions
        assert result == expected_result
        
        # Verify calls
        mock_update_wazo.assert_called_once_with(
            admin_token="admin-token-123",
            voicemail_id=voicemail_id,
            message_id=message_id,
            folder_id=folder_id,  # Custom folder
        )

    @patch("voice_core.services.voicemail.update_voicemail.VoicemailAssignment")
    def test_set_voicemail_as_read_missing_tenant_uuid(self, mock_vm_assignment):
        tenant = DummyTenant(wazo_tenant_uuid=None)
        user = DummyUser()
        
        with pytest.raises(ValidationError, match="Tenant is missing wazo_tenant_uuid"):
            set_voicemail_as_read(tenant, user, 123, "msg-456")
        
        # Should not make any other calls
        mock_vm_assignment.objects.get.assert_not_called()

    @patch("voice_core.services.voicemail.update_voicemail.VoicemailAssignment")
    def test_set_voicemail_as_read_voicemail_not_assigned(self, mock_vm_assignment):
        # Setup DoesNotExist exception properly
        mock_vm_assignment.DoesNotExist = type("DoesNotExist", (Exception,), {})
        mock_vm_assignment.objects.get.side_effect = mock_vm_assignment.DoesNotExist
        
        tenant = DummyTenant()
        user = DummyUser()
        
        with pytest.raises(ValidationError, match="Voicemail not assigned to this user"):
            set_voicemail_as_read(tenant, user, 123, "msg-456")
        
        mock_vm_assignment.objects.get.assert_called_once_with(user=user, voicemail_id=123)

    @patch("voice_core.services.voicemail.update_voicemail.update_voicemail_as_read")
    @patch("voice_core.services.voicemail.update_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.update_voicemail.VoicemailAssignment")
    def test_set_voicemail_as_read_wazo_api_failure(self, mock_vm_assignment, mock_get_token, mock_update_wazo):
        # Setup mocks
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_update_wazo.side_effect = Exception("Wazo API error")
        
        tenant = DummyTenant()
        user = DummyUser()
        
        with pytest.raises(Exception, match="Wazo API error"):
            set_voicemail_as_read(tenant, user, 123, "msg-456")
        
        # Verify calls were made before the error
        mock_get_token.assert_called_once()
        mock_vm_assignment.objects.get.assert_called_once()
        mock_update_wazo.assert_called_once()

    @patch("voice_core.services.voicemail.update_voicemail.update_voicemail_as_read")
    @patch("voice_core.services.voicemail.update_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.update_voicemail.VoicemailAssignment")
    def test_set_voicemail_as_read_get_token_failure(self, mock_vm_assignment, mock_get_token, mock_update_wazo):
        # Setup mocks
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_get_token.side_effect = Exception("Token retrieval failed")
        
        tenant = DummyTenant()
        user = DummyUser()
        
        with pytest.raises(Exception, match="Token retrieval failed"):
            set_voicemail_as_read(tenant, user, 123, "msg-456")
        
        # Verify assignment check was done before token retrieval
        mock_vm_assignment.objects.get.assert_called_once()
        mock_get_token.assert_called_once()
        mock_update_wazo.assert_not_called()

    @patch("voice_core.services.voicemail.update_voicemail.datetime")
    @patch("voice_core.services.voicemail.update_voicemail.update_voicemail_as_read")
    @patch("voice_core.services.voicemail.update_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.update_voicemail.VoicemailAssignment")
    def test_set_voicemail_as_read_timing_logs(self, mock_vm_assignment, mock_get_token, mock_update_wazo, mock_datetime):
        # Setup timing mocks
        start_time = datetime(2023, 1, 1, 12, 0, 0)
        end_time = datetime(2023, 1, 1, 12, 0, 1)  # 1 second later
        mock_datetime.now.side_effect = [start_time, end_time]
        
        # Setup other mocks
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_update_wazo.return_value = {"status": "success"}
        
        tenant = DummyTenant()
        user = DummyUser()
        
        result = set_voicemail_as_read(tenant, user, 123, "msg-456")
        
        # Verify timing calls
        assert mock_datetime.now.call_count == 2
        assert result == {"status": "success"}

    @patch("voice_core.services.voicemail.update_voicemail.update_voicemail_as_read")
    @patch("voice_core.services.voicemail.update_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.update_voicemail.VoicemailAssignment")
    def test_set_voicemail_as_read_return_none_from_wazo(self, mock_vm_assignment, mock_get_token, mock_update_wazo):
        # Setup mocks - Wazo API returns None
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_update_wazo.return_value = None
        
        tenant = DummyTenant()
        user = DummyUser()
        
        result = set_voicemail_as_read(tenant, user, 123, "msg-456")
        
        # Should return None if Wazo API returns None
        assert result is None

    @patch("voice_core.services.voicemail.update_voicemail.update_voicemail_as_read")
    @patch("voice_core.services.voicemail.update_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.update_voicemail.VoicemailAssignment")
    def test_set_voicemail_as_read_empty_dict_from_wazo(self, mock_vm_assignment, mock_get_token, mock_update_wazo):
        # Setup mocks - Wazo API returns empty dict
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_update_wazo.return_value = {}
        
        tenant = DummyTenant()
        user = DummyUser()
        
        result = set_voicemail_as_read(tenant, user, 123, "msg-456")
        
        # Should return empty dict if Wazo API returns empty dict
        assert result == {}

    @patch("voice_core.services.voicemail.update_voicemail.update_voicemail_as_read")
    @patch("voice_core.services.voicemail.update_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.update_voicemail.VoicemailAssignment")
    def test_set_voicemail_as_read_different_voicemail_ids(self, mock_vm_assignment, mock_get_token, mock_update_wazo):
        # Test with different voicemail IDs to ensure proper parameter passing
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_update_wazo.return_value = {"status": "updated"}
        
        tenant = DummyTenant()
        user = DummyUser()
        
        # Test with different voicemail ID
        voicemail_id = 999
        message_id = "msg-xyz"
        folder_id = 3
        
        result = set_voicemail_as_read(tenant, user, voicemail_id, message_id, folder_id)
        
        # Verify correct parameters were passed
        mock_vm_assignment.objects.get.assert_called_once_with(user=user, voicemail_id=voicemail_id)
        mock_update_wazo.assert_called_once_with(
            admin_token="admin-token-123",
            voicemail_id=voicemail_id,
            message_id=message_id,
            folder_id=folder_id,
        )

    @patch("voice_core.services.voicemail.update_voicemail.update_voicemail_as_read")
    @patch("voice_core.services.voicemail.update_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.update_voicemail.VoicemailAssignment")
    def test_set_voicemail_as_read_different_users(self, mock_vm_assignment, mock_get_token, mock_update_wazo):
        # Test with different users to ensure proper validation
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_update_wazo.return_value = {"status": "updated"}
        
        tenant = DummyTenant()
        user1 = DummyUser(user_id=1)
        user2 = DummyUser(user_id=2)
        
        # Test with first user
        set_voicemail_as_read(tenant, user1, 123, "msg-456")
        mock_vm_assignment.objects.get.assert_called_with(user=user1, voicemail_id=123)
        
        # Reset mock and test with second user
        mock_vm_assignment.objects.get.reset_mock()
        set_voicemail_as_read(tenant, user2, 123, "msg-456")
        mock_vm_assignment.objects.get.assert_called_with(user=user2, voicemail_id=123)


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    @patch("voice_core.services.voicemail.update_voicemail.update_voicemail_as_read")
    @patch("voice_core.services.voicemail.update_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.update_voicemail.VoicemailAssignment")
    def test_user_without_id_attribute(self, mock_vm_assignment, mock_get_token, mock_update_wazo):
        """Test error logging when user object doesn't have id attribute."""
        # Setup mocks to cause an error
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_update_wazo.side_effect = Exception("Wazo API error")
        
        # Create user without id attribute
        class UserWithoutId:
            name = "Test User"
        
        user = UserWithoutId()
        tenant = DummyTenant()
        
        # Just check that an exception is raised, don't match the specific message
        # since the getattr(user, 'id', 'unknown') handles missing id gracefully
        with pytest.raises(Exception):
            set_voicemail_as_read(tenant, user, 123, "msg-456")

    @patch("voice_core.services.voicemail.update_voicemail.update_voicemail_as_read")
    @patch("voice_core.services.voicemail.update_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.update_voicemail.VoicemailAssignment")
    def test_zero_voicemail_id(self, mock_vm_assignment, mock_get_token, mock_update_wazo):
        """Test with voicemail_id of 0."""
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment(voicemail_id=0)
        mock_vm_assignment.objects.get.return_value = assignment
        mock_update_wazo.return_value = {"status": "updated"}
        
        tenant = DummyTenant()
        user = DummyUser()
        
        result = set_voicemail_as_read(tenant, user, 0, "msg-456")
        
        assert result == {"status": "updated"}
        mock_update_wazo.assert_called_once_with(
            admin_token="admin-token-123",
            voicemail_id=0,
            message_id="msg-456",
            folder_id=2,
        )

    @patch("voice_core.services.voicemail.update_voicemail.update_voicemail_as_read")
    @patch("voice_core.services.voicemail.update_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.update_voicemail.VoicemailAssignment")
    def test_empty_message_id(self, mock_vm_assignment, mock_get_token, mock_update_wazo):
        """Test with empty message_id."""
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_update_wazo.return_value = {"status": "updated"}
        
        tenant = DummyTenant()
        user = DummyUser()
        
        result = set_voicemail_as_read(tenant, user, 123, "")
        
        assert result == {"status": "updated"}
        mock_update_wazo.assert_called_once_with(
            admin_token="admin-token-123",
            voicemail_id=123,
            message_id="",
            folder_id=2,
        )

    @patch("voice_core.services.voicemail.update_voicemail.update_voicemail_as_read")
    @patch("voice_core.services.voicemail.update_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.update_voicemail.VoicemailAssignment")
    def test_negative_folder_id(self, mock_vm_assignment, mock_get_token, mock_update_wazo):
        """Test with negative folder_id."""
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_update_wazo.return_value = {"status": "updated"}
        
        tenant = DummyTenant()
        user = DummyUser()
        
        result = set_voicemail_as_read(tenant, user, 123, "msg-456", -1)
        
        assert result == {"status": "updated"}
        mock_update_wazo.assert_called_once_with(
            admin_token="admin-token-123",
            voicemail_id=123,
            message_id="msg-456",
            folder_id=-1,
        )


class TestIntegrationScenarios:
    """Test integration scenarios that combine multiple aspects."""

    @patch("voice_core.services.voicemail.update_voicemail.datetime")
    @patch("voice_core.services.voicemail.update_voicemail.update_voicemail_as_read")
    @patch("voice_core.services.voicemail.update_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.update_voicemail.VoicemailAssignment")
    def test_complete_successful_workflow(self, mock_vm_assignment, mock_get_token, mock_update_wazo, mock_datetime):
        """Test the complete successful workflow from start to finish."""
        # Setup timing
        start_time = datetime(2023, 1, 1, 12, 0, 0)
        end_time = datetime(2023, 1, 1, 12, 0, 2)  # 2 seconds later
        mock_datetime.now.side_effect = [start_time, end_time]
        
        # Setup mocks
        mock_get_token.return_value = "admin-token-xyz"
        assignment = DummyVoicemailAssignment(voicemail_id=789)
        assignment.user = DummyUser(user_id=456)
        mock_vm_assignment.objects.get.return_value = assignment
        
        expected_result = {
            "status": "success",
            "message": "Voicemail moved to folder 1",
            "folder_id": 1
        }
        mock_update_wazo.return_value = expected_result
        
        # Setup test data
        tenant = DummyTenant("tenant-uuid-789")
        user = DummyUser(user_id=456)
        voicemail_id = 789
        message_id = "msg-abc123"
        folder_id = 1  # Inbox folder
        
        # Execute
        result = set_voicemail_as_read(tenant, user, voicemail_id, message_id, folder_id)
        
        # Comprehensive assertions
        assert result == expected_result
        
        # Verify all calls with exact parameters
        mock_vm_assignment.objects.get.assert_called_once_with(user=user, voicemail_id=voicemail_id)
        mock_get_token.assert_called_once()
        mock_update_wazo.assert_called_once_with(
            admin_token="admin-token-xyz",
            voicemail_id=voicemail_id,
            message_id=message_id,
            folder_id=folder_id,
        )
        
        # Verify timing calls
        assert mock_datetime.now.call_count == 2

    def test_parameter_validation_consistency(self):
        """Test that parameter validation is consistent across different scenarios."""
        tenant_no_uuid = DummyTenant(wazo_tenant_uuid=None)
        tenant_empty_uuid = DummyTenant(wazo_tenant_uuid="")
        user = DummyUser()
        
        # Both None and empty string should raise ValidationError
        with pytest.raises(ValidationError, match="Tenant is missing wazo_tenant_uuid"):
            set_voicemail_as_read(tenant_no_uuid, user, 123, "msg-456")
        
        with pytest.raises(ValidationError, match="Tenant is missing wazo_tenant_uuid"):
            set_voicemail_as_read(tenant_empty_uuid, user, 123, "msg-456")