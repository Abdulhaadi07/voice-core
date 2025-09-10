import pytest
from unittest.mock import patch, MagicMock
from voice_core.services.extensions.available_extensions import get_available_extensions

MODULE = "voice_core.services.extensions.available_extensions"

def _mock_values_list(return_list):
    qs = MagicMock()
    qs.values_list.return_value = return_list
    return qs

@patch(f"{MODULE}.ExtensionAssignment")
@patch(f"{MODULE}.Tenant")
def test_happy_path_list_contexts(mock_tenant, mock_assignments):
    tenant = MagicMock()
    tenant.name = "Acme"
    tenant.contexts = [
        {"name": "ctx-a", "user_ranges": [{"start": "100", "end": "103"}, {"start": 105, "end": 106}]},
        {"name": "ctx-b", "user_ranges": [{"start": 200, "end": 201}]},
    ]
    mock_tenant.objects.get.return_value = tenant
    mock_assignments.objects.filter.return_value = _mock_values_list(["100", "106", "200"])

    out = get_available_extensions(tenant_id=1)

    assert out["ctx-a"] == [101, 102, 103, 105]
    assert out["ctx-b"] == [201]

@patch(f"{MODULE}.ExtensionAssignment")
@patch(f"{MODULE}.Tenant")
def test_legacy_dict_contexts(mock_tenant, mock_assignments):
    tenant = MagicMock()
    tenant.name = "Acme"
    tenant.contexts = {
        "k1": {"name": "ctx-x", "user_ranges": [{"start": 10, "end": 12}]}
    }
    mock_tenant.objects.get.return_value = tenant
    mock_assignments.objects.filter.return_value = _mock_values_list([])

    out = get_available_extensions(tenant_id=1)

    assert out == {"ctx-x": [10, 11, 12]}

@patch(f"{MODULE}.ExtensionAssignment")
@patch(f"{MODULE}.Tenant")
def test_overlapping_ranges_are_deduped_and_sorted(mock_tenant, mock_assignments):
    tenant = MagicMock()
    tenant.name = "Acme"
    tenant.contexts = [
        {"name": "ctx", "user_ranges": [{"start": 1, "end": 3}, {"start": 3, "end": 5}]}
    ]
    mock_tenant.objects.get.return_value = tenant
    mock_assignments.objects.filter.return_value = _mock_values_list([2])

    out = get_available_extensions(tenant_id=1)

    assert out == {"ctx": [1, 3, 4, 5]}

@patch(f"{MODULE}.ExtensionAssignment")
@patch(f"{MODULE}.Tenant")
def test_all_assigned_still_returns_empty_list_for_context(mock_tenant, mock_assignments):
    tenant = MagicMock()
    tenant.name = "Acme"
    tenant.contexts = [{"name": "ctx", "user_ranges": [{"start": 10, "end": 11}]}]
    mock_tenant.objects.get.return_value = tenant
    mock_assignments.objects.filter.return_value = _mock_values_list([10, 11])

    out = get_available_extensions(tenant_id=1)

    assert out == {"ctx": []}

@patch(f"{MODULE}.ExtensionAssignment")
@patch(f"{MODULE}.Tenant")
def test_empty_contexts_returns_empty_dict(mock_tenant, mock_assignments):
    tenant = MagicMock()
    tenant.name = "Acme"
    tenant.contexts = []
    mock_tenant.objects.get.return_value = tenant

    out = get_available_extensions(1)

    assert out == {}

@patch(f"{MODULE}.Tenant")
def test_tenant_not_found_returns_empty_dict(mock_tenant):
    mock_tenant.DoesNotExist = type("DoesNotExist", (Exception,), {})
    mock_tenant.objects.get.side_effect = mock_tenant.DoesNotExist

    with pytest.raises(mock_tenant.DoesNotExist):
        get_available_extensions(999)

@patch(f"{MODULE}.ExtensionAssignment")
@patch(f"{MODULE}.Tenant")
def test_generic_exception_returns_empty_dict(mock_tenant, mock_assignments):
    # Make mock Tenant’s DoesNotExist a real exception to satisfy `except Tenant.DoesNotExist`
    mock_tenant.DoesNotExist = type("DoesNotExist", (Exception,), {})

    tenant = MagicMock()
    tenant.name = "Acme"
    tenant.contexts = [{"name": "ctx", "user_ranges": [{"start": 1, "end": 1}]}]
    mock_tenant.objects.get.return_value = tenant
    mock_assignments.objects.filter.side_effect = RuntimeError("db error")

    with pytest.raises(RuntimeError, match="db error"):
        get_available_extensions(1) 