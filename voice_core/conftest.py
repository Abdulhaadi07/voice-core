import pytest

from voice_core.users.models import User
from tests.factories import UserFactory


@pytest.fixture(autouse=True)
def _media_storage(settings, tmpdir) -> None:
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def user(db) -> User:
    return UserFactory()

@pytest.fixture(autouse=True)
def disable_tz_for_tests(settings):
    """Disable timezone support for all tests."""
    settings.USE_TZ = False