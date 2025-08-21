from __future__ import annotations

import boto3
from botocore.exceptions import ClientError
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import PermissionDenied
from voice_core.users.utils import get_secret_hash

import logging
logger = logging.getLogger(__name__)

class CognitoBackend(BaseBackend):
    """Authenticate users against AWS Cognito for admin login."""

    def verify_with_cognito(self, username: str, password: str, expected_sub: str | None) -> bool:
        logger.info(f"[CognitoBackend] Starting congnito authentication for user: {username}")
        
        if not username or not password:
            logger.info(f"[CognitoBackend] Missing username or password")
            raise PermissionDenied("Missing username or password")
        
        client = boto3.client("cognito-idp", region_name=getattr(settings, "COGNITO_REGION", None))
        try:
            secret_hash = get_secret_hash(username)
            resp = client.initiate_auth(
                ClientId=settings.COGNITO_APP_CLIENT_ID,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": username,
                    "PASSWORD": password,
                    "SECRET_HASH": secret_hash
                },
            )
            
            access_token = resp["AuthenticationResult"]["AccessToken"]
            user_info = client.get_user(AccessToken=access_token)
            cognito_sub = next(
                (attr["Value"] for attr in user_info["UserAttributes"] if attr["Name"] == "sub"),
                None
            )

            if expected_sub and cognito_sub != expected_sub:
                logger.warning(
                    f"[CognitoBackend] Sub mismatch for {username}: "
                    f"Django={expected_sub}, Cognito={cognito_sub}"
                )
                return False

            logger.info(f"[CognitoBackend] Cognito verification succeeded for {username}")
            return True
        except ClientError as e:
            msg = getattr(e, 'response', {}).get('Error', {}).get('Message', str(e))
            logger.error(f"[CognitoBackend] Cognito authentication failed: {msg}")
            raise PermissionDenied(f"Cognito authentication failed: {msg}")


class CognitoAndModelBackend:
    """
    Authenticates the user with BOTH Cognito and Django's ModelBackend.
    If either fails, login fails.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        logger.info(f"[CognitoAndModelBackend] Starting combined authentication for user: {username}")
        if not username or not password:
            logger.error(f"[CognitoAndModelBackend] Missing username or password")
            raise PermissionDenied("Missing username or password")

        User = get_user_model()
        user = User.objects.filter(email=username).first()

        if not user:
            logger.error(f"[CognitoAndModelBackend] User not found")
            raise PermissionDenied("User not found")

        if not getattr(user, "cognito_sub", None):
            logger.error(f"[CognitoAndModelBackend] User is not linked to Cognito (missing cognito_sub)")
            raise PermissionDenied("User is not linked to Cognito (missing cognito_sub)")

        cognito_backend = CognitoBackend()
        if cognito_backend.verify_with_cognito(username, password, user.cognito_sub):
            logger.info(f"[CognitoAndModelBackend] Authentication succeeded for {username}")
            return user

        logger.error(f"[CognitoAndModelBackend] Authentication failed")
        raise PermissionDenied("Authentication failed")

    def get_user(self, user_id):
        User = get_user_model()
        return User.objects.filter(pk=user_id).first()
