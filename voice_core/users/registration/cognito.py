import boto3
import logging
from django.conf import settings
from botocore.exceptions import ClientError
from rest_framework.exceptions import ValidationError
from voice_core.users.utils import get_secret_hash
import time

logger = logging.getLogger(__name__)

# Initialize Cognito IDP client
client = boto3.client("cognito-idp", region_name=settings.COGNITO_REGION)

def create_cognito_user(email: str, password: str, name: str = "") -> str:
    """Creates a user in AWS Cognito and confirms the signup."""
    UserSub = None
    try:
        secret_hash = get_secret_hash(email)

        # Register user using sign_up (validates password properly)
        response = client.sign_up(
            ClientId=settings.COGNITO_APP_CLIENT_ID,
            Username=email,
            Password=password,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "name", "Value": name},
            ],
            SecretHash=secret_hash,
        )
        logger.info(f"Cognito sign-up successful: {response['UserSub']}")
        UserSub = response['UserSub']
        # Immediately confirm the user so no email/SMS flow is needed
        # Retry confirmation with backoff
        max_retries = 10
        for attempt in range(max_retries):
            try:
                client.admin_confirm_sign_up(
                    UserPoolId=settings.COGNITO_USER_POOL_ID,
                    Username=email,
                )
                logger.info(f"Cognito user confirmed: {email}")
                break
            except ClientError as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(f"Confirmation attempt {attempt + 1} failed, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"Confirmation attempt failed: exception {e}") 
                    raise Exception("Failed to confirm Cognito user")  # <-- explicit message


        logger.info(f"Cognito user confirmed: {email} ")
        return UserSub

    except Exception as e:
        # Rollback if user was partially created
        if UserSub:
            delete_cognito_user(email)

        # Map known exception messages to friendly errors
        error_message = str(e)
        if "InvalidPassword" in error_message:
            raise ValidationError({"password": error_message})
        elif "UsernameExists" in error_message:
            raise ValidationError({"email": "A user with this email already exists."})
        else:
            # Log and raise a generic exception
            logger.exception(f"Failed to create Cognito user: {error_message}")
            raise Exception(f"Failed to create Cognito user: {error_message}")


def delete_cognito_user(email: str) -> bool:
    """Deletes a user from AWS Cognito."""
    try:
        # Get user by username (email)
        response = client.admin_get_user(
            UserPoolId=settings.COGNITO_USER_POOL_ID,
            Username=email,
        )
        logger.info(f"User found for deletion: {response['Username']}")

        # Delete the user
        client.admin_delete_user(
            UserPoolId=settings.COGNITO_USER_POOL_ID,
            Username=email,
        )
        
        logger.info(f"Cognito user deleted successfully: {email}")
        return True
        
    except ClientError as e:
        if e.response["Error"].get("Code") == "UserNotFoundException":
            logger.warning(f"Cognito user not found for deletion: {email}")
            return True
        logger.error(f"Failed to delete Cognito user {email}: {e.response['Error']['Message']}")
        return False
    except Exception as e:
        # This is a catch-all for any other unexpected exceptions.
        logger.error(f"An unexpected error occurred while deleting Cognito user {email}: {e}")
        return False
