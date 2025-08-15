import uuid
import pytest
from unittest.mock import patch
from voice_core.users.models import User
from voice_core.tenant.models import Tenant
from io import StringIO
from django.core.management import call_command
from django.contrib.auth.models import Group

@pytest.fixture
def test_tenant(db):
    return Tenant.objects.create(
        name="example.com",
        domain="example.com",
        wazo_tenant_uuid=uuid.uuid4()
    )

@pytest.fixture(autouse=True)
def create_user_groups(db):
    Group.objects.get_or_create(name="admin")
    Group.objects.get_or_create(name="agent")

@pytest.mark.django_db
class TestUserManager:

    @pytest.fixture(autouse=True)
    def patch_managers(self, test_tenant):
        """Patch external calls."""
        with patch('voice_core.users.managers.create_cognito_user', return_value="mock_cognito_sub"), \
             patch('voice_core.users.managers.get_wazo_admin_token', return_value=str(uuid.uuid4())), \
             patch('voice_core.users.managers.get_wazo_tenant_uuid', return_value=[str(uuid.uuid4()), True]), \
             patch('voice_core.users.managers.create_wazo_user', return_value=[str(uuid.uuid4()), "mock_wazo_username"]), \
             patch('voice_core.users.managers.resolve_tenant_from_email', return_value=test_tenant), \
             patch('voice_core.users.managers.send_welcome_msg'):
            yield

    def test_create_superuser(self, test_tenant):
        user = User.objects.create_superuser(
            email="admin@example.com",
            name="admin",
            password="testPassWord12$",
            tenant=test_tenant,
        )
        assert user.email == "admin@example.com"
        assert user.is_staff is True
        assert user.is_superuser is True
        assert user.username is None

    def test_create_superuser_username_ignored(self, test_tenant):
        user = User.objects.create_superuser(
            email="test@example.com",
            name="test",
            password="testPassWord12$",
            tenant=test_tenant,
        )
        assert user.username is None

    def test_createsuperuser_command(self, test_tenant):
        out = StringIO()
        call_command(
            "createsuperuser",
            "--email", "henry@example.com",
            "--name", "Henry Example",
            "--noinput",
            stdout=out,
        )
        user = User.objects.get(email="henry@example.com")
        assert "Superuser" in out.getvalue()
