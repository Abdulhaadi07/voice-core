import pytest
from unittest.mock import patch, MagicMock
import requests
import uuid
from voice_core.services.wazo_helpers.wazo_sip_template import (
    _truncate,
    _headers,
    get_sip_global_template,
    get_tenant_global_template_uuid,
    get_master_global_template,
    create_tenant_global_template,
    delete_sip_template,
)


class TestTruncateFunction:
    def test_truncate_none_returns_empty_string(self):
        assert _truncate(None) == ""

    def test_truncate_short_text_returns_unchanged(self):
        text = "Short text"
        assert _truncate(text) == text

    def test_truncate_long_text_with_default_limit(self):
        text = "a" * 600
        result = _truncate(text)
        assert len(result) == 503  # 500 + "..."
        assert result.endswith("...")
        assert result.startswith("a" * 100)

    def test_truncate_long_text_with_custom_limit(self):
        text = "a" * 100
        result = _truncate(text, limit=50)
        assert len(result) == 53  # 50 + "..."
        assert result.endswith("...")


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


class TestGetTenantGlobalTemplateUuid:
    @patch("voice_core.services.wazo_helpers.wazo_sip_template.requests.get")
    def test_get_tenant_global_template_uuid_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {"label": "other", "uuid": "other-uuid"},
                {"label": "global", "uuid": "global-uuid-123"},
            ]
        }
        mock_get.return_value = mock_response

        admin_token = "admin-token"
        tenant_uuid = "tenant-uuid"
        result = get_tenant_global_template_uuid(admin_token, tenant_uuid)

        assert result == "global-uuid-123"
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert args[0].endswith("/api/confd/1.1/endpoints/sip/templates?recurse=false")
        assert kwargs["headers"]["X-Auth-Token"] == admin_token
        assert kwargs["headers"]["Wazo-Tenant"] == tenant_uuid
        assert kwargs["verify"] is False

    @patch("voice_core.services.wazo_helpers.wazo_sip_template.requests.get")
    def test_get_tenant_global_template_uuid_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {"label": "other", "uuid": "other-uuid"},
            ]
        }
        mock_get.return_value = mock_response

        result = get_tenant_global_template_uuid("admin-token", "tenant-uuid")
        assert result is None

    @patch("voice_core.services.wazo_helpers.wazo_sip_template.requests.get")
    def test_get_tenant_global_template_uuid_request_exception(self, mock_get):
        mock_get.side_effect = requests.RequestException("Connection error")

        with pytest.raises(requests.RequestException):
            get_tenant_global_template_uuid("admin-token", "tenant-uuid")

    @patch("voice_core.services.wazo_helpers.wazo_sip_template.requests.get")
    def test_get_tenant_global_template_uuid_non_200_status(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_get.return_value = mock_response

        result = get_tenant_global_template_uuid("admin-token", "tenant-uuid")
        assert result is False


class TestGetMasterGlobalTemplate:
    @patch("voice_core.services.wazo_helpers.wazo_sip_template.requests.get")
    def test_get_master_global_template_success(self, mock_get):
        template_data = {
            "uuid": "master-uuid",
            "label": "global",
            "options": {"some": "config"},
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [template_data]
        }
        mock_get.return_value = mock_response

        admin_token = "admin-token"
        result = get_master_global_template(admin_token)

        assert result == template_data
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert "search=" in args[0]
        assert kwargs["headers"]["X-Auth-Token"] == admin_token
        assert "Wazo-Tenant" not in kwargs["headers"]
        assert kwargs["verify"] is False

    @patch("voice_core.services.wazo_helpers.wazo_sip_template.requests.get")
    def test_get_master_global_template_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {"label": "other", "uuid": "other-uuid"},
            ]
        }
        mock_get.return_value = mock_response

        result = get_master_global_template("admin-token")
        assert result is None

    @patch("voice_core.services.wazo_helpers.wazo_sip_template.requests.get")
    def test_get_master_global_template_request_exception(self, mock_get):
        mock_get.side_effect = requests.RequestException("Connection error")

        with pytest.raises(requests.RequestException):
            get_master_global_template("admin-token")

    @patch("voice_core.services.wazo_helpers.wazo_sip_template.requests.get")
    def test_get_master_global_template_non_200_status(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_get.return_value = mock_response

        result = get_master_global_template("admin-token")
        assert result is None


class TestCreateTenantGlobalTemplate:
    @patch("voice_core.services.wazo_helpers.wazo_sip_template.requests.post")
    def test_create_tenant_global_template_success(self, mock_post):
        master_template = {
            "uuid": "master-uuid",
            "tenant_uuid": "master-tenant",
            "name": "master-name",
            "label": "global",
            "options": {"some": "config"},
        }
        new_uuid = "new-tenant-uuid"
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"uuid": new_uuid}
        mock_post.return_value = mock_response

        admin_token = "admin-token"
        tenant_uuid = "tenant-uuid"
        result = create_tenant_global_template(admin_token, tenant_uuid, master_template)

        assert result == new_uuid
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0].endswith("/api/confd/1.1/endpoints/sip/templates")
        assert kwargs["headers"]["X-Auth-Token"] == admin_token
        assert kwargs["headers"]["Wazo-Tenant"] == tenant_uuid
        assert kwargs["verify"] is False
        
        # Check that excluded fields are not in payload
        payload = kwargs["json"]
        assert "uuid" not in payload
        assert "tenant_uuid" not in payload
        assert "name" not in payload
        assert "label" in payload
        assert "options" in payload

    @patch("voice_core.services.wazo_helpers.wazo_sip_template.requests.post")
    def test_create_tenant_global_template_success_status_200(self, mock_post):
        master_template = {"label": "global", "options": {}}
        mock_response = MagicMock()
        mock_response.status_code = 200  # Also acceptable
        mock_response.json.return_value = {"uuid": "new-uuid"}
        mock_post.return_value = mock_response

        result = create_tenant_global_template("admin-token", "tenant-uuid", master_template)
        assert result == "new-uuid"

    @patch("voice_core.services.wazo_helpers.wazo_sip_template.requests.post")
    def test_create_tenant_global_template_request_exception(self, mock_post):
        mock_post.side_effect = requests.RequestException("Connection error")
        with pytest.raises(requests.RequestException):
             create_tenant_global_template("admin-token", "tenant-uuid", {"label": "global", "options": {}})

    @patch("voice_core.services.wazo_helpers.wazo_sip_template.requests.post")
    def test_create_tenant_global_template_non_success_status(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        result = create_tenant_global_template("admin-token", "tenant-uuid", {})
        assert result is None


class TestGetSipGlobalTemplate:
    @patch("voice_core.services.wazo_helpers.wazo_sip_template.get_tenant_global_template_uuid")
    def test_get_sip_global_template_tenant_exists(self, mock_get_tenant):
        mock_get_tenant.return_value = "existing-tenant-uuid"

        admin_token = "admin-token"
        tenant_uuid = "tenant-uuid"
        result = get_sip_global_template(admin_token, tenant_uuid)

        assert result == "existing-tenant-uuid"
        mock_get_tenant.assert_called_once_with(admin_token, tenant_uuid)

    @patch("voice_core.services.wazo_helpers.wazo_sip_template.create_tenant_global_template")
    @patch("voice_core.services.wazo_helpers.wazo_sip_template.get_master_global_template")
    @patch("voice_core.services.wazo_helpers.wazo_sip_template.get_tenant_global_template_uuid")
    def test_get_sip_global_template_create_from_master_success(self, mock_get_tenant, mock_get_master, mock_create):
        mock_get_tenant.return_value = None  # Tenant doesn't have template
        master_template = {"uuid": "master-uuid", "label": "global"}
        mock_get_master.return_value = master_template
        mock_create.return_value = "new-tenant-uuid"

        admin_token = "admin-token"
        tenant_uuid = "tenant-uuid"
        result = get_sip_global_template(admin_token, tenant_uuid)

        assert result == "new-tenant-uuid"
        mock_get_tenant.assert_called_once_with(admin_token, tenant_uuid)
        mock_get_master.assert_called_once_with(admin_token)
        mock_create.assert_called_once_with(admin_token, tenant_uuid, master_template)

    @patch("voice_core.services.wazo_helpers.wazo_sip_template.get_master_global_template")
    @patch("voice_core.services.wazo_helpers.wazo_sip_template.get_tenant_global_template_uuid")
    def test_get_sip_global_template_master_not_found(self, mock_get_tenant, mock_get_master):
        mock_get_tenant.return_value = None
        mock_get_master.return_value = None

        result = get_sip_global_template("admin-token", "tenant-uuid")
        assert result is None

    @patch("voice_core.services.wazo_helpers.wazo_sip_template.create_tenant_global_template")
    @patch("voice_core.services.wazo_helpers.wazo_sip_template.get_master_global_template")
    @patch("voice_core.services.wazo_helpers.wazo_sip_template.get_tenant_global_template_uuid")
    def test_get_sip_global_template_create_fails(self, mock_get_tenant, mock_get_master, mock_create):
        mock_get_tenant.return_value = None
        mock_get_master.return_value = {"uuid": "master-uuid"}
        mock_create.return_value = None  # Creation failed

        result = get_sip_global_template("admin-token", "tenant-uuid")
        assert result is None


class TestDeleteSipTemplate:
    @patch("voice_core.services.wazo_helpers.wazo_sip_template.requests.delete")
    def test_delete_sip_template_success_with_content(self, mock_delete):
        mock_response = MagicMock()
        mock_response.content = b'{"success": true}'
        mock_response.json.return_value = {"success": True}
        mock_delete.return_value = mock_response

        template_uuid = "template-uuid-123"
        admin_token = "admin-token"
        result = delete_sip_template(template_uuid, admin_token)

        assert result == {"success": True}
        mock_delete.assert_called_once()
        args, kwargs = mock_delete.call_args
        assert template_uuid in args[0]
        assert kwargs["headers"]["X-Auth-Token"] == admin_token
        assert kwargs["headers"]["accept"] == "application/json"

    @patch("voice_core.services.wazo_helpers.wazo_sip_template.requests.delete")
    def test_delete_sip_template_success_no_content(self, mock_delete):
        mock_response = MagicMock()
        mock_response.content = b''  # No content
        mock_delete.return_value = mock_response

        result = delete_sip_template("template-uuid", "admin-token")
        assert result == {"message": "Deleted successfully"}

    @patch("voice_core.services.wazo_helpers.wazo_sip_template.requests.delete")
    def test_delete_sip_template_raises_for_status(self, mock_delete):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_delete.return_value = mock_response

        with pytest.raises(requests.HTTPError, match="404 Not Found"):
            delete_sip_template("template-uuid", "admin-token")