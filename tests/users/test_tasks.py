import pytest
from celery.result import EagerResult
from unittest.mock import patch, MagicMock, PropertyMock
from types import SimpleNamespace
from smtplib import SMTPAuthenticationError
from celery.exceptions import Retry 
import voice_core.users.tasks as tasks

pytestmark = pytest.mark.django_db


def test_user_count(settings):
    """A basic test to execute the get_users_count Celery task."""
    batch_size = 3
    from voice_core.users.models import User 
    with patch.object(User.objects, 'count', return_value=batch_size):
        settings.CELERY_TASK_ALWAYS_EAGER = True
        task_result = tasks.get_users_count.delay()
        assert isinstance(task_result, EagerResult)
        assert task_result.result == batch_size


@pytest.mark.django_db
class TestSendEmailTask:
    @patch("voice_core.users.tasks.get_connection")
    @patch("voice_core.users.tasks.EmailMultiAlternatives")
    def test_send_email_success(self, mock_email_cls, mock_get_connection, settings):
        mock_connection = MagicMock()
        mock_get_connection.return_value = mock_connection
  
        mock_email = MagicMock()
        mock_email.send.return_value = 1  # Simulate successful send (1 email sent)
        mock_email_cls.return_value = mock_email

        settings.DEFAULT_FROM_EMAIL = "from@example.com"
        
        mock_self = MagicMock()
        mock_self.request = SimpleNamespace(retries=0)
        mock_self.max_retries = tasks.send_email_task.max_retries
        
        mock_self.retry = MagicMock()
        result = tasks.send_email_task(
            mock_self, 
            "Test Subject", 
            "Body",         
            ["mdmustafiz7676@gmail.com"], 
        )

        assert result is True
        mock_email_cls.assert_called_once()
        mock_email.send.assert_called_once()

    @patch("voice_core.users.tasks.get_connection")
    @patch("voice_core.users.tasks.EmailMultiAlternatives")
    def test_send_email_failure_zero_count(self, mock_email_cls, mock_get_connection, settings):
        mock_connection = MagicMock()
        mock_get_connection.return_value = mock_connection

        mock_email = MagicMock()
        mock_email.send.return_value = 0  # Simulate send failure (0 emails sent)
        mock_email_cls.return_value = mock_email

        settings.DEFAULT_FROM_EMAIL = "from@example.com"

        mock_self = MagicMock()
        mock_self.request = SimpleNamespace(retries=0)
        mock_self.max_retries = tasks.send_email_task.max_retries
        mock_self.retry = MagicMock()

        result = tasks.send_email_task(
            mock_self, 
            "Test Subject", 
            "Body",         
            ["to@example.com"], 
        )

        assert result is False
        mock_email_cls.assert_called_once()

    @patch("voice_core.users.tasks.get_connection")
    @patch("voice_core.users.tasks.EmailMultiAlternatives")
    def test_smtp_authentication_error_triggers_retry(self, mock_email_cls, mock_get_connection, settings):
        mock_connection = MagicMock()
        mock_get_connection.return_value = mock_connection

        mock_email = MagicMock()
        mock_email.send.side_effect = SMTPAuthenticationError(534, b"auth failed") # Simulate SMTP auth error
        mock_email_cls.return_value = mock_email

        settings.DEFAULT_FROM_EMAIL = "from@example.com"

        mock_self = MagicMock()
        mock_self.request = SimpleNamespace(retries=1)
        mock_self.max_retries = 3

        real_task = tasks.send_email_task._get_current_object()

        with patch.object(type(real_task), "request", new_callable=PropertyMock) as mock_request:
            mock_request.return_value = SimpleNamespace(retries=2)

            with patch.object(real_task, "max_retries", 3):
                def raise_exc(countdown, exc):
                    raise exc

                with patch.object(real_task, "retry", side_effect=raise_exc) as mock_retry:
                    with pytest.raises(SMTPAuthenticationError):
                        tasks.send_email_task(
                            "Subject Test",
                            "Message Body ",
                            ["to@example.com"],
                        )

                    mock_email.send.assert_called_once()
                    mock_retry.assert_called_once()



    @patch("voice_core.users.tasks.get_connection")
    @patch("voice_core.users.tasks.EmailMultiAlternatives")
    def test_generic_exception_triggers_retry(self, mock_email_cls, mock_get_connection, settings):
        mock_connection = MagicMock()
        mock_get_connection.return_value = mock_connection

        mock_email = MagicMock()
        mock_email.send.side_effect = RuntimeError("boom")
        mock_email_cls.return_value = mock_email

        settings.DEFAULT_FROM_EMAIL = "from@example.com"

        real_task = tasks.send_email_task._get_current_object()

        with patch.object(type(real_task), "request", new_callable=PropertyMock) as mock_request:
            mock_request.return_value = SimpleNamespace(retries=2)

            with patch.object(real_task, "max_retries", 3):
                def raise_exc(countdown, exc):
                    raise exc

                with patch.object(real_task, "retry", side_effect=raise_exc) as mock_retry:
                    with pytest.raises(RuntimeError):
                        tasks.send_email_task(
                            "Subject Test",
                            "Message Body ",
                            ["to@example.com"],
                        )

                    mock_email.send.assert_called_once()
                    mock_retry.assert_called_once()
