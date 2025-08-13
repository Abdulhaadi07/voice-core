import logging
import os
from voice_core.users.tasks import send_email_task

logger = logging.getLogger(__name__)

def send_welcome_msg(name: str, email: str):
    try:
        send_email_task.delay(
            subject="🎉 Welcome to Voice Core!",
            message=(
                 f"Hi {name},\n\n"
                "Welcome aboard! 🎉\n"
                "Thank you for joining Netapse – we’re excited to have you with us.\n\n"
                "Cheers,\n"
                "The Netapse Team"
            ),
            recipient_list=[email],
        )
        logger.info(f"Welcome email task has been queued for {email}")
    except Exception as e:
        logger.error(f"Failed to enqueue welcome email task for {email}: {e}")
