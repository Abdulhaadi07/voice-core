import pytest
from unittest.mock import patch, MagicMock
import requests
import uuid
from voice_core.services.wazo_helpers.wazo_voicemail import (
    _truncate,
    _headers,
    fetch_all_voicemail,
    fetch_voicemails_by_folder,
    update_voicemail_as_read,
    fetch_voicemail_recording,
)

class TestHeadersFunction:
    def test_headers_without_tenant_uuid(self):
        admin_token = "admin-token-123"
        headers = _headers(admin_token)
        
        expected = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "X-Auth-Token": admin_token,
        }
        assert headers == expected

    def test_headers_with_tenant_uuid(self):
        admin_token = "admin-token-123"
        tenant_uuid = str(uuid.uuid4())
        headers = _headers(admin_token, tenant_uuid)
        
        expected = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "X-Auth-Token": admin_token,
            "Wazo-Tenant": tenant_uuid,
        }
        assert headers == expected

    def test_headers_converts_tenant_uuid_to_string(self):
        admin_token = "admin-token-123"
        tenant_uuid = uuid.uuid4()  # UUID object, not string
        headers = _headers(admin_token, tenant_uuid)
        
        assert headers["Wazo-Tenant"] == str(tenant_uuid)
        assert isinstance(headers["Wazo-Tenant"], str)


class TestFetchAllVoicemail:
    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.get")
    def test_fetch_all_voicemail_success(self, mock_get):
        voicemail_data = {
            "id": 123,
            "folders": [
                {"id": 1, "name": "inbox", "messages": []},
                {"id": 2, "name": "old", "messages": []},
            ]
        }
        mock_response = MagicMock()
        mock_response.json.return_value = voicemail_data
        mock_get.return_value = mock_response

        admin_token = "admin-token"
        voicemail_id = 123
        result = fetch_all_voicemail(admin_token, voicemail_id)

        assert result == voicemail_data
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert f"/api/calld/1.0/voicemails/{voicemail_id}" in args[0]
        assert kwargs["headers"]["X-Auth-Token"] == admin_token
        assert kwargs["timeout"] == 10
        assert kwargs["verify"] is False
        mock_response.raise_for_status.assert_called_once()

    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.get")
    def test_fetch_all_voicemail_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.RequestException("404 Not Found")
        mock_get.return_value = mock_response

        with pytest.raises(requests.RequestException, match="404 Not Found"):
            fetch_all_voicemail("admin-token", 123)

    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.get")
    def test_fetch_all_voicemail_request_exception(self, mock_get):
        mock_get.side_effect = requests.RequestException("Connection error")

        with pytest.raises(requests.RequestException, match="Connection error"):
            fetch_all_voicemail("admin-token", 123)

    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.get")
    def test_fetch_all_voicemail_request_exception_with_response(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = "Error response body"
        exception = requests.RequestException("Connection error")
        exception.response = mock_response
        mock_get.side_effect = exception

        with pytest.raises(requests.RequestException, match="Connection error"):
            fetch_all_voicemail("admin-token", 123)


class TestFetchVoicemailsByFolder:
    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.get")
    def test_fetch_voicemails_by_folder_success(self, mock_get):
        folder_data = {
            "id": 1,
            "name": "inbox",
            "messages": [
                {"id": "msg1", "caller_id": "123456789"},
                {"id": "msg2", "caller_id": "987654321"},
            ]
        }
        mock_response = MagicMock()
        mock_response.json.return_value = folder_data
        mock_get.return_value = mock_response

        admin_token = "admin-token"
        voicemail_id = 123
        folder_id = 1
        result = fetch_voicemails_by_folder(admin_token, voicemail_id, folder_id)

        assert result == folder_data
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert f"/api/calld/1.0/voicemails/{voicemail_id}/folders/{folder_id}" in args[0]
        assert kwargs["headers"]["X-Auth-Token"] == admin_token
        assert kwargs["timeout"] == 10
        assert kwargs["verify"] is False
        mock_response.raise_for_status.assert_called_once()

    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.get")
    def test_fetch_voicemails_by_folder_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        with pytest.raises(requests.HTTPError, match="404 Not Found"):
            fetch_voicemails_by_folder("admin-token", 123, 1)

    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.get")
    def test_fetch_voicemails_by_folder_request_exception(self, mock_get):
        mock_get.side_effect = requests.RequestException("Connection error")

        with pytest.raises(requests.RequestException, match="Connection error"):
            fetch_voicemails_by_folder("admin-token", 123, 1)

    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.get")
    def test_fetch_voicemails_by_folder_request_exception_with_response(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = "Error response body"
        exception = requests.RequestException("Connection error")
        exception.response = mock_response
        mock_get.side_effect = exception

        with pytest.raises(requests.RequestException, match="Connection error"):
            fetch_voicemails_by_folder("admin-token", 123, 1)


class TestUpdateVoicemailAsRead:
    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.put")
    def test_update_voicemail_as_read_success_with_response(self, mock_put):
        response_data = {"status": "updated"}
        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.text = '{"status": "updated"}'
        mock_put.return_value = mock_response

        admin_token = "admin-token"
        voicemail_id = 123
        message_id = "msg-123"
        folder_id = 2
        result = update_voicemail_as_read(admin_token, voicemail_id, message_id, folder_id)

        assert result == response_data
        mock_put.assert_called_once()
        args, kwargs = mock_put.call_args
        assert f"/api/calld/1.0/voicemails/{voicemail_id}/messages/{message_id}" in args[0]
        assert kwargs["headers"]["X-Auth-Token"] == admin_token
        assert kwargs["json"] == {"folder_id": folder_id}
        assert kwargs["timeout"] == 10
        assert kwargs["verify"] is False
        mock_response.raise_for_status.assert_called_once()

    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.put")
    def test_update_voicemail_as_read_success_empty_response(self, mock_put):
        mock_response = MagicMock()
        mock_response.text = ""  # Empty response
        mock_put.return_value = mock_response

        result = update_voicemail_as_read("admin-token", 123, "msg-123", 2)
        assert result == {}

    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.put")
    def test_update_voicemail_as_read_http_error(self, mock_put):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("400 Bad Request")
        mock_put.return_value = mock_response

        with pytest.raises(requests.HTTPError, match="400 Bad Request"):
            update_voicemail_as_read("admin-token", 123, "msg-123", 2)
       

    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.put")
    def test_update_voicemail_as_read_request_exception(self, mock_put):
        mock_put.side_effect = requests.RequestException("Connection error")

        with pytest.raises(requests.RequestException, match="Connection error"):
            update_voicemail_as_read("admin-token", 123, "msg-123", 2)

    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.put")
    def test_update_voicemail_as_read_request_exception_with_response(self, mock_put):
        mock_response = MagicMock()
        mock_response.text = "Error response body"
        exception = requests.RequestException("Connection error")
        exception.response = mock_response
        mock_put.side_effect = exception

        with pytest.raises(requests.RequestException, match="Connection error"):   
            update_voicemail_as_read("admin-token", 123, "msg-123", 2)


class TestFetchVoicemailRecording:
    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.get")
    def test_fetch_voicemail_recording_success_with_content_type(self, mock_get):
        audio_content = b"fake audio data"
        content_type = "audio/wav"
        mock_response = MagicMock()
        # Streamed content via iter_content; first call yields data, second yields nothing
        mock_response.iter_content.side_effect = [iter([audio_content]), iter([])]
        mock_response.headers = {"Content-Type": content_type}
        mock_get.return_value = mock_response

        admin_token = "admin-token"
        voicemail_id = 123
        message_id = "msg-123"
        chunks_iter, headers = fetch_voicemail_recording(admin_token, voicemail_id, message_id)

        # Consume iterator and verify content and headers
        content = b"".join(chunks_iter)
        assert content == audio_content
        assert headers["Content-Type"] == content_type
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert f"/api/calld/1.0/voicemails/{voicemail_id}/messages/{message_id}/recording" in args[0]
        assert kwargs["headers"]["accept"] == "audio/wav"
        assert kwargs["headers"]["X-Auth-Token"] == admin_token
        # Helper uses connect/read timeout tuple
        assert kwargs["timeout"] == (15, 15)
        assert kwargs["stream"] is True
        assert kwargs["verify"] is False
        mock_response.raise_for_status.assert_called_once()

    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.get")
    def test_fetch_voicemail_recording_success_default_content_type(self, mock_get):
        audio_content = b"fake audio data"
        mock_response = MagicMock()
        mock_response.iter_content.side_effect = [iter([audio_content]), iter([])]
        mock_response.headers = {}  # No Content-Type header
        mock_get.return_value = mock_response

        chunks_iter, headers = fetch_voicemail_recording("admin-token", 123, "msg-123")
        content = b"".join(chunks_iter)
        assert content == audio_content
        assert headers["Content-Type"] == "audio/wav"  # Default content type

    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.get")
    def test_fetch_voicemail_recording_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        with pytest.raises(requests.HTTPError, match="404 Not Found"):  
            fetch_voicemail_recording("admin-token", 123, "msg-123")

    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.get")
    def test_fetch_voicemail_recording_request_exception(self, mock_get):
        mock_get.side_effect = requests.RequestException("Connection error")

        with pytest.raises(requests.RequestException, match="Connection error"):
            fetch_voicemail_recording("admin-token", 123, "msg-123")

    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.get")
    def test_fetch_voicemail_recording_request_exception_with_response(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = "Error response body"
        exception = requests.RequestException("Connection error")
        exception.response = mock_response
        mock_get.side_effect = exception
        with pytest.raises(requests.RequestException, match="Connection error"):
             fetch_voicemail_recording("admin-token", 123, "msg-123")

    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.get")
    def test_fetch_voicemail_recording_different_content_type(self, mock_get):
        audio_content = b"fake mp3 data"
        content_type = "audio/mpeg"
        mock_response = MagicMock()
        mock_response.iter_content.side_effect = [iter([audio_content]), iter([])]
        mock_response.headers = {"Content-Type": content_type}
        mock_get.return_value = mock_response

        chunks_iter, headers = fetch_voicemail_recording("admin-token", 123, "msg-123")
        content = b"".join(chunks_iter)
        assert content == audio_content
        assert headers["Content-Type"] == content_type


class TestIntegrationScenarios:
    """Test scenarios that combine multiple functions or edge cases."""
    
    @patch("voice_core.services.wazo_helpers.wazo_voicemail.requests.get")
    def test_fetch_all_voicemail_then_fetch_folder(self, mock_get):
        # First call returns all voicemail data
        all_voicemail_data = {
            "id": 123,
            "folders": [{"id": 1, "name": "inbox"}]
        }
        # Second call returns specific folder data
        folder_data = {
            "id": 1,
            "name": "inbox",
            "messages": [{"id": "msg1"}]
        }
        
        mock_get.side_effect = [
            MagicMock(json=lambda: all_voicemail_data),
            MagicMock(json=lambda: folder_data)
        ]

        # Test the workflow
        all_result = fetch_all_voicemail("admin-token", 123)
        folder_result = fetch_voicemails_by_folder("admin-token", 123, 1)

        assert all_result == all_voicemail_data
        assert folder_result == folder_data
        assert mock_get.call_count == 2

    def test_headers_consistency_across_functions(self):
        """Ensure _headers function works consistently for all functions that use it."""
        admin_token = "test-token"
        tenant_uuid = "test-tenant"
        
        headers_without_tenant = _headers(admin_token)
        headers_with_tenant = _headers(admin_token, tenant_uuid)
        
        # Basic headers should be the same
        assert headers_without_tenant["X-Auth-Token"] == admin_token
        assert headers_with_tenant["X-Auth-Token"] == admin_token
        assert headers_without_tenant["accept"] == "application/json"
        assert headers_with_tenant["accept"] == "application/json"
        
        # Tenant header should only be present when provided
        assert "Wazo-Tenant" not in headers_without_tenant
        assert headers_with_tenant["Wazo-Tenant"] == tenant_uuid

    def test_error_handling_consistency(self):
        """Test that all functions handle None/error cases consistently."""
        # These functions should return None on error

        with pytest.raises(requests.RequestException):
            fetch_all_voicemail("", 0)
        with pytest.raises(requests.RequestException):
            fetch_voicemails_by_folder("", 0, 0)
        with pytest.raises(requests.RequestException):
            update_voicemail_as_read("", 0, "", 0)
        
        
        # This function returns tuple of (None, None) on error

        with pytest.raises(requests.RequestException):
            fetch_voicemail_recording("", 0, "")
