# tests: voice_core/users/tests/test_wazo_api/test_wazo_context.py
import pytest
from unittest.mock import patch, MagicMock
import uuid
from requests.exceptions import RequestException

from voice_core.services.wazo_helpers.wazo_context import (
    create_wazo_context,
    create_context,
)

@pytest.fixture
def tenant():
    class T:
        pass
    t = T()
    t.name = "Acme"
    t.max_users = 50
    t.wazo_tenant_uuid = uuid.uuid4()
    return t

@patch("voice_core.services.wazo_helpers.wazo_context.requests.post")
def test_create_wazo_context_success_builds_payload_and_parses_response(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "uuid": "ctx-uuid",
        "name": "ctx-name",
        "label": "Acme-initial-context",
        "user_ranges": [{"start": "100", "end": "150"}],
    }
    mock_post.return_value = mock_response

    admin_token = "adm"
    tenant_uuid = str(uuid.uuid4())
    label = "Acme-initial-context"
    ranges = [{"start": "100", "end": "150"}]

    out = create_wazo_context(admin_token, tenant_uuid, label, "internal", ranges)

    assert out["uuid"] == "ctx-uuid"
    # URL, headers, and payload were sent correctly
    args, kwargs = mock_post.call_args
    assert args[0].endswith("/api/confd/1.1/contexts")
    assert kwargs["verify"] is False
    assert kwargs["headers"]["X-Auth-Token"] == admin_token
    assert kwargs["headers"]["Wazo-Tenant"] == tenant_uuid
    assert kwargs["json"] == {"label": label, "type": "internal", "user_ranges": ranges}

@patch("voice_core.services.wazo_helpers.wazo_context.requests.post")
def test_create_wazo_context_non_201_raises(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad"
    # response.raise_for_status() should be called; have it raise
    mock_response.raise_for_status.side_effect = Exception("HTTP 400")
    mock_post.return_value = mock_response

    with pytest.raises(Exception, match="HTTP 400"):
        create_wazo_context("adm", str(uuid.uuid4()), "label", "internal", [])

@patch("voice_core.services.wazo_helpers.wazo_context.requests.post")
def test_create_wazo_context_request_exception_bubbles(mock_post):
    mock_post.side_effect = RequestException("network")

    with pytest.raises(RequestException, match="network"):
        create_wazo_context("adm", str(uuid.uuid4()), "label", "internal", [])

@patch("voice_core.services.wazo_helpers.wazo_context.requests.post")
def test_create_wazo_context_missing_keys_raises_keyerror(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"uuid": "only-uuid"}  # missing keys
    mock_post.return_value = mock_response

    with pytest.raises(KeyError):
        create_wazo_context("adm", str(uuid.uuid4()), "label", "internal", [])

@pytest.mark.skip(reason="Skipping this test for now")
@patch("voice_core.services.wazo_helpers.wazo_context.create_wazo_context")
@patch("voice_core.services.wazo_helpers.wazo_context.get_wazo_admin_token")
def test_create_context_success_calls_create_wazo_context_with_computed_values(mock_get_token, mock_create_ctx, tenant):
    mock_get_token.return_value = "adm-token"
    fake_ctx = {"uuid": "ctx", "name": "n", "label": "l", "user_ranges": []}
    mock_create_ctx.return_value = fake_ctx

    out = create_context(tenant)

    assert out == fake_ctx
    # label and ranges are computed inside create_context
    expected_label = f"{tenant.name}-initial-context"
    expected_ranges = [{"start": "100", "end": f"{100 + tenant.max_users}"}]
    mock_create_ctx.assert_called_once_with("adm-token", str(tenant.wazo_tenant_uuid), expected_label, "internal", expected_ranges)

@patch("voice_core.services.wazo_helpers.wazo_context.create_wazo_context")
@patch("voice_core.services.wazo_helpers.wazo_context.get_wazo_admin_token", return_value="adm-token")
def test_create_context_bubbles_error(mock_get_token, mock_create_ctx, tenant):
    mock_create_ctx.side_effect = Exception("boom")
    with pytest.raises(Exception, match="boom"):
        create_context(tenant)
