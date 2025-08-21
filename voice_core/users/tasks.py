from django.core.mail import get_connection, EmailMultiAlternatives
from django.conf import settings
from celery import shared_task
from smtplib import SMTPAuthenticationError
from typing import List, Optional, Sequence

import logging
logger = logging.getLogger(__name__)

@shared_task()
def get_users_count():
    """A pointless Celery task to demonstrate usage."""
    print("UserCount")
    from .models import User
    return User.objects.count()

@shared_task(bind=True, max_retries=3)
def send_email_task(
    self,
    subject: str,
    message: str,
    recipient_list: List[str],
    from_email: Optional[str] = None,
    html_message: Optional[str] = None,
    fail_silently: bool = False,
    cc: Optional[Sequence[str]] = None,
    bcc: Optional[Sequence[str]] = None,
    reply_to: Optional[Sequence[str]] = None,
) -> bool:
    try:   
        logger.info(f"Sending Welcome mail to  {recipient_list}")
        # Fallback to default sender from settings
        if not from_email:
            from_email = (
                getattr(settings, "DEFAULT_FROM_EMAIL", None)
                or getattr(settings, "EMAIL_HOST_USER", None)
            )

        if not from_email:
            logger.error(
                "No DEFAULT_FROM_EMAIL or EMAIL_HOST_USER configured; cannot send email."
            )
            return False
        # passr = getattr(settings, "EMAIL_HOST_PASSWORD", None)
        # Explicit SMTP connection (use settings)
        connection = get_connection(
            backend=getattr(settings, "EMAIL_BACKEND", None),
            host=getattr(settings, "EMAIL_HOST", None),
            port=getattr(settings, "EMAIL_PORT", None),
            username=getattr(settings, "EMAIL_HOST_USER", None),
            password=getattr(settings, "EMAIL_HOST_PASSWORD", None),
            use_tls=getattr(settings, "EMAIL_USE_TLS", False),
            use_ssl=getattr(settings, "EMAIL_USE_SSL", False),
            timeout=getattr(settings, "EMAIL_TIMEOUT", 5),
        )   

        logger.info(f"Sending Email from {connection.username}")

        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=f"Welcome to Netapse <{from_email}>",
            to=recipient_list,
            cc=list(cc) if cc else [],
            bcc=list(bcc) if bcc else [],
            reply_to=[getattr(settings, "EMAIL_REPLY_TO", None)], 
            connection=connection,
        )

        if html_message:
            email.attach_alternative(html_message, "text/html")

        sent_count = email.send(fail_silently=fail_silently)

        if sent_count:
            logger.info(
                "Email sent successfully | to=%s backend=%s host=%s port=%s tls=%s ssl=%s",
                recipient_list,
                getattr(settings, "EMAIL_BACKEND", None),
                getattr(settings, "EMAIL_HOST", None),
                getattr(settings, "EMAIL_PORT", None),
                getattr(settings, "EMAIL_USE_TLS", None),
                getattr(settings, "EMAIL_USE_SSL", None),
            )
            return True

        logger.warning("Email send() returned 0 | to=%s", recipient_list)
        return False

    except SMTPAuthenticationError as exc:
        logger.error(
            "SMTP authentication failed (code=%s). If using Gmail, configure App Passwords.",
            getattr(exc, "smtp_code", "unknown"),
            exc_info=True
        )
        logger.debug(f"DEBUG: In SMTPAuthError - retries: {self.request.retries}, max_retries: {self.max_retries}")
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying email task (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries), exc=exc)
        logger.error(f"Email task failed after {self.max_retries} retries")
        raise  

    except Exception as exc:
        logger.error(f"Failed to send email to {recipient_list}", exc_info=True)
        if getattr(self, "request", None) and self.request.retries < self.max_retries:
            logger.info(f"Retrying email task (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries), exc=exc)
        logger.error(f"Email task failed after {self.max_retries} retries")
        raise exc
