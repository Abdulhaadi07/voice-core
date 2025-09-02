import uuid
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock

from voice_core.tenant.models import Tenant
from tests.factories import UserFactory


@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def tenant(db):
    return Tenant.objects.create(
        name=f"T-{uuid.uuid4().hex[:8]}",
        domain=f"{uuid.uuid4().hex[:8]}.io",
        max_users=50,
    )

@pytest.fixture
def staff_user(db, tenant):
    u = UserFactory(tenant=tenant, cognito_sub=str(uuid.uuid4()))
    u.is_staff = True
    u.is_superuser = True  # make platform admin
    u.save(update_fields=["is_staff", "is_superuser"])
    return u

@pytest.fixture
def non_staff_user(db, tenant):
    return UserFactory(tenant=tenant, cognito_sub=str(uuid.uuid4()))


@pytest.mark.django_db
def test_tenant_list_permissions(api_client, non_staff_user, staff_user):
    url = reverse("tenant-list")

    # Unauthenticated
    res = api_client.get(url)
    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    # Authenticated but not staff
    api_client.force_authenticate(user=non_staff_user)
    res = api_client.get(url)
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # Staff
    api_client.force_authenticate(user=staff_user)
    res = api_client.get(url)
    assert res.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_tenant_list_and_search_filter(api_client, staff_user):
    Tenant.objects.create(name="Acme", domain="acme.io", max_users=10)
    Tenant.objects.create(name="Beta", domain="beta.com", max_users=20)

    api_client.force_authenticate(user=staff_user)

    url = reverse("tenant-list")
    res = api_client.get(url)
    assert res.status_code == status.HTTP_200_OK
    assert len(res.data) >= 2

    res = api_client.get(url, {"search": "acme"})
    assert res.status_code == status.HTTP_200_OK
    assert any(t["name"] == "Acme" for t in res.data)
    assert all("acme" in (t["name"] + (t.get("domain") or "")).lower() for t in res.data)


@pytest.mark.django_db
@patch("voice_core.tenant.api.views.tenant_views.LogEntry.objects.log_action")
@patch("voice_core.tenant.api.views.tenant_views.get_wazo_tenant_uuid", return_value=(uuid.uuid4(), False))
@patch("voice_core.tenant.api.views.tenant_views.get_wazo_admin_token", return_value="adm")
def test_tenant_create_success(mock_token, mock_get_uuid, mock_log, api_client, staff_user):
    api_client.force_authenticate(user=staff_user)

    url = reverse("tenant-list")
    payload = {"name": "Gamma", "domain": "gamma.io", "max_users": 25, "status": "active"}
    res = api_client.post(url, payload, format="json")

    assert res.status_code == status.HTTP_201_CREATED
    assert res.data["name"] == "Gamma"
    assert "wazo_tenant_uuid" in res.data
    assert mock_token.called
    assert mock_get_uuid.called
    assert mock_log.called


@pytest.mark.django_db
@patch("voice_core.tenant.api.views.tenant_views.get_wazo_tenant_uuid", return_value=(uuid.uuid4(), True))
@patch("voice_core.tenant.api.views.tenant_views.get_wazo_admin_token", return_value="adm")
def test_tenant_create_conflict_when_preexists(mock_token, mock_get_uuid, api_client, staff_user):
    api_client.force_authenticate(user=staff_user)

    url = reverse("tenant-list")
    payload = {"name": "Already", "domain": "already.io", "max_users": 5, "status": "active"}
    res = api_client.post(url, payload, format="json")

    assert res.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
def test_tenant_create_validation_error_conflict(api_client, staff_user):
    # Pre-create tenant with unique name, then attempt duplicate
    Tenant.objects.create(name="Dup", domain="dup.io", max_users=10)
    api_client.force_authenticate(user=staff_user)

    url = reverse("tenant-list")
    payload = {"name": "Dup", "domain": "dup2.io"}
    res = api_client.post(url, payload, format="json")

    # View catches ValidationError and returns 409
    assert res.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
@patch("voice_core.tenant.api.views.tenant_views.LogEntry.objects.log_action")
def test_tenant_partial_update_success(mock_log, api_client, staff_user):
    t = Tenant.objects.create(name="Up", domain="up.io", max_users=10)
    api_client.force_authenticate(user=staff_user)

    url = reverse("tenant-detail", args=[t.id])
    res = api_client.patch(url, {"max_users": 99}, format="json")

    assert res.status_code == status.HTTP_200_OK
    assert res.data["max_users"] == 99
    assert mock_log.called

# -------- ExtensionViewSet: available --------

@pytest.mark.django_db
@patch("voice_core.tenant.api.views.extension_views.get_available_extensions", return_value={"ctx": [100, 101]})
def test_extensions_available_success(mock_avail, api_client, staff_user):
    api_client.force_authenticate(user=staff_user)
    url = reverse("tenant-extensions-available", kwargs={"tenant_id": 1})
    res = api_client.get(url)
    assert res.status_code == status.HTTP_200_OK
    assert res.data == {"contexts": {"ctx": [100, 101]}}


@pytest.mark.django_db
@patch("voice_core.tenant.api.views.extension_views.get_available_extensions", side_effect=Exception("fail"))
def test_extensions_available_internal_error_500(mock_avail, api_client, staff_user):
    api_client.force_authenticate(user=staff_user)
    url = reverse("tenant-extensions-available", kwargs={"tenant_id": 1})
    res = api_client.get(url)
    assert res.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# -------- ExtensionViewSet: assign --------

@pytest.mark.django_db
@patch("voice_core.tenant.api.views.extension_views.User")
def test_assign_404_when_user_not_found(mock_user, api_client, staff_user):
    # Ensure DoesNotExist is a real exception class on the mock
    mock_user.DoesNotExist = type("DoesNotExist", (Exception,), {})
    mock_user.objects.select_related.return_value.get.side_effect = mock_user.DoesNotExist

    api_client.force_authenticate(user=staff_user)
    url = reverse("tenant-extensions-assign", kwargs={"tenant_id": 1, "user_id": 999})
    payload = {
        "extension": 100,
        "sip_username": "sipuser",
        "sip_password": "sippwd",
        "voicemail_max_messages": 10,
        "voicemail_pin": 1234,
        "context_name": "ctx",
    }
    res = api_client.post(url, payload, format="json")
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
@patch("voice_core.tenant.api.views.extension_views.User")
def test_assign_400_when_no_contexts(mock_user, api_client, staff_user):
    user = MagicMock()
    tenant = MagicMock()
    tenant.contexts = []
    user.tenant = tenant

    mock_user.objects.select_related.return_value.get.return_value = user

    api_client.force_authenticate(user=staff_user)
    url = reverse("tenant-extensions-assign", kwargs={"tenant_id": 1, "user_id": 2})
    payload = {
        "extension": 100,
        "sip_username": "sipuser",
        "sip_password": "sippwd",
        "voicemail_max_messages": 10,
        "voicemail_pin": 1234,
    }
    res = api_client.post(url, payload, format="json")
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "No contexts configured" in res.data["detail"]


@pytest.mark.django_db
@patch("voice_core.tenant.api.views.extension_views.get_available_extensions", return_value={"ctxA": [101]})
@patch("voice_core.tenant.api.views.extension_views.User")
def test_assign_400_when_extension_not_available(mock_user, mock_avail, api_client, staff_user):
    user = MagicMock()
    tenant = MagicMock()
    tenant.id = 1
    tenant.contexts = [{"name": "ctxA"}]
    user.tenant = tenant
    mock_user.objects.select_related.return_value.get.return_value = user

    api_client.force_authenticate(user=staff_user)
    url = reverse("tenant-extensions-assign", kwargs={"tenant_id": 1, "user_id": 2})
    payload = {
        "extension": 100,  # not in available list
        "sip_username": "sipuser",
        "sip_password": "sippwd",
        "voicemail_max_messages": 10,
        "voicemail_pin": 1234,
        "context_name": "ctxA",
    }
    res = api_client.post(url, payload, format="json")
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "not available" in res.data["detail"]


@pytest.mark.django_db
@patch("voice_core.tenant.api.views.extension_views.ExtensionAssignment")
@patch("voice_core.tenant.api.views.extension_views.get_available_extensions", return_value={"ctxA": [100]})
@patch("voice_core.tenant.api.views.extension_views.User")
def test_assign_409_when_extension_already_assigned(mock_user, mock_avail, mock_assignment, api_client, staff_user):
    user = MagicMock()
    tenant = MagicMock()
    tenant.id = 1
    tenant.contexts = [{"name": "ctxA"}]
    user.tenant = tenant
    mock_user.objects.select_related.return_value.get.return_value = user

    # First uniqueness check: extension already assigned
    mock_assignment.objects.filter.return_value.exists.return_value = True

    api_client.force_authenticate(user=staff_user)
    url = reverse("tenant-extensions-assign", kwargs={"tenant_id": 1, "user_id": 2})
    payload = {
        "extension": 100,
        "sip_username": "sipuser",
        "sip_password": "sippwd",
        "voicemail_max_messages": 10,
        "voicemail_pin": 1234,
        "context_name": "ctxA",
    }
    res = api_client.post(url, payload, format="json")
    assert res.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
@patch("voice_core.tenant.api.views.extension_views.assign_extension")
@patch("voice_core.tenant.api.views.extension_views.get_available_extensions", return_value={"ctxA": [100]})
@patch("voice_core.tenant.api.views.extension_views.ExtensionAssignment")
@patch("voice_core.tenant.api.views.extension_views.User")
def test_assign_success_201(mock_user, mock_assignment, mock_avail, mock_assign, api_client, staff_user):
    user = MagicMock()
    user.id = 2  # ensure JSON-serializable
    tenant = MagicMock()
    tenant.id = 1  # ensure JSON-serializable
    tenant.contexts = [{"name": "ctxA"}]
    user.tenant = tenant
    mock_user.objects.select_related.return_value.get.return_value = user

    # both uniqueness checks -> False
    mock_assignment.objects.filter.return_value.exists.return_value = False

    # assign_extension returns serializable fields
    assignment = MagicMock(
        wazo_line_id=123,
        extension="100",
        sip_username="sipuser",
        context_name="ctxA",
    )
    mock_assign.return_value = assignment

    api_client.force_authenticate(user=staff_user)
    url = reverse("tenant-extensions-assign", kwargs={"tenant_id": 1, "user_id": 2})
    payload = {
        "extension": 100,
        "sip_username": "sipuser",
        "sip_password": "sippwd",
        "voicemail_max_messages": 10,
        "voicemail_pin": 1234,
        # no context_name → defaults to ctxA
    }
    res = api_client.post(url, payload, format="json")

    assert res.status_code == status.HTTP_201_CREATED
    assert res.data["line_id"] == 123
    assert res.data["extension"] == "100"
    assert res.data["sip_username"] == "sipuser"
    assert res.data["context_name"] == "ctxA"


@pytest.mark.django_db
@patch("voice_core.tenant.api.views.extension_views.ExtensionAssignment")
@patch("voice_core.tenant.api.views.extension_views.get_available_extensions", return_value={"ctxA": [100]})
@patch("voice_core.tenant.api.views.extension_views.User")
def test_assign_409_when_sip_username_in_use(mock_user, mock_avail, mock_assignment, api_client, staff_user):
    user = MagicMock()
    tenant = MagicMock()
    tenant.id = 1
    tenant.contexts = [{"name": "ctxA"}]
    user.tenant = tenant
    mock_user.objects.select_related.return_value.get.return_value = user

    # First exists() for extension → False; second exists() for sip_username → True
    first_filter = MagicMock(); first_filter.exists.return_value = False
    second_filter = MagicMock(); second_filter.exists.return_value = True
    mock_assignment.objects.filter.side_effect = [first_filter, second_filter]

    api_client.force_authenticate(user=staff_user)
    url = reverse("tenant-extensions-assign", kwargs={"tenant_id": 1, "user_id": 2})
    payload = {
        "extension": 100,
        "sip_username": "dupuser",
        "sip_password": "pwd",
        "voicemail_max_messages": 10,
        "voicemail_pin": 1234,
        "context_name": "ctxA",
    }
    res = api_client.post(url, payload, format="json")
    assert res.status_code == status.HTTP_409_CONFLICT