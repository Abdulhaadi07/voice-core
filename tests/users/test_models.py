from voice_core.users.models import User
import pytest
@pytest.mark.skip(reason="Skipping this tests for now")
def test_user_get_absolute_url(user: User):
    assert user.get_absolute_url() == f"/users/{user.pk}/"
