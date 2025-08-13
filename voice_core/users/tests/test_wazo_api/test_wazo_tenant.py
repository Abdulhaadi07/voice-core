import pytest
from unittest.mock import patch, MagicMock
from voice_core.tenant.models import Tenant
from voice_core.users.wazo_helpers.wazo_tenant import get_wazo_tenant_uuid, create_wazo_tenant
import uuid


@pytest.fixture
def tenant():
    # Create a simple Tenant instance (not saved to DB)
    return Tenant(name="TestTenant")


@patch("voice_core.users.wazo_helpers.wazo_tenant.requests.post")
def test_create_wazo_tenant_success(mock_post):
    fake_uuid = str(uuid.uuid4())
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"uuid": fake_uuid}
    mock_post.return_value = mock_response

    result = create_wazo_tenant("TenantName", "admin-token-123")

    assert isinstance(result, uuid.UUID)
    assert str(result) == fake_uuid
    mock_post.assert_called_once()
    called_url = mock_post.call_args[1]["url"] if "url" in mock_post.call_args[1] else mock_post.call_args[0][0]
    assert called_url.endswith("/api/auth/0.1/tenants")


@patch("voice_core.users.wazo_helpers.wazo_tenant.requests.post")
def test_create_wazo_tenant_failure_status(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad request"
    mock_post.return_value = mock_response

    result = create_wazo_tenant("TenantName", "admin-token-123")
    assert result is None


@patch("voice_core.users.wazo_helpers.wazo_tenant.requests.post")
def test_create_wazo_tenant_raises_request_exception(mock_post):
    mock_post.side_effect = Exception("Connection error")

    result = create_wazo_tenant("TenantName", "admin-token-123")
    assert result is None


@patch("voice_core.users.wazo_helpers.wazo_tenant.create_wazo_tenant")
def test_get_wazo_tenant_uuid_existing_tenant(mock_create_tenant, tenant):
    tenant.wazo_tenant_uuid = uuid.uuid4()
    tenant.save = MagicMock()

    result = get_wazo_tenant_uuid(tenant, "admin-token-123")

    assert result == tenant.wazo_tenant_uuid
    mock_create_tenant.assert_not_called()
    tenant.save.assert_not_called()


@patch("voice_core.users.wazo_helpers.wazo_tenant.create_wazo_tenant")
def test_get_wazo_tenant_uuid_new_tenant_success(mock_create_tenant, tenant):
    new_uuid = uuid.uuid4()
    mock_create_tenant.return_value = new_uuid
    tenant.wazo_tenant_uuid = None
    tenant.save = MagicMock()

    result = get_wazo_tenant_uuid(tenant, "admin-token-123")

    assert result == new_uuid
    tenant.save.assert_called_once_with(update_fields=['wazo_tenant_uuid'])
    mock_create_tenant.assert_called_once_with(tenant.name, "admin-token-123")


@patch("voice_core.users.wazo_helpers.wazo_tenant.create_wazo_tenant")
def test_get_wazo_tenant_uuid_save_raises(mock_create_tenant, tenant):
    new_uuid = uuid.uuid4()
    mock_create_tenant.return_value = new_uuid
    tenant.wazo_tenant_uuid = None

    def raise_exc(*args, **kwargs):
        raise Exception("DB save error")

    tenant.save = MagicMock(side_effect=raise_exc)

    with pytest.raises(Exception, match="DB save error"):
        get_wazo_tenant_uuid(tenant, "admin-token-123")
