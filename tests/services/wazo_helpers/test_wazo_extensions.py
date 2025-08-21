import pytest
from unittest.mock import patch, MagicMock
import uuid

from voice_core.services.wazo_helpers import wazo_extensions as ext

def test_headers_includes_tenant_as_str():
    h = ext._headers("adm", uuid.uuid4())
    assert h["X-Auth-Token"] == "adm"
    assert "Wazo-Tenant" in h
    assert isinstance(h["Wazo-Tenant"], str)

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.post")
def test_create_line_success(mock_post):
    mock_resp = MagicMock(status_code=201, json=lambda: {"id": "123", "provisioning_extension": "456"})
    mock_resp.status_code = 201
    mock_post.return_value = mock_resp

    out = ext.create_line("adm", "ten", "ctx")
    assert out == (123, "456")

    args, kwargs = mock_post.call_args
    assert args[0].endswith("/api/confd/1.1/lines")
    assert kwargs["json"] == {"context": "ctx"}
    assert kwargs["headers"]["X-Auth-Token"] == "adm"
    assert kwargs["headers"]["Wazo-Tenant"] == "ten"

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.post")
def test_create_line_non_2xx_raises(mock_post):
    mock_resp = MagicMock(status_code=400)
    mock_resp.raise_for_status.side_effect = Exception("HTTP 400")
    mock_post.return_value = mock_resp
    with pytest.raises(Exception, match="HTTP 400"):
        ext.create_line("adm", "ten", "ctx")

@patch("voice_core.services.wazo_helpers.wazo_extensions.get_transport_uuid", return_value="transport-uuid")
@patch("voice_core.services.wazo_helpers.wazo_extensions.get_global_template_uuid", return_value="global-uuid")
@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.post")
def test_create_sip_endpoint_success(mock_post, _gt, _tt):
    mock_resp = MagicMock(status_code=201)
    mock_resp.json.return_value = {"uuid": "u", "label": "L", "name": "N"}
    mock_post.return_value = mock_resp

    out = ext.create_sip_endpoint("adm", "ten", "user", "pwd", "lbl")
    assert out == ("u", "L", "N")

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.get")
def test_get_transport_uuid_success(mock_get):
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"items": [{"name": "transport-udp", "uuid": "udp-uuid"}]}
    mock_get.return_value = mock_resp
    assert ext.get_transport_uuid("adm") == "udp-uuid"

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.get")
def test_get_transport_uuid_not_found_raises_attribute_error_current_impl(mock_get):
    # Current code calls .get() on None; consider fixing to raise ValueError instead.
    mock_resp = MagicMock(status_code=400)
    mock_resp.json.return_value = {"items": [{"name": "other", "uuid": "x"}]}
    mock_get.return_value = mock_resp
    with pytest.raises(Exception):
        ext.get_transport_uuid("adm")

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.post")
def test_create_user_voicemail_success_bool_enabled(mock_post):
    mock_resp = MagicMock(status_code=201)
    mock_resp.json.return_value = {"id": "id1", "password": "p1", "enabled": True}
    mock_post.return_value = mock_resp
    out = ext.create_user_voicemail("user", "ten", "adm", "ctx", "e@x", "100", "1234", "Name")
    assert out == ("id1", "p1", True)

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.post")
def test_create_user_voicemail_success_string_enabled(mock_post):
    mock_resp = MagicMock(status_code=201)
    mock_resp.json.return_value = {"id": "id1", "password": "p1", "enabled": "false"}
    mock_post.return_value = mock_resp
    out = ext.create_user_voicemail("user", "ten", "adm", "ctx", "e@x", "100", "1234", "Name")
    assert out == ("id1", "p1", False)

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.post")
def test_create_user_voicemail_parse_error_returns_nones(mock_post):
    mock_resp = MagicMock(status_code=201)
    mock_resp.json.side_effect = ValueError("bad json")
    mock_post.return_value = mock_resp
    out = ext.create_user_voicemail("user", "ten", "adm", "ctx", "e@x", "100", "1234", "Name")
    assert out == (None, None, None)

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.post")
def test_create_user_voicemail_non_201_returns_false(mock_post):
    mock_resp = MagicMock(status_code=400, text="bad")
    mock_post.return_value = mock_resp
    assert ext.create_user_voicemail("user", "ten", "adm", "ctx", "e@x", "100", "1234", "Name") is False

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.put")
def test_assign_line_with_sip_endpoint_statuses(mock_put):
    mock_put.return_value = MagicMock(status_code=204)
    assert ext.assign_line_with_sip_endpoint("adm", "ten", 1, "sip") is True
    mock_put.return_value = MagicMock(status_code=500, text="err")
    assert ext.assign_line_with_sip_endpoint("adm", "ten", 1, "sip") is False

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.post")
def test_create_extension_success(mock_post):
    mock_post.return_value = MagicMock(status_code=201, json=lambda: {"id": "7"})
    assert ext.create_extension("adm", "ten", "ctx", 123) == 7

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.post")
def test_create_extension_non_2xx_raises(mock_post):
    resp = MagicMock(status_code=400)
    resp.raise_for_status.side_effect = Exception("HTTP 400")
    mock_post.return_value = resp
    with pytest.raises(Exception, match="HTTP 400"):
        ext.create_extension("adm", "ten", "ctx", 123)

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.post")
def test_create_sip_endpoint_non_201_raises(mock_post):
    resp = MagicMock(status_code=400)
    resp.raise_for_status.side_effect = Exception("HTTP 400")
    mock_post.return_value = resp
    with pytest.raises(Exception, match="HTTP 400"):
        ext.create_sip_endpoint("adm", "ten", "u", "p", "lbl")

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.get")
def test_get_global_template_uuid_success(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200, json=lambda: {"items": [{"label": "global", "uuid": "g"}]}
    )
    assert ext.get_global_template_uuid("adm", "ten") == "g"

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.get")
def test_get_global_template_uuid_not_found_raises_current_impl(mock_get):
    mock_get.return_value = MagicMock(
        status_code=400, json=lambda: {"items": [{"label": "other", "uuid": "x"}]}
    )
    with pytest.raises(Exception):
        ext.get_global_template_uuid("adm", "ten")

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.get")
def test_get_global_template_uuid_non_200_returns_false(mock_get):
    mock_get.return_value = MagicMock(status_code=500, text="err")
    assert ext.get_global_template_uuid("adm", "ten") is False

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.get")
def test_get_transport_uuid_non_200_returns_false(mock_get):
    mock_get.return_value = MagicMock(status_code=500, text="err")
    assert ext.get_transport_uuid("adm") is False

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.put")
def test_assign_line_with_extension_statuses(mock_put):
    mock_put.return_value = MagicMock(status_code=204)
    assert ext.assign_line_with_extension("adm", "ten", 1, 2) is True
    mock_put.return_value = MagicMock(status_code=400, text="err")
    assert ext.assign_line_with_extension("adm", "ten", 1, 2) is False

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.put")
def test_assign_user_with_line_statuses(mock_put):
    mock_put.return_value = MagicMock(status_code=204)
    assert ext.assign_user_with_line("adm", "ten", "usr", 1) is True
    mock_put.return_value = MagicMock(status_code=400, text="err")
    assert ext.assign_user_with_line("adm", "ten", "usr", 1) is False

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.delete")
def test_unassign_line_with_sip_endpoint_statuses(mock_delete):
    mock_delete.return_value = MagicMock(status_code=204)
    assert ext.unassign_line_with_sip_endpoint("adm", "ten", 1, "sip") is True
    mock_delete.return_value = MagicMock(status_code=400, text="err")
    assert ext.unassign_line_with_sip_endpoint("adm", "ten", 1, "sip") is False

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.delete")
def test_unassign_line_with_extension_statuses(mock_delete):
    mock_delete.return_value = MagicMock(status_code=204)
    assert ext.unassign_line_with_extension("adm", "ten", 1, 2) is True
    mock_delete.return_value = MagicMock(status_code=400, text="err")
    assert ext.unassign_line_with_extension("adm", "ten", 1, 2) is False

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.delete")
def test_unassign_user_with_line_statuses(mock_delete):
    mock_delete.return_value = MagicMock(status_code=204)
    assert ext.unassign_user_with_line("adm", "ten", "usr", 1) is True
    mock_delete.return_value = MagicMock(status_code=400, text="err")
    assert ext.unassign_user_with_line("adm", "ten", "usr", 1) is False

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.delete")
def test_delete_sip_endpoint_statuses(mock_delete):
    mock_delete.return_value = MagicMock(status_code=204)
    assert ext.delete_sip_endpoint("adm", "ten", "sip") is True
    mock_delete.return_value = MagicMock(status_code=400, text="err")
    assert ext.delete_sip_endpoint("adm", "ten", "sip") is False

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.delete")
def test_delete_line_statuses(mock_delete):
    mock_delete.return_value = MagicMock(status_code=200)
    assert ext.delete_line("adm", "ten", 1) is True
    mock_delete.return_value = MagicMock(status_code=500, text="err")
    assert ext.delete_line("adm", "ten", 1) is False

@patch("voice_core.services.wazo_helpers.wazo_extensions.requests.delete")
def test_delete_extension_statuses(mock_delete):
    mock_delete.return_value = MagicMock(status_code=204)
    assert ext.delete_extension("adm", "ten", 2) is True
    mock_delete.return_value = MagicMock(status_code=500, text="err")
    assert ext.delete_extension("adm", "ten", 2) is False