import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from rest_framework.exceptions import ValidationError

from voice_core.services.voicemail.get_voicemail import (
    get_all_voicemails,
    get_voicemails_by_folder,
    get_voicemail_recording,
)


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


class TestGetAllVoicemails:
    @patch("voice_core.services.voicemail.get_voicemail.fetch_all_voicemail")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_all_voicemails_success(self, mock_vm_assignment, mock_get_token, mock_fetch_all):
        # Setup mocks
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        
        expected_voicemails = {
            "id": 123,
            "folders": [
                {"id": 1, "name": "inbox", "messages": [{"id": "msg1"}]},
                {"id": 2, "name": "old", "messages": [{"id": "msg2"}]},
            ]
        }
        mock_fetch_all.return_value = expected_voicemails
        
        # Setup test data
        tenant = DummyTenant()
        user = DummyUser()
        voicemail_id = 123
        
        # Execute
        result = get_all_voicemails(tenant, user, voicemail_id)
        
        # Assertions
        assert result == expected_voicemails
        
        # Verify calls
        mock_get_token.assert_called_once()
        mock_vm_assignment.objects.get.assert_called_once_with(user=user, voicemail_id=voicemail_id)
        mock_fetch_all.assert_called_once_with(
            voicemail_id=voicemail_id,
            admin_token="admin-token-123",
        )

    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_all_voicemails_missing_tenant_uuid(self, mock_vm_assignment):
        tenant = DummyTenant(wazo_tenant_uuid=None)
        user = DummyUser()
        
        with pytest.raises(ValidationError, match="Tenant is missing wazo_tenant_uuid"):
            get_all_voicemails(tenant, user, 123)
        
        # Should not make any other calls
        mock_vm_assignment.objects.get.assert_not_called()

    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_all_voicemails_voicemail_not_assigned(self, mock_vm_assignment):
        # Setup DoesNotExist exception properly
        mock_vm_assignment.DoesNotExist = type("DoesNotExist", (Exception,), {})
        mock_vm_assignment.objects.get.side_effect = mock_vm_assignment.DoesNotExist
        
        tenant = DummyTenant()
        user = DummyUser()
        
        with pytest.raises(ValidationError, match="Voicemail not assigned to this user"):
            get_all_voicemails(tenant, user, 123)
        
        mock_vm_assignment.objects.get.assert_called_once_with(user=user, voicemail_id=123)

    @patch("voice_core.services.voicemail.get_voicemail.fetch_all_voicemail")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_all_voicemails_returns_none_from_wazo(self, mock_vm_assignment, mock_get_token, mock_fetch_all):
        # Setup mocks
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_fetch_all.return_value = None
        
        tenant = DummyTenant()
        user = DummyUser()
        
        result = get_all_voicemails(tenant, user, 123)
        
        # Should return None if Wazo API returns None
        assert result is None

    @patch("voice_core.services.voicemail.get_voicemail.fetch_all_voicemail")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_all_voicemails_wazo_api_failure(self, mock_vm_assignment, mock_get_token, mock_fetch_all):
        # Setup mocks
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_fetch_all.side_effect = Exception("Wazo API error")
        
        tenant = DummyTenant()
        user = DummyUser()
        
        with pytest.raises(Exception, match="Wazo API error"):
            get_all_voicemails(tenant, user, 123)

    @patch("voice_core.services.voicemail.get_voicemail.fetch_all_voicemail")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_all_voicemails_get_token_failure(self, mock_vm_assignment, mock_get_token, mock_fetch_all):
        # Setup mocks
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_get_token.side_effect = Exception("Token retrieval failed")
        
        tenant = DummyTenant()
        user = DummyUser()
        
        with pytest.raises(Exception, match="Token retrieval failed"):
            get_all_voicemails(tenant, user, 123)
        
        mock_fetch_all.assert_not_called()

    @patch("voice_core.services.voicemail.get_voicemail.datetime")
    @patch("voice_core.services.voicemail.get_voicemail.fetch_all_voicemail")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_all_voicemails_timing_logs(self, mock_vm_assignment, mock_get_token, mock_fetch_all, mock_datetime):
        # Setup timing mocks
        start_time = datetime(2023, 1, 1, 12, 0, 0)
        end_time = datetime(2023, 1, 1, 12, 0, 2)  # 2 seconds later
        mock_datetime.now.side_effect = [start_time, end_time]
        
        # Setup other mocks
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_fetch_all.return_value = [{"id": "msg1"}, {"id": "msg2"}]  # 2 voicemails
        
        tenant = DummyTenant()
        user = DummyUser()
        
        result = get_all_voicemails(tenant, user, 123)
        
        # Verify timing calls
        assert mock_datetime.now.call_count == 2
        assert len(result) == 2


class TestGetVoicemailsByFolder:
    @patch("voice_core.services.voicemail.get_voicemail.fetch_voicemails_by_folder")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_voicemails_by_folder_success(self, mock_vm_assignment, mock_get_token, mock_fetch_by_folder):
        # Setup mocks
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        
        expected_recordings = {
            "id": 1,
            "name": "inbox",
            "messages": [
                {"id": "msg1", "caller_id": "123456789"},
                {"id": "msg2", "caller_id": "987654321"},
            ]
        }
        mock_fetch_by_folder.return_value = expected_recordings
        
        # Setup test data
        tenant = DummyTenant()
        user = DummyUser()
        voicemail_id = 123
        folder_id = 1
        
        # Execute
        result = get_voicemails_by_folder(tenant, user, voicemail_id, folder_id)
        
        # Assertions
        assert result == expected_recordings
        
        # Verify calls
        mock_get_token.assert_called_once()
        mock_vm_assignment.objects.get.assert_called_once_with(user=user, voicemail_id=voicemail_id)
        mock_fetch_by_folder.assert_called_once_with(
            voicemail_id=voicemail_id,
            folder_id=folder_id,
            admin_token="admin-token-123",
        )

    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_voicemails_by_folder_missing_tenant_uuid(self, mock_vm_assignment):
        tenant = DummyTenant(wazo_tenant_uuid=None)
        user = DummyUser()
        
        with pytest.raises(ValidationError, match="Tenant is missing wazo_tenant_uuid"):
            get_voicemails_by_folder(tenant, user, 123, 1)
        
        mock_vm_assignment.objects.get.assert_not_called()

    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_voicemails_by_folder_voicemail_not_assigned(self, mock_vm_assignment):
        # Setup DoesNotExist exception properly
        mock_vm_assignment.DoesNotExist = type("DoesNotExist", (Exception,), {})
        mock_vm_assignment.objects.get.side_effect = mock_vm_assignment.DoesNotExist
        
        tenant = DummyTenant()
        user = DummyUser()
        
        with pytest.raises(ValidationError, match="Voicemail not assigned to this user"):
            get_voicemails_by_folder(tenant, user, 123, 1)

    @patch("voice_core.services.voicemail.get_voicemail.fetch_voicemails_by_folder")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_voicemails_by_folder_returns_none_from_wazo(self, mock_vm_assignment, mock_get_token, mock_fetch_by_folder):
        # Setup mocks
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_fetch_by_folder.return_value = None
        
        tenant = DummyTenant()
        user = DummyUser()
        
        result = get_voicemails_by_folder(tenant, user, 123, 1)
        
        # Should return None if Wazo API returns None
        assert result is None

    @patch("voice_core.services.voicemail.get_voicemail.fetch_voicemails_by_folder")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_voicemails_by_folder_different_folders(self, mock_vm_assignment, mock_get_token, mock_fetch_by_folder):
        # Test with different folder IDs
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_fetch_by_folder.return_value = {"messages": []}
        
        tenant = DummyTenant()
        user = DummyUser()
        
        # Test different folder IDs
        for folder_id in [0, 1, 2, 3]:
            get_voicemails_by_folder(tenant, user, 123, folder_id)
            # Verify correct folder_id was passed
            mock_fetch_by_folder.assert_called_with(
                voicemail_id=123,
                folder_id=folder_id,
                admin_token="admin-token-123",
            )

    @patch("voice_core.services.voicemail.get_voicemail.datetime")
    @patch("voice_core.services.voicemail.get_voicemail.fetch_voicemails_by_folder")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_voicemails_by_folder_timing_logs(self, mock_vm_assignment, mock_get_token, mock_fetch_by_folder, mock_datetime):
        # Setup timing mocks
        start_time = datetime(2023, 1, 1, 12, 0, 0)
        end_time = datetime(2023, 1, 1, 12, 0, 1)  # 1 second later
        mock_datetime.now.side_effect = [start_time, end_time]
        
        # Setup other mocks
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_fetch_by_folder.return_value = [{"id": "msg1"}]  # 1 recording
        
        tenant = DummyTenant()
        user = DummyUser()
        
        result = get_voicemails_by_folder(tenant, user, 123, 1)
        
        # Verify timing calls
        assert mock_datetime.now.call_count == 2
        assert len(result) == 1


class TestGetVoicemailRecording:
    @patch("voice_core.services.voicemail.get_voicemail.fetch_voicemail_recording")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_voicemail_recording_success(self, mock_vm_assignment, mock_get_token, mock_fetch_recording):
        # Setup mocks
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        
        expected_content = b"fake audio data"
        expected_content_type = "audio/wav"
        mock_fetch_recording.return_value = (expected_content, expected_content_type)
        
        # Setup test data
        tenant = DummyTenant()
        user = DummyUser()
        voicemail_id = 123
        message_id = "msg-456"
        
        # Execute
        recording, content_type = get_voicemail_recording(tenant, user, voicemail_id, message_id)
        
        # Assertions
        assert recording == expected_content
        assert content_type == expected_content_type
        
        # Verify calls
        mock_get_token.assert_called_once()
        mock_vm_assignment.objects.get.assert_called_once_with(user=user, voicemail_id=voicemail_id)
        mock_fetch_recording.assert_called_once_with(
            voicemail_id=voicemail_id,
            message_id=message_id,
            admin_token="admin-token-123",
        )

    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_voicemail_recording_missing_tenant_uuid(self, mock_vm_assignment):
        tenant = DummyTenant(wazo_tenant_uuid=None)
        user = DummyUser()
        
        with pytest.raises(ValidationError, match="Tenant is missing wazo_tenant_uuid"):
            get_voicemail_recording(tenant, user, 123, "msg-456")
        
        mock_vm_assignment.objects.get.assert_not_called()

    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_voicemail_recording_voicemail_not_assigned(self, mock_vm_assignment):
        # Setup DoesNotExist exception properly
        mock_vm_assignment.DoesNotExist = type("DoesNotExist", (Exception,), {})
        mock_vm_assignment.objects.get.side_effect = mock_vm_assignment.DoesNotExist
        
        tenant = DummyTenant()
        user = DummyUser()
        
        with pytest.raises(ValidationError, match="Voicemail not assigned to this user"):
            get_voicemail_recording(tenant, user, 123, "msg-456")

    @patch("voice_core.services.voicemail.get_voicemail.fetch_voicemail_recording")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_voicemail_recording_returns_none_from_wazo(self, mock_vm_assignment, mock_get_token, mock_fetch_recording):
        # Setup mocks
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_fetch_recording.return_value = (None, None)
        
        tenant = DummyTenant()
        user = DummyUser()
        
        recording, content_type = get_voicemail_recording(tenant, user, 123, "msg-456")
        
        # Should return (None, None) if Wazo API returns (None, None)
        assert recording is None
        assert content_type is None

    @patch("voice_core.services.voicemail.get_voicemail.fetch_voicemail_recording")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_voicemail_recording_different_content_types(self, mock_vm_assignment, mock_get_token, mock_fetch_recording):
        # Test with different content types
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        
        tenant = DummyTenant()
        user = DummyUser()
        
        # Test different content types
        test_cases = [
            (b"wav data", "audio/wav"),
            (b"mp3 data", "audio/mpeg"),
            (b"ogg data", "audio/ogg"),
        ]
        
        for expected_content, expected_type in test_cases:
            mock_fetch_recording.return_value = (expected_content, expected_type)
            
            recording, content_type = get_voicemail_recording(tenant, user, 123, "msg-456")
            
            assert recording == expected_content
            assert content_type == expected_type

    @patch("voice_core.services.voicemail.get_voicemail.fetch_voicemail_recording")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_voicemail_recording_wazo_api_failure(self, mock_vm_assignment, mock_get_token, mock_fetch_recording):
        # Setup mocks
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_fetch_recording.side_effect = Exception("Wazo API error")
        
        tenant = DummyTenant()
        user = DummyUser()
        
        with pytest.raises(Exception, match="Wazo API error"):
            get_voicemail_recording(tenant, user, 123, "msg-456")

    @patch("voice_core.services.voicemail.get_voicemail.datetime")
    @patch("voice_core.services.voicemail.get_voicemail.fetch_voicemail_recording")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_get_voicemail_recording_timing_logs(self, mock_vm_assignment, mock_get_token, mock_fetch_recording, mock_datetime):
        # Setup timing mocks
        start_time = datetime(2023, 1, 1, 12, 0, 0)
        end_time = datetime(2023, 1, 1, 12, 0, 3)  # 3 seconds later
        mock_datetime.now.side_effect = [start_time, end_time]
        
        # Setup other mocks
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_fetch_recording.return_value = (b"audio data", "audio/wav")
        
        tenant = DummyTenant()
        user = DummyUser()
        
        recording, content_type = get_voicemail_recording(tenant, user, 123, "msg-456")
        
        # Verify timing calls
        assert mock_datetime.now.call_count == 2
        assert recording == b"audio data"
        assert content_type == "audio/wav"


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    @patch("voice_core.services.voicemail.get_voicemail.fetch_all_voicemail")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_user_without_id_attribute_get_all_voicemails(self, mock_vm_assignment, mock_get_token, mock_fetch_all):
        """Test error logging when user object doesn't have id attribute."""
        # Setup mocks to cause an error
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_fetch_all.side_effect = Exception("Wazo API error")
        
        # Create user without id attribute
        class UserWithoutId:
            name = "Test User"
        
        user = UserWithoutId()
        tenant = DummyTenant()
        
        with pytest.raises(Exception):
            get_all_voicemails(tenant, user, 123)

    @patch("voice_core.services.voicemail.get_voicemail.fetch_voicemails_by_folder")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_user_without_id_attribute_get_by_folder(self, mock_vm_assignment, mock_get_token, mock_fetch_by_folder):
        """Test error logging when user object doesn't have id attribute."""
        # Setup mocks to cause an error
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_fetch_by_folder.side_effect = Exception("Wazo API error")
        
        # Create user without id attribute
        class UserWithoutId:
            name = "Test User"
        
        user = UserWithoutId()
        tenant = DummyTenant()
        
        with pytest.raises(Exception):
            get_voicemails_by_folder(tenant, user, 123, 1)

    @patch("voice_core.services.voicemail.get_voicemail.fetch_voicemail_recording")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_user_without_id_attribute_get_recording(self, mock_vm_assignment, mock_get_token, mock_fetch_recording):
        """Test error logging when user object doesn't have id attribute."""
        # Setup mocks to cause an error
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_fetch_recording.side_effect = Exception("Wazo API error")
        
        # Create user without id attribute
        class UserWithoutId:
            name = "Test User"
        
        user = UserWithoutId()
        tenant = DummyTenant()
        
        with pytest.raises(Exception):
            get_voicemail_recording(tenant, user, 123, "msg-456")

    @patch("voice_core.services.voicemail.get_voicemail.fetch_all_voicemail")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_zero_voicemail_id(self, mock_vm_assignment, mock_get_token, mock_fetch_all):
        """Test with voicemail_id of 0."""
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment(voicemail_id=0)
        mock_vm_assignment.objects.get.return_value = assignment
        mock_fetch_all.return_value = {"id": 0, "folders": []}
        
        tenant = DummyTenant()
        user = DummyUser()
        
        result = get_all_voicemails(tenant, user, 0)
        
        assert result == {"id": 0, "folders": []}
        mock_fetch_all.assert_called_once_with(
            voicemail_id=0,
            admin_token="admin-token-123",
        )

    @patch("voice_core.services.voicemail.get_voicemail.fetch_voicemail_recording")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_empty_message_id(self, mock_vm_assignment, mock_get_token, mock_fetch_recording):
        """Test with empty message_id."""
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment()
        mock_vm_assignment.objects.get.return_value = assignment
        mock_fetch_recording.return_value = (b"data", "audio/wav")
        
        tenant = DummyTenant()
        user = DummyUser()
        
        recording, content_type = get_voicemail_recording(tenant, user, 123, "")
        
        assert recording == b"data"
        assert content_type == "audio/wav"
        mock_fetch_recording.assert_called_once_with(
            voicemail_id=123,
            message_id="",
            admin_token="admin-token-123",
        )


class TestIntegrationScenarios:
    """Test integration scenarios that combine multiple aspects."""

    @patch("voice_core.services.voicemail.get_voicemail.datetime")
    @patch("voice_core.services.voicemail.get_voicemail.fetch_all_voicemail")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_complete_get_all_voicemails_workflow(self, mock_vm_assignment, mock_get_token, mock_fetch_all, mock_datetime):
        """Test the complete successful workflow for getting all voicemails."""
        # Setup timing
        start_time = datetime(2023, 1, 1, 12, 0, 0)
        end_time = datetime(2023, 1, 1, 12, 0, 5)  # 5 seconds later
        mock_datetime.now.side_effect = [start_time, end_time]
        
        # Setup mocks
        mock_get_token.return_value = "admin-token-xyz"
        assignment = DummyVoicemailAssignment(voicemail_id=789)
        assignment.user = DummyUser(user_id=456)
        mock_vm_assignment.objects.get.return_value = assignment
        
        expected_result = {
            "id": 789,
            "folders": [
                {"id": 1, "name": "inbox", "messages": [{"id": "msg1"}, {"id": "msg2"}]},
                {"id": 2, "name": "old", "messages": [{"id": "msg3"}]},
                {"id": 3, "name": "deleted", "messages": []},
            ]
        }
        mock_fetch_all.return_value = expected_result
        
        # Setup test data
        tenant = DummyTenant("tenant-uuid-789")
        user = DummyUser(user_id=456)
        voicemail_id = 789
        
        # Execute
        result = get_all_voicemails(tenant, user, voicemail_id)
        
        # Comprehensive assertions
        assert result == expected_result
        
        # Verify all calls with exact parameters
        mock_vm_assignment.objects.get.assert_called_once_with(user=user, voicemail_id=voicemail_id)
        mock_get_token.assert_called_once()
        mock_fetch_all.assert_called_once_with(
            voicemail_id=voicemail_id,
            admin_token="admin-token-xyz",
        )
        
        # Verify timing calls
        assert mock_datetime.now.call_count == 2

    def test_parameter_validation_consistency_across_functions(self):
        """Test that parameter validation is consistent across all functions."""
        tenant_no_uuid = DummyTenant(wazo_tenant_uuid=None)
        tenant_empty_uuid = DummyTenant(wazo_tenant_uuid="")
        user = DummyUser()
        
        # All functions should raise ValidationError for missing tenant UUID
        with pytest.raises(ValidationError, match="Tenant is missing wazo_tenant_uuid"):
            get_all_voicemails(tenant_no_uuid, user, 123)
        
        with pytest.raises(ValidationError, match="Tenant is missing wazo_tenant_uuid"):
            get_voicemails_by_folder(tenant_no_uuid, user, 123, 1)
        
        with pytest.raises(ValidationError, match="Tenant is missing wazo_tenant_uuid"):
            get_voicemail_recording(tenant_no_uuid, user, 123, "msg-456")
        
        # Empty string should also raise ValidationError
        with pytest.raises(ValidationError, match="Tenant is missing wazo_tenant_uuid"):
            get_all_voicemails(tenant_empty_uuid, user, 123)

    @patch("voice_core.services.voicemail.get_voicemail.fetch_all_voicemail")
    @patch("voice_core.services.voicemail.get_voicemail.fetch_voicemails_by_folder")
    @patch("voice_core.services.voicemail.get_voicemail.fetch_voicemail_recording")
    @patch("voice_core.services.voicemail.get_voicemail.get_wazo_admin_token")
    @patch("voice_core.services.voicemail.get_voicemail.VoicemailAssignment")
    def test_multiple_functions_same_user_voicemail(self, mock_vm_assignment, mock_get_token, mock_fetch_recording, mock_fetch_by_folder, mock_fetch_all):
        """Test calling multiple functions with the same user and voicemail."""
        # Setup mocks
        mock_get_token.return_value = "admin-token-123"
        assignment = DummyVoicemailAssignment(voicemail_id=123)
        mock_vm_assignment.objects.get.return_value = assignment
        
        mock_fetch_all.return_value = {"id": 123, "folders": []}
        mock_fetch_by_folder.return_value = {"id": 1, "messages": []}
        mock_fetch_recording.return_value = (b"audio", "audio/wav")
        
        tenant = DummyTenant()
        user = DummyUser()
        voicemail_id = 123
        
        # Call all functions
        result1 = get_all_voicemails(tenant, user, voicemail_id)
        result2 = get_voicemails_by_folder(tenant, user, voicemail_id, 1)
        result3 = get_voicemail_recording(tenant, user, voicemail_id, "msg-456")
        
        # Verify results
        assert result1 == {"id": 123, "folders": []}
        assert result2 == {"id": 1, "messages": []}
        assert result3 == (b"audio", "audio/wav")
        
        # Verify all assignment checks were made
        assert mock_vm_assignment.objects.get.call_count == 3
        assert mock_get_token.call_count == 3