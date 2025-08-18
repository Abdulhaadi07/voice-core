import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import Group
from voice_core.users.managers import UserManager

class MockUser:
    pk = 1
    is_staff = False
    groups = MagicMock()

    def __init__(self, email, **kwargs):
        self.email = email
        self.__dict__.update(kwargs)
        self.password = None
        self.save = MagicMock()
        self.delete = MagicMock()
        self.refresh_from_db = MagicMock()
        self.first_name = kwargs.get("first_name", "")
        self.wazo_user_id = None
        self.wazo_username = None
        self.wazo_provisioned_at = None

    @property
    def name(self):
        return self.first_name

@pytest.mark.django_db
def test_create_admin_user_success():
    email = "test@example.com"
    password = "securepassword"
    name = "Test User"
    manager = UserManager()
    manager.model = MockUser 

    with patch("voice_core.users.managers.resolve_tenant_from_email", return_value="example"), \
         patch("voice_core.users.managers.create_cognito_user", return_value="cognito-sub-123"), \
         patch("voice_core.users.managers.get_wazo_admin_token", return_value="admin-token-123"), \
         patch("voice_core.users.managers.get_wazo_tenant_uuid", return_value=("tenant-uuid-123", False)), \
         patch("voice_core.users.managers.create_wazo_user", return_value=["wazo-id-123", "wazo-username"]), \
         patch("voice_core.users.managers.send_welcome_msg"):

        Group.objects.get_or_create(name="agent")

        user = manager._create_user(email=email, password=password, name=name)

        assert user.email == email
        assert user.cognito_sub == "cognito-sub-123"
        assert user.wazo_user_id == "wazo-id-123"
        assert user.wazo_username == "wazo-username"
        user.groups.add.assert_called() 
        assert user.groups.filter(name="agent").exists()


@pytest.mark.django_db
def test_create_agent_user_success():
    email = "agent@example.com"
    password = "agentpassword"
    name = "Agent User"
    manager = UserManager()
    manager.model = MagicMock() 

    with patch("voice_core.users.managers.resolve_tenant_from_email", return_value="example"), \
         patch("voice_core.users.managers.create_cognito_user", return_value="cognito-sub-456"), \
         patch("voice_core.users.managers.get_wazo_admin_token", return_value="admin-token-456"), \
         patch("voice_core.users.managers.get_wazo_tenant_uuid", return_value=("tenant-uuid-456", True)), \
         patch("voice_core.users.managers.create_wazo_user", return_value=["wazo-id-456", "wazo-username"]), \
         patch("voice_core.users.managers.send_welcome_msg"):

        Group.objects.get_or_create(name="agent")

        user_instance = MagicMock()
        manager.model.return_value = user_instance  

        user = manager._create_user(email=email, password=password, name=name)

        assert user == user_instance
        user.groups.add.assert_called()  
        assert user.groups.filter(name="agent").exists()


@pytest.mark.django_db
def test_create_user_cognito_failure():
    manager = UserManager()
    manager.model = MockUser

    with patch("voice_core.users.managers.resolve_tenant_from_email", return_value="example"), \
         patch("voice_core.users.managers.create_cognito_user", return_value=None):

        with pytest.raises(Exception) as exc_info:
            manager._create_user(email="failcognito@example.com", password="pass")
        assert "Failed to create Cognito user" in str(exc_info.value)

@pytest.mark.django_db
def test_create_user_wazo_token_failure_triggers_rollback():
    manager = UserManager()
    manager.model = MockUser

    with patch("voice_core.users.managers.resolve_tenant_from_email", return_value="example"), \
         patch("voice_core.users.managers.create_cognito_user", return_value="sub123"), \
         patch("voice_core.users.managers.get_wazo_admin_token", return_value=None), \
         patch.object(manager, "_rollback_on_failure") as mock_rollback:

        with pytest.raises(Exception) as exc_info:
            manager._create_user(email="failwazo@example.com", password="pass")

        mock_rollback.assert_called_once()
        assert "Failed to get Wazo admin token" in str(exc_info.value)

@pytest.mark.django_db
def test_create_user_wazo_tenant_failure_triggers_rollback():
    manager = UserManager()
    manager.model = MockUser

    with patch("voice_core.users.managers.resolve_tenant_from_email", return_value="example"), \
         patch("voice_core.users.managers.create_cognito_user", return_value="sub123"), \
         patch("voice_core.users.managers.get_wazo_admin_token", return_value="admin-token"), \
         patch("voice_core.users.managers.get_wazo_tenant_uuid", return_value=(None, False)), \
         patch.object(manager, "_rollback_on_failure") as mock_rollback:

        with pytest.raises(Exception) as exc_info:
            manager._create_user(email="failtenant@example.com", password="pass")

        mock_rollback.assert_called_once()
        assert "Failed to get Wazo tenant UUID" in str(exc_info.value)
      
def test_rollback_on_failure_deletes_from_all_services():
    manager = UserManager()
    user_mock = MagicMock()
    cognito_sub = "sub123"
    wazo_user_id = "wazo123"
    admin_token = "token123"

    with patch("voice_core.users.managers.delete_cognito_user") as mock_cognito, \
         patch("voice_core.users.managers.delete_wazo_user") as mock_wazo:

        manager._rollback_on_failure(
            email="test@example.com",
            cognito_sub=cognito_sub,
            user=user_mock,
            wazo_user_uuid=wazo_user_id,
            admin_token=admin_token
        )

        mock_cognito.assert_called_once_with("test@example.com")
        mock_wazo.assert_called_once_with(wazo_user_id, admin_token)
        user_mock.delete.assert_called_once()

def test_create_user_with_no_email_raises_value_error():
    manager = UserManager()
    manager.model = MockUser

    with pytest.raises(ValueError) as exc_info:
        manager._create_user(email=None, password="pass")

    assert "The given email must be set" in str(exc_info.value)

@pytest.mark.django_db
def test_create_superuser_sets_fields_correctly():
    manager = UserManager()
    manager.model = MockUser
    
    Group.objects.get_or_create(name="admin")
    Group.objects.get_or_create(name="agent")

    with patch("voice_core.users.managers.resolve_tenant_from_email", return_value="example"), \
            patch("voice_core.users.managers.create_cognito_user", return_value="sub123"), \
            patch("voice_core.users.managers.get_wazo_admin_token", return_value="admin-token"), \
            patch("voice_core.users.managers.get_wazo_tenant_uuid", return_value=("tenant-uuid", False)), \
            patch("voice_core.users.managers.create_wazo_user", return_value=["123e4567-e89b-12d3-a456-426614174000", "wazo-username"]), \
            patch("voice_core.users.managers.send_welcome_msg"), \
            patch("voice_core.users.managers.delete_cognito_user"), \
            patch("voice_core.users.managers.delete_wazo_user"):

        superuser = manager.create_superuser(email="super@example.com", password="superpass")

        assert superuser.is_superuser is True
        assert superuser.is_staff is True