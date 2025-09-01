import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from rest_framework.exceptions import ValidationError

from voice_core.services.voicemail.assign_voicemail import (
    _rollback_voicemail_assignment,
    assign_voicemail,
)


class DummyTenant:
    def __init__(self, wazo_tenant_uuid="tenant-uuid-123"):
        self.id = 1
        self.name = "Test Tenant"
        self.wazo_tenant_uuid = wazo_tenant_uuid


class DummyUser:
    def __init__(self, wazo_user_id="user-uuid-123"):
        self.id = 2
        self.name = "John Doe"
        self.email = "john@example.com"
        self.wazo_user_id = wazo_user_id
        
        class _Config:
            def __init__(self):
                self.extension_enabled = False
                self.voicemail_enabled = False
            
            def save(self):
                pass
        
        self.config = _Config()


class DummyExtensionAssignment:
    def __init__(self):
        self.extension = 1001
        self.context_name = "default"


class TestRollbackVoicemailAssignment:
    def test_rollback_early_return_missing_admin_token(self):
        user = DummyUser()
        # Should return early without doing anything
        _rollback_voicemail_assignment(
            user=user,
            admin_token=None,
            tenant_uuid="tenant-uuid",
            user_uuid="user-uuid",
            voicemail_id=123,
        )
        # No assertions needed - function should complete without error

    def test_rollback_early_return_missing_tenant_uuid(self):
        user = DummyUser()
        _rollback_voicemail_assignment(
            user=user,
            admin_token="admin-token",
            tenant_uuid=None,
            user_uuid="user-uuid",
            voicemail_id=123,
        )

    def test_rollback_early_return_missing_voicemail_id(self):
        user = DummyUser()
        _rollback_voicemail_assignment(
            user=user,
            admin_token="admin-token",
            tenant_uuid="tenant-uuid",
            user_uuid="user-uuid",
            voicemail_id=None,
        )

    def test_rollback_early_return_missing_user_uuid(self):
        user = DummyUser()
        _rollback_voicemail_assignment(
            user=user,
            admin_token="admin-token",
            tenant_uuid="tenant-uuid",
            user_uuid=None,
            voicemail_id=123,
        )

    @patch("voice_core.services.voicemail.assign_voicemail.delete_voicemail")
    @patch("voice_core.services.voicemail.assign_voicemail.deassociate_user_with_voicemail")
    def test_rollback_successful_deassociation_and_deletion(self, mock_deassociate, mock_delete):
        mock_deassociate.return_value = True
        mock_delete.return_value = True
        
        user = DummyUser()
        _rollback_voicemail_assignment(
            user=user,
            admin_token="admin-token",
            tenant_uuid="tenant-uuid",
            user_uuid="user-uuid",
            voicemail_id=123,
        )
        
        mock_deassociate.assert_called_once_with("admin-token", "tenant-uuid", "user-uuid")
        mock_delete.assert_called_once_with("admin-token", "tenant-uuid", 123)

    @patch("voice_core.services.voicemail.assign_voicemail.delete_voicemail")
    @patch("voice_core.services.voicemail.assign_voicemail.deassociate_user_with_voicemail")
    def test_rollback_failed_deassociation(self, mock_deassociate, mock_delete):
        mock_deassociate.return_value = False
        
        user = DummyUser()
        _rollback_voicemail_assignment(
            user=user,
            admin_token="admin-token",
            tenant_uuid="tenant-uuid",
            user_uuid="user-uuid",
            voicemail_id=123,
        )
        
        mock_deassociate.assert_called_once_with("admin-token", "tenant-uuid", "user-uuid")
        mock_delete.assert_not_called()  # Should not delete if deassociation failed

    @patch("voice_core.services.voicemail.assign_voicemail.delete_voicemail")
    @patch("voice_core.services.voicemail.assign_voicemail.deassociate_user_with_voicemail")
    def test_rollback_successful_deassociation_failed_deletion(self, mock_deassociate, mock_delete):
        mock_deassociate.return_value = True
        mock_delete.return_value = False
        
        user = DummyUser()
        _rollback_voicemail_assignment(
            user=user,
            admin_token="admin-token",
            tenant_uuid="tenant-uuid",
            user_uuid="user-uuid",
            voicemail_id=123,
        )
        
        mock_deassociate.assert_called_once()
        mock_delete.assert_called_once()

    @patch("voice_core.services.voicemail.assign_voicemail.delete_voicemail")
    @patch("voice_core.services.voicemail.assign_voicemail.deassociate_user_with_voicemail")
    def test_rollback_exception_in_wazo_operations(self, mock_deassociate, mock_delete):
        mock_deassociate.side_effect = Exception("Wazo API error")
        
        user = DummyUser()
        # Should not raise exception, just log it
        _rollback_voicemail_assignment(
            user=user,
            admin_token="admin-token",
            tenant_uuid="tenant-uuid",
            user_uuid="user-uuid",
            voicemail_id=123,
        )

    @patch("voice_core.services.voicemail.assign_voicemail.VoicemailAssignment")
    def test_rollback_database_cleanup_success(self, mock_voicemail_assignment):
        mock_queryset = MagicMock()
        mock_voicemail_assignment.objects.filter.return_value = mock_queryset
        
        user = DummyUser()
        _rollback_voicemail_assignment(
            user=user,
            admin_token="admin-token",
            tenant_uuid="tenant-uuid",
            user_uuid="user-uuid",
            voicemail_id=123,
        )
        
        mock_voicemail_assignment.objects.filter.assert_called_once_with(
            user=user,
            voicemail_id=123
        )
        mock_queryset.delete.assert_called_once()

    @patch("voice_core.services.voicemail.assign_voicemail.VoicemailAssignment")
    def test_rollback_database_cleanup_exception(self, mock_voicemail_assignment):
        mock_voicemail_assignment.objects.filter.side_effect = Exception("Database error")
        
        user = DummyUser()
        # Should not raise exception, just log it
        _rollback_voicemail_assignment(
            user=user,
            admin_token="admin-token",
            tenant_uuid="tenant-uuid",
            user_uuid="user-uuid",
            voicemail_id=123,
        )

    def test_rollback_user_config_reset_success(self):
        user = DummyUser()
        user.config.extension_enabled = True
        user.config.voicemail_enabled = True
        
        _rollback_voicemail_assignment(
            user=user,
            admin_token="admin-token",
            tenant_uuid="tenant-uuid",
            user_uuid="user-uuid",
            voicemail_id=123,
        )
        
        assert user.config.extension_enabled is False
        assert user.config.voicemail_enabled is False

    def test_rollback_user_config_reset_exception(self):
        user = DummyUser()
        user.config.save = MagicMock(side_effect=Exception("Config save error"))
        
        # Should not raise exception, just log it
        _rollback_voicemail_assignment(
            user=user,
            admin_token="admin-token",
            tenant_uuid="tenant-uuid",
            user_uuid="user-uuid",
            voicemail_id=123,
        )


class TestAssignVoicemail:
    @patch("voice_core.services.voicemail.assign_voicemail.VoicemailAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.ExtensionAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.create_user_voicemail")
    @patch("voice_core.services.voicemail.assign_voicemail.get_wazo_admin_token")
    def test_assign_voicemail_success(self, mock_get_token, mock_create_voicemail, mock_ext_assignment, mock_vm_assignment):
        # Setup mocks
        mock_get_token.return_value = "admin-token-123"
        mock_create_voicemail.return_value = (456, 1234, True)  # voicemail_id, pin, enabled
        
        # Mock extension assignment exists
        extension_assignment = DummyExtensionAssignment()
        mock_ext_assignment.objects.get.return_value = extension_assignment
        
        # Mock voicemail assignment doesn't exist
        mock_vm_assignment.objects.filter.return_value.exists.return_value = False
        
        # Mock voicemail assignment creation
        assignment_instance = MagicMock()
        mock_vm_assignment.objects.create.return_value = assignment_instance
        
        # Setup test data
        tenant = DummyTenant()
        user = DummyUser()
        voicemail_pin = 1234
        voicemail_max_messages = 20
        
        # Execute
        result = assign_voicemail(tenant, user, voicemail_pin, voicemail_max_messages)
        
        # Assertions
        assert result == assignment_instance
        assert user.config.voicemail_enabled is True
        
        # Verify calls
        mock_get_token.assert_called_once()
        mock_ext_assignment.objects.get.assert_called_once_with(user=user)
        mock_vm_assignment.objects.filter.assert_called_once_with(user=user)
        
        mock_create_voicemail.assert_called_once_with(
            wazo_user_id=str(user.wazo_user_id),
            tenant_uuid=str(tenant.wazo_tenant_uuid),
            admin_token="admin-token-123",
            context_name=extension_assignment.context_name,
            email=user.email,
            extension_number=str(extension_assignment.extension),
            pin=voicemail_pin,
            name=user.name,
            max_messages=voicemail_max_messages,
        )
        
        mock_vm_assignment.objects.create.assert_called_once_with(
            voicemail_id=456,
            voicemail_pin=1234,
            user=user,
        )

    @patch("voice_core.services.voicemail.assign_voicemail.VoicemailAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.ExtensionAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.create_user_voicemail")
    @patch("voice_core.services.voicemail.assign_voicemail.get_wazo_admin_token")
    def test_assign_voicemail_success_disabled_voicemail(self, mock_get_token, mock_create_voicemail, mock_ext_assignment, mock_vm_assignment):
        # Setup mocks for disabled voicemail
        mock_get_token.return_value = "admin-token-123"
        mock_create_voicemail.return_value = (456, 1234, False)  # enabled=False
        
        extension_assignment = DummyExtensionAssignment()
        mock_ext_assignment.objects.get.return_value = extension_assignment
        mock_vm_assignment.objects.filter.return_value.exists.return_value = False
        
        tenant = DummyTenant()
        user = DummyUser()
        
        result = assign_voicemail(tenant, user, 1234, 10)
        
        # Should return None when voicemail is disabled
        assert result is None
        assert user.config.voicemail_enabled is False  # Should remain False
        mock_vm_assignment.objects.create.assert_not_called()

    @patch("voice_core.services.voicemail.assign_voicemail.VoicemailAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.ExtensionAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.create_user_voicemail")
    @patch("voice_core.services.voicemail.assign_voicemail.get_wazo_admin_token")
    def test_assign_voicemail_default_max_messages(self, mock_get_token, mock_create_voicemail, mock_ext_assignment, mock_vm_assignment):
        mock_get_token.return_value = "admin-token-123"
        mock_create_voicemail.return_value = (456, 1234, True)
        
        extension_assignment = DummyExtensionAssignment()
        mock_ext_assignment.objects.get.return_value = extension_assignment
        mock_vm_assignment.objects.filter.return_value.exists.return_value = False
        mock_vm_assignment.objects.create.return_value = MagicMock()
        
        tenant = DummyTenant()
        user = DummyUser()
        
        # Test with None max_messages
        assign_voicemail(tenant, user, 1234, None)
        
        # Should use default of 10
        mock_create_voicemail.assert_called_once()
        call_args = mock_create_voicemail.call_args[1]
        assert call_args['max_messages'] == 10

    @patch("voice_core.services.voicemail.assign_voicemail.get_wazo_admin_token")
    def test_assign_voicemail_missing_tenant_uuid(self, mock_get_token):
        mock_get_token.return_value = "admin-token-123"
        
        tenant = DummyTenant(wazo_tenant_uuid=None)
        user = DummyUser()
        
        with pytest.raises(ValueError, match="Tenant is missing wazo_tenant_uuid"):
            assign_voicemail(tenant, user, 1234, 10)

    @patch("voice_core.services.voicemail.assign_voicemail.ExtensionAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.get_wazo_admin_token")
    def test_assign_voicemail_no_extension_assigned(self, mock_get_token, mock_ext_assignment):
        mock_get_token.return_value = "admin-token-123"
        # Properly create the DoesNotExist exception class
        mock_ext_assignment.DoesNotExist = type("DoesNotExist", (Exception,), {})
        mock_ext_assignment.objects.get.side_effect = mock_ext_assignment.DoesNotExist
        
        tenant = DummyTenant()
        user = DummyUser()
        
        with pytest.raises(ValidationError, match="User does not have an extension assigned"):
            assign_voicemail(tenant, user, 1234, 10)

    @patch("voice_core.services.voicemail.assign_voicemail.VoicemailAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.ExtensionAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.get_wazo_admin_token")
    def test_assign_voicemail_already_has_voicemail(self, mock_get_token, mock_ext_assignment, mock_vm_assignment):
        mock_get_token.return_value = "admin-token-123"
        mock_ext_assignment.objects.get.return_value = DummyExtensionAssignment()
        mock_vm_assignment.objects.filter.return_value.exists.return_value = True
        
        tenant = DummyTenant()
        user = DummyUser()
        
        with pytest.raises(ValidationError, match="User already has a voicemail assigned"):
            assign_voicemail(tenant, user, 1234, 10)

    @patch("voice_core.services.voicemail.assign_voicemail._rollback_voicemail_assignment")
    @patch("voice_core.services.voicemail.assign_voicemail.VoicemailAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.ExtensionAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.create_user_voicemail")
    @patch("voice_core.services.voicemail.assign_voicemail.get_wazo_admin_token")
    def test_assign_voicemail_create_voicemail_fails(self, mock_get_token, mock_create_voicemail, mock_ext_assignment, mock_vm_assignment, mock_rollback):
        mock_get_token.return_value = "admin-token-123"
        mock_ext_assignment.objects.get.return_value = DummyExtensionAssignment()
        mock_vm_assignment.objects.filter.return_value.exists.return_value = False
        mock_create_voicemail.side_effect = Exception("Wazo API error")
        
        tenant = DummyTenant()
        user = DummyUser()
        
        with pytest.raises(Exception, match="Wazo API error"):
            assign_voicemail(tenant, user, 1234, 10)
        
        # Should trigger rollback
        mock_rollback.assert_called_once_with(
            user=user,
            admin_token="admin-token-123",
            tenant_uuid=str(tenant.wazo_tenant_uuid),
            user_uuid=None,  # user_uuid not set when create_user_voicemail fails
            voicemail_id=None,  # voicemail_id not set when create_user_voicemail fails
        )

    @patch("voice_core.services.voicemail.assign_voicemail._rollback_voicemail_assignment")
    @patch("voice_core.services.voicemail.assign_voicemail.VoicemailAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.ExtensionAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.create_user_voicemail")
    @patch("voice_core.services.voicemail.assign_voicemail.get_wazo_admin_token")
    def test_assign_voicemail_database_save_fails(self, mock_get_token, mock_create_voicemail, mock_ext_assignment, mock_vm_assignment, mock_rollback):
        mock_get_token.return_value = "admin-token-123"
        mock_create_voicemail.return_value = (456, 1234, True)
        mock_ext_assignment.objects.get.return_value = DummyExtensionAssignment()
        mock_vm_assignment.objects.filter.return_value.exists.return_value = False
        mock_vm_assignment.objects.create.side_effect = Exception("Database error")
        
        tenant = DummyTenant()
        user = DummyUser()
        
        with pytest.raises(Exception, match="Database error"):
            assign_voicemail(tenant, user, 1234, 10)
        
        # Should trigger rollback with voicemail_id set
        mock_rollback.assert_called_once_with(
            user=user,
            admin_token="admin-token-123",
            tenant_uuid=str(tenant.wazo_tenant_uuid),
            user_uuid=None,
            voicemail_id=456,
        )

    @patch("voice_core.services.voicemail.assign_voicemail._rollback_voicemail_assignment")
    @patch("voice_core.services.voicemail.assign_voicemail.VoicemailAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.ExtensionAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.create_user_voicemail")
    @patch("voice_core.services.voicemail.assign_voicemail.get_wazo_admin_token")
    def test_assign_voicemail_rollback_fails(self, mock_get_token, mock_create_voicemail, mock_ext_assignment, mock_vm_assignment, mock_rollback):
        mock_get_token.return_value = "admin-token-123"
        mock_create_voicemail.side_effect = Exception("Wazo API error")
        mock_ext_assignment.objects.get.return_value = DummyExtensionAssignment()
        mock_vm_assignment.objects.filter.return_value.exists.return_value = False
        mock_rollback.side_effect = Exception("Rollback error")
        
        tenant = DummyTenant()
        user = DummyUser()
        
        # Should still raise the original exception, not the rollback exception
        with pytest.raises(Exception, match="Wazo API error"):
            assign_voicemail(tenant, user, 1234, 10)

    @patch("voice_core.services.voicemail.assign_voicemail.datetime")
    @patch("voice_core.services.voicemail.assign_voicemail.VoicemailAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.ExtensionAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.create_user_voicemail")
    @patch("voice_core.services.voicemail.assign_voicemail.get_wazo_admin_token")
    def test_assign_voicemail_timing_logs(self, mock_get_token, mock_create_voicemail, mock_ext_assignment, mock_vm_assignment, mock_datetime):
        # Setup timing mocks
        start_time = datetime(2023, 1, 1, 12, 0, 0)
        middle_time = datetime(2023, 1, 1, 12, 0, 1)  # 1 second later
        end_time = datetime(2023, 1, 1, 12, 0, 2)     # 2 seconds later
        
        mock_datetime.now.side_effect = [start_time, middle_time, end_time]
        
        # Setup other mocks
        mock_get_token.return_value = "admin-token-123"
        mock_create_voicemail.return_value = (456, 1234, True)
        mock_ext_assignment.objects.get.return_value = DummyExtensionAssignment()
        mock_vm_assignment.objects.filter.return_value.exists.return_value = False
        mock_vm_assignment.objects.create.return_value = MagicMock()
        
        tenant = DummyTenant()
        user = DummyUser()
        
        assign_voicemail(tenant, user, 1234, 10)
        
        # Verify datetime.now() was called for timing
        assert mock_datetime.now.call_count == 3


class TestIntegrationScenarios:
    """Test scenarios that combine multiple aspects or edge cases."""
    
    @patch("voice_core.services.voicemail.assign_voicemail.VoicemailAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.ExtensionAssignment")
    @patch("voice_core.services.voicemail.assign_voicemail.create_user_voicemail")
    @patch("voice_core.services.voicemail.assign_voicemail.get_wazo_admin_token")
    def test_assign_voicemail_complete_workflow(self, mock_get_token, mock_create_voicemail, mock_ext_assignment, mock_vm_assignment):
        """Test the complete successful workflow from start to finish."""
        # Setup all mocks for success
        mock_get_token.return_value = "admin-token-123"
        mock_create_voicemail.return_value = (789, 5678, True)
        
        extension_assignment = DummyExtensionAssignment()
        extension_assignment.extension = 2001
        extension_assignment.context_name = "internal"
        mock_ext_assignment.objects.get.return_value = extension_assignment
        
        mock_vm_assignment.objects.filter.return_value.exists.return_value = False
        assignment_instance = MagicMock()
        assignment_instance.voicemail_id = 789
        assignment_instance.voicemail_pin = 5678
        mock_vm_assignment.objects.create.return_value = assignment_instance
        
        # Setup test data
        tenant = DummyTenant("tenant-uuid-456")
        user = DummyUser("user-uuid-789")
        user.name = "Jane Smith"
        user.email = "jane@example.com"
        
        # Execute
        result = assign_voicemail(tenant, user, 9999, 25)
        
        # Comprehensive assertions
        assert result == assignment_instance
        assert user.config.voicemail_enabled is True
        
        # Verify all the calls with exact parameters
        mock_get_token.assert_called_once()
        mock_ext_assignment.objects.get.assert_called_once_with(user=user)
        mock_vm_assignment.objects.filter.assert_called_once_with(user=user)
        
        mock_create_voicemail.assert_called_once_with(
            wazo_user_id="user-uuid-789",
            tenant_uuid="tenant-uuid-456",
            admin_token="admin-token-123",
            context_name="internal",
            email="jane@example.com",
            extension_number="2001",
            pin=9999,
            name="Jane Smith",
            max_messages=25,
        )
        
        mock_vm_assignment.objects.create.assert_called_once_with(
            voicemail_id=789,
            voicemail_pin=5678,  # Note: uses pin returned from create_user_voicemail
            user=user,
        )

    def test_error_handling_consistency(self):
        """Test that error handling is consistent across different failure scenarios."""
        tenant = DummyTenant()
        user = DummyUser()
        
        # Test with invalid inputs - should raise appropriate exceptions
        with pytest.raises(ValueError):
            assign_voicemail(DummyTenant(wazo_tenant_uuid=None), user, 1234, 10)