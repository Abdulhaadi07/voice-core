import uuid
import pytest
from unittest.mock import patch
from voice_core.users.models import User
from voice_core.tenant.models import Tenant
from io import StringIO
from django.core.management import call_command

@pytest.mark.django_db
@patch('voice_core.users.managers.create_cognito_user', return_value="mock_cognito_sub")
@patch('voice_core.users.managers.get_wazo_admin_token', return_value=uuid.uuid4())
@patch('voice_core.users.managers.get_wazo_tenant_uuid', return_value=uuid.uuid4())
@patch('voice_core.users.managers.create_wazo_user', return_value=[uuid.uuid4(), "mock_wazo_username"])
@patch('voice_core.users.managers.resolve_tenant_from_email')
@patch('voice_core.users.managers.send_welcome_msg')
class TestUserManager:
    @pytest.fixture(autouse=True)
    def setup_tenant(self, db):
        self.test_tenant = Tenant.objects.create(
            name="example.com",
            domain="example.com",
            wazo_tenant_uuid=uuid.uuid4()
        )

    def test_create_superuser(
        self,
        mock_send_welcome_msg,
        mock_resolve_tenant,
        mock_create_wazo_user,
        mock_get_wazo_tenant_uuid,
        mock_get_wazo_admin_token,
        mock_create_cognito_user,
    ):
        mock_resolve_tenant.return_value = self.test_tenant

        user = User.objects.create_superuser(
            email="admin@example.com",
            name="admin",
            password="testPassWord12$",
            tenant=self.test_tenant,
        )
        assert user.email == "admin@example.com"
        assert user.is_staff
        assert user.is_superuser
        assert user.username is None\
        
    def test_create_superuser_username_ignored(self,
        mock_send_welcome_msg,
        mock_resolve_tenant,
        mock_create_wazo_user,
        mock_get_wazo_tenant_uuid,
        mock_get_wazo_admin_token,
        mock_create_cognito_user,
    ):
        mock_resolve_tenant.return_value = self.test_tenant
        user = User.objects.create_superuser(
            email="test@example.com",
            name="test",
            password="testPassWord12$",  # noqa: S106
        )
        assert user.username is None

    def test_createsuperuser_command(self,
        mock_send_welcome,
        mock_resolve_tenant,
        mock_create_wazo_user,
        mock_get_wazo_tenant_uuid,
        mock_get_wazo_admin_token,
        mock_create_cognito_user,
    ):
        mock_resolve_tenant.return_value = self.test_tenant
        """Ensure createsuperuser command works with our custom manager."""
        out = StringIO()
        command_result = call_command(
            "createsuperuser",
            "--email", "henry@example.com",
            "--name", "Henry Example",
            "--noinput",  # same as interactive=False
            stdout=out,
        )

        assert command_result is None
        assert out.getvalue() == "Superuser created successfully.\n"
        user = User.objects.get(email="henry@example.com")
        assert not user.has_usable_password()
