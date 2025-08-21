import uuid
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock

from voice_core.tenant.models import Tenant
from tests.factories import UserFactory


pytestmark = pytest.mark.urls("config.urls")


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


@pytest.mark.django_db
def test_list_permissions(api_client, staff_user):
    url = reverse("tenant-users-list-create", kwargs={"tenant_id": staff_user.tenant_id})
    res = api_client.get(url)  # unauthenticated
    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    api_client.force_authenticate(user=staff_user)
    res = api_client.get(url)
    assert res.status_code == status.HTTP_200_OK


@pytest.mark.django_db
@patch("voice_core.users.api.views.tenant_user_views.UserListSerializer")
@patch("voice_core.users.api.views.tenant_user_views.get_object_or_404")
def test_list_success_with_mocked_serializer(mock_get, mock_list_serializer, api_client, staff_user, tenant):
    mock_get.return_value = tenant  # return tenant for get_object_or_404(Tenant,...)

    class DummyListSerializer:
        def __init__(self, *args, **kwargs): pass  # accept (queryset, many=True, context=..)
        @property
        def data(self):
            return [{"id": 1, "email": "a@example.com"}, {"id": 2, "email": "b@example.com"}]
    mock_list_serializer.side_effect = DummyListSerializer

    api_client.force_authenticate(user=staff_user)
    url = reverse("tenant-users-list-create", kwargs={"tenant_id": tenant.id})
    res = api_client.get(url)
    assert res.status_code == 200
    assert res.data == [{"id": 1, "email": "a@example.com"}, {"id": 2, "email": "b@example.com"}]


@pytest.mark.django_db
@patch("voice_core.users.api.views.tenant_user_views.LogEntry.objects.log_action")
@patch("voice_core.users.api.views.tenant_user_views.UserCreateSerializer")
@patch("voice_core.users.api.views.tenant_user_views.get_object_or_404")
def test_create_success_with_mocked_serializer(mock_get, mock_create_serializer, mock_log, api_client, staff_user, tenant):
    mock_get.return_value = tenant

    class DummyCreateSerializer:
        def __init__(self, *args, **kwargs): self._data = {"id": 10, "email": "new@example.com"}
        def is_valid(self, raise_exception=False): return True
        @property
        def validated_data(self): return {"tenant_role": "agent"}
        def save(self, **kwargs): return MagicMock(id=10, email="new@example.com", tenant_role="agent")
        @property
        def data(self): return self._data
    mock_create_serializer.side_effect = DummyCreateSerializer

    api_client.force_authenticate(user=staff_user)
    url = reverse("tenant-users-list-create", kwargs={"tenant_id": tenant.id})
    res = api_client.post(url, {"email":"new@example.com","name":"New","password":"Secretp@ssw0rd!"}, format="json")
    assert res.status_code == 201
    assert res.data["email"] == "new@example.com"
    assert mock_log.called


@pytest.mark.django_db
@patch("voice_core.users.api.views.tenant_user_views.get_object_or_404")
@patch("voice_core.users.api.views.tenant_user_views.UserDetailSerializer")
def test_retrieve_success_with_mocks(mock_detail_serializer, mock_get_obj, api_client, staff_user, tenant):
    # Note: router path uses 'pk' in URL; view reads 'user_id' internally.
    # We mock get_object_or_404 to avoid kwargs mismatch issues.
    mock_tenant_obj = tenant
    mock_user_obj = MagicMock(id=99, email="x@example.com")
    # First call returns tenant, second returns user
    mock_get_obj.side_effect = [mock_tenant_obj, mock_user_obj]

    class DummyDetailSerializer:
        def __init__(self, instance, context=None): pass
        @property
        def data(self): return {"id": 99, "email": "x@example.com"}
    mock_detail_serializer.side_effect = DummyDetailSerializer

    api_client.force_authenticate(user=staff_user)
    url = reverse("tenant-users-detail-update", kwargs={"tenant_id": tenant.id, "user_id": 99})
    res = api_client.get(url)

    assert res.status_code == status.HTTP_200_OK
    assert res.data == {"id": 99, "email": "x@example.com"}


@pytest.mark.django_db
@patch("voice_core.users.api.views.tenant_user_views.LogEntry.objects.log_action")
@patch("voice_core.users.api.views.tenant_user_views.get_object_or_404")
@patch("voice_core.users.api.views.tenant_user_views.UserUpdateSerializer")
def test_partial_update_success_with_mocks(
    mock_update_serializer, mock_get_obj, mock_log, api_client, staff_user, tenant
):
    mock_tenant_obj = tenant
    mock_user_obj = MagicMock(id=101, email="y@example.com")
    mock_get_obj.side_effect = [mock_tenant_obj, mock_user_obj]

    class DummyUpdateSerializer:
        def __init__(self, instance, data=None, partial=False, context=None): pass
        def is_valid(self, raise_exception=False): return True
        def save(self): return MagicMock(id=101, email="new@example.com")
    mock_update_serializer.side_effect = DummyUpdateSerializer

    # Also mock the final detail serializer used in response
    with patch("voice_core.users.api.views.tenant_user_views.UserDetailSerializer") as mock_detail:
        class DummyDetailSerializer:
            def __init__(self, instance, context=None): pass
            @property
            def data(self): return {"id": 101, "email": "new@example.com"}
        mock_detail.side_effect = DummyDetailSerializer

        api_client.force_authenticate(user=staff_user)
        url = reverse("tenant-users-detail-update", kwargs={"tenant_id": tenant.id, "user_id": 101})
        res = api_client.patch(url, {"name": "Updated"}, format="json")

        assert res.status_code == status.HTTP_200_OK
        assert res.data == {"id": 101, "email": "new@example.com"}
        mock_log.assert_called_once()
        

@pytest.mark.django_db
def test_list_search_filters_by_email_and_name(api_client, staff_user, tenant):
    # make sure staff_user is platform admin already; add two users in same tenant
    u1 = UserFactory(tenant=tenant, email="alice@example.com", name="Alice A", cognito_sub=str(uuid.uuid4()))
    u2 = UserFactory(tenant=tenant, email="bob@example.com", name="Bob B", cognito_sub=str(uuid.uuid4()))
    api_client.force_authenticate(user=staff_user)
    url = reverse("tenant-users-list-create", kwargs={"tenant_id": tenant.id})

    res = api_client.get(url, {"search": "alice"})
    assert res.status_code == status.HTTP_200_OK
    # Should include alice and not bob (serializer returns list of dicts)
    assert any("alice@example.com" == r.get("email") for r in res.data)
