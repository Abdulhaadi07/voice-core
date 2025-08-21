import pytest
from unittest.mock import patch, MagicMock

from voice_core.services.extensions.assign_extension import assign_extension

class DummyTenant:
    id = 1
    name = "Acme"
    wazo_tenant_uuid = "ten-uuid"
    contexts = [{"name": "ctx-acme"}]  # or dict for legacy

class DummyUser:
    id = 2
    name = "John"
    email = "john@example.com"
    wazo_user_id = "user-uuid"

@patch("voice_core.services.extensions.assign_extension.ExtensionAssignment")
@patch("voice_core.services.extensions.assign_extension.create_user_voicemail", return_value=("vmid", "1234", True))
@patch("voice_core.services.extensions.assign_extension.assign_user_with_line", return_value=True)
@patch("voice_core.services.extensions.assign_extension.assign_line_with_extension", return_value=True)
@patch("voice_core.services.extensions.assign_extension.assign_line_with_sip_endpoint", return_value=True)
@patch("voice_core.services.extensions.assign_extension.create_sip_endpoint", return_value=("sip-uuid", "lbl", "name"))
@patch("voice_core.services.extensions.assign_extension.create_extension", return_value=789)
@patch("voice_core.services.extensions.assign_extension.create_line", return_value=(123, "456"))
@patch("voice_core.services.extensions.assign_extension.get_wazo_admin_token", return_value="adm")
def test_assign_extension_success(mock_token, mock_line, mock_ext, mock_sip, mock_attach_sip, mock_attach_ext, mock_attach_user, mock_vm, mock_model):
    tenant = DummyTenant()
    user = DummyUser()

    assignment_instance = MagicMock()
    mock_model.objects.create.return_value = assignment_instance

    out = assign_extension(
        tenant=tenant,
        extension_int=142,
        sip_username="u",
        sip_password="p",
        user=user,
        context_name="ctx-acme",
        voicemail_pin=9999,
        voicemail_max_messages=10,
    )
    assert out is assignment_instance

    # sip label includes extension and line id
    mock_sip.assert_called_once()
    args, kwargs = mock_sip.call_args
    assert kwargs["label"].startswith("sip-E-142-L-123")

    mock_attach_sip.assert_called_once_with("adm", str(tenant.wazo_tenant_uuid), 123, "sip-uuid")
    mock_attach_ext.assert_called_once_with("adm", str(tenant.wazo_tenant_uuid), 123, 789)
    mock_attach_user.assert_called_once_with("adm", str(tenant.wazo_tenant_uuid), str(user.wazo_user_id), 123)
    mock_vm.assert_called_once()

    mock_model.objects.create.assert_called_once()
    created_kwargs = mock_model.objects.create.call_args.kwargs
    assert created_kwargs["extension"] == "142"
    assert created_kwargs["wazo_line_id"] == 123
    assert created_kwargs["context_name"] == "ctx-acme"
    assert created_kwargs["voicemail_id"] == "vmid"
    assert created_kwargs["voicemail_enabled"] is True

def test_assign_extension_missing_tenant_uuid_raises():
    tenant = DummyTenant()
    tenant.wazo_tenant_uuid = None
    user = DummyUser()
    with pytest.raises(ValueError, match="wazo_tenant_uuid"):
        assign_extension(tenant, 100, "u", "p", user, "ctx", 1234, 10)

def test_assign_extension_missing_user_uuid_raises():
    tenant = DummyTenant()
    user = DummyUser()
    user.wazo_user_id = None
    with patch("voice_core.services.extensions.assign_extension.get_wazo_admin_token", return_value="adm"), \
         patch("voice_core.services.extensions.assign_extension.create_line", return_value=(1, "pe")), \
         patch("voice_core.services.extensions.assign_extension.create_extension", return_value=2), \
         patch("voice_core.services.extensions.assign_extension.create_sip_endpoint", return_value=("sip", "l", "n")), \
         patch("voice_core.services.extensions.assign_extension.assign_line_with_sip_endpoint", return_value=True), \
         patch("voice_core.services.extensions.assign_extension.assign_line_with_extension", return_value=True):
        with pytest.raises(ValueError, match="wazo_user_id"):
            assign_extension(tenant, 100, "u", "p", user, "ctx", 1234, 10)

@pytest.mark.parametrize("which,ret", [
    ("assign_line_with_sip_endpoint", False),
    ("assign_line_with_extension", False),
    ("assign_user_with_line", False),
])
def test_assign_extension_step_failures_raise(which, ret):
    tenant = DummyTenant()
    user = DummyUser()
    patches = {
        "get_wazo_admin_token": ("adm"),
        "create_line": (1, "pe"),
        "create_extension": 2,
        "create_sip_endpoint": ("sip", "l", "n"),
        "assign_line_with_sip_endpoint": True,
        "assign_line_with_extension": True,
        "assign_user_with_line": True,
    }
    patches[which] = ret
    with patch("voice_core.services.extensions.assign_extension.get_wazo_admin_token", return_value=patches["get_wazo_admin_token"]), \
         patch("voice_core.services.extensions.assign_extension.create_line", return_value=patches["create_line"]), \
         patch("voice_core.services.extensions.assign_extension.create_extension", return_value=patches["create_extension"]), \
         patch("voice_core.services.extensions.assign_extension.create_sip_endpoint", return_value=patches["create_sip_endpoint"]), \
         patch("voice_core.services.extensions.assign_extension.assign_line_with_sip_endpoint", return_value=patches["assign_line_with_sip_endpoint"]), \
         patch("voice_core.services.extensions.assign_extension.assign_line_with_extension", return_value=patches["assign_line_with_extension"]), \
         patch("voice_core.services.extensions.assign_extension.assign_user_with_line", return_value=patches["assign_user_with_line"]):
        with pytest.raises(RuntimeError):
            assign_extension(tenant, 100, "u", "p", user, "ctx", 1234, 10)

def test_assign_extension_context_resolution_list_and_legacy_dict():
    tenant = DummyTenant()
    user = DummyUser()

    # list form
    tenant.contexts = [{"name": "list-name"}]
    with patch("voice_core.services.extensions.assign_extension.get_wazo_admin_token", return_value="adm"), \
         patch("voice_core.services.extensions.assign_extension.create_line", return_value=(1, "pe")), \
         patch("voice_core.services.extensions.assign_extension.create_extension", return_value=2), \
         patch("voice_core.services.extensions.assign_extension.create_sip_endpoint", return_value=("sip", "l", "n")), \
         patch("voice_core.services.extensions.assign_extension.assign_line_with_sip_endpoint", return_value=True), \
         patch("voice_core.services.extensions.assign_extension.assign_line_with_extension", return_value=True), \
         patch("voice_core.services.extensions.assign_extension.assign_user_with_line", return_value=True), \
         patch("voice_core.services.extensions.assign_extension.create_user_voicemail", return_value=("vmid", "1234", True)), \
         patch("voice_core.services.extensions.assign_extension.ExtensionAssignment.objects.create", return_value=MagicMock()) as mock_create:
        assign_extension(tenant, 100, "u", "p", user, "list-name", 1234, 10)
        assert mock_create.called

    # legacy dict form
    tenant.contexts = {"k1": {"name": "dict-name"}}
    with patch("voice_core.services.extensions.assign_extension.get_wazo_admin_token", return_value="adm"), \
         patch("voice_core.services.extensions.assign_extension.create_line", return_value=(1, "pe")), \
         patch("voice_core.services.extensions.assign_extension.create_extension", return_value=2), \
         patch("voice_core.services.extensions.assign_extension.create_sip_endpoint", return_value=("sip", "l", "n")), \
         patch("voice_core.services.extensions.assign_extension.assign_line_with_sip_endpoint", return_value=True), \
         patch("voice_core.services.extensions.assign_extension.assign_line_with_extension", return_value=True), \
         patch("voice_core.services.extensions.assign_extension.assign_user_with_line", return_value=True), \
         patch("voice_core.services.extensions.assign_extension.create_user_voicemail", return_value=("vmid", "1234", True)), \
         patch("voice_core.services.extensions.assign_extension.ExtensionAssignment.objects.create", return_value=MagicMock()) as mock_create:
        assign_extension(tenant, 100, "u", "p", user, "dict-name", 1234, 10)
        assert mock_create.called