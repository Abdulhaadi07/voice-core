import hmac
import hashlib
import base64
from django.conf import settings
from voice_core.tenant.models import Tenant

def resolve_tenant_from_email(email: str) -> Tenant:
    domain = email.split("@")[-1].lower()
    tenant, _ = Tenant.objects.get_or_create(domain=domain, defaults={"name": domain})
    return tenant

def get_secret_hash(username: str) -> str:
    message = username + settings.COGNITO_APP_CLIENT_ID
    digest = hmac.new(
        settings.COGNITO_APP_CLIENT_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).digest()
    return base64.b64encode(digest).decode()