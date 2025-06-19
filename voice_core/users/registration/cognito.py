import boto3
import logging
from django.conf import settings
from botocore.exceptions import ClientError
from rest_framework.exceptions import ValidationError
from voice_core.users.utils import get_secret_hash

logger = logging.getLogger(__name__)

# Initialize Cognito IDP client
client = boto3.client("cognito-idp", region_name=settings.COGNITO_REGION)

def create_cognito_user(email: str, password: str, name: str = "") -> str:
    """Creates a user in AWS Cognito and confirms the signup."""
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

        # Immediately confirm the user so no email/SMS flow is needed
        client.admin_confirm_sign_up(
            UserPoolId=settings.COGNITO_USER_POOL_ID,
            Username=email,
        )
        logger.info(f"Cognito user confirmed: {email}")

        return response["UserSub"]

    except client.exceptions.InvalidPasswordException as e:
        raise ValidationError({"password": e.response["Error"]["Message"]})
    except client.exceptions.UsernameExistsException as e:
        raise ValidationError({"email": "A user with this email already exists in Cognito."})
    except ClientError as e:
        logger.error(f"Failed to create Cognito user: {e.response['Error']['Message']}")
        raise Exception(f"Failed to create Cognito user: {e.response['Error']['Message']}")
