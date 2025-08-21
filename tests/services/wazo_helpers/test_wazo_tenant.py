import pytest
from unittest.mock import patch, MagicMock
from voice_core.tenant.models import Tenant
from voice_core.services.wazo_helpers.wazo_tenant import get_wazo_tenant_uuid, create_wazo_tenant
import uuid


@pytest.fixture
def tenant():
    return Tenant(name="TestTenant")


@patch("voice_core.services.wazo_helpers.wazo_tenant.requests.post")
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


@patch("voice_core.services.wazo_helpers.wazo_tenant.requests.post")
def test_create_wazo_tenant_failure_status(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad request"
    mock_post.return_value = mock_response

    result = create_wazo_tenant("TenantName", "admin-token-123")
    assert result is None


@patch("voice_core.services.wazo_helpers.wazo_tenant.requests.post")
def test_create_wazo_tenant_raises_request_exception(mock_post):
    mock_post.side_effect = Exception("Connection error")

    result = create_wazo_tenant("TenantName", "admin-token-123")
    assert result is None


def test_get_wazo_tenant_uuid_existing_tenant(tenant):
    existing_uuid = uuid.uuid4()
    tenant.wazo_tenant_uuid = existing_uuid
    tenant.save = MagicMock()

    # Mock create_wazo_tenant and create_context
    with patch("voice_core.services.wazo_helpers.wazo_tenant.create_wazo_tenant") as mock_create_tenant, \
         patch("voice_core.services.wazo_helpers.wazo_tenant.create_context") as mock_create_context:
        result_uuid, did_exist = get_wazo_tenant_uuid(tenant, "admin-token-123")

        assert result_uuid == existing_uuid
        assert did_exist is True
        mock_create_tenant.assert_not_called()
        mock_create_context.assert_not_called()
        tenant.save.assert_not_called()

def test_get_wazo_tenant_uuid_new_tenant_success(tenant):
    new_uuid = uuid.uuid4()
    tenant.wazo_tenant_uuid = None
    tenant.save = MagicMock()

    fake_context = {"uuid": "ctx-uuid", "name": "name", "label": "label", "user_ranges": []}

    with patch("voice_core.services.wazo_helpers.wazo_tenant.create_wazo_tenant", return_value=new_uuid) as mock_create_tenant, \
         patch("voice_core.services.wazo_helpers.wazo_tenant.create_context", return_value=fake_context) as mock_create_context:
        result_uuid, did_exist = get_wazo_tenant_uuid(tenant, "admin-token-123")

    assert result_uuid == new_uuid
    assert did_exist is False

    tenant.save.assert_any_call(update_fields=['wazo_tenant_uuid'])
    assert tenant.save.call_count == 2  # second save after contexts update

    mock_create_tenant.assert_called_once_with(tenant.name, "admin-token-123")
    mock_create_context.assert_called_once_with(tenant)

@patch("voice_core.services.wazo_helpers.wazo_tenant.create_wazo_tenant")
def test_get_wazo_tenant_uuid_save_raises(mock_create_tenant, tenant):
    new_uuid = uuid.uuid4()
    mock_create_tenant.return_value = new_uuid
    tenant.wazo_tenant_uuid = None

    def raise_exc(*args, **kwargs):
        raise Exception("DB save error")

    tenant.save = MagicMock(side_effect=raise_exc)

    with pytest.raises(Exception, match="DB save error"):
        get_wazo_tenant_uuid(tenant, "admin-token-123")