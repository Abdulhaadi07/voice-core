import requests
from typing import Tuple
import uuid
from config.settings.base import WAZO_API_URL
from voice_core.tenant.models import Tenant
from voice_core.services.wazo_helpers.wazo_context import create_context

import logging
logger = logging.getLogger(__name__)

def get_wazo_tenant_uuid(tenant: Tenant, admin_token: str) -> Tuple[str, bool]: # return tenant_uuid, does_tenant_pre_exist flag
    if tenant.wazo_tenant_uuid is not None:
        logger.info(f"Get Wazo Tenant ID from db")
        return tenant.wazo_tenant_uuid, True
    #create tenant
    tenant_uuid = create_wazo_tenant(tenant.name, admin_token)
    logger.info(f"Created New Wazo tenant: {tenant_uuid}")

    # Update tenant object and save
    try:
        tenant.wazo_tenant_uuid = tenant_uuid
        tenant.save(update_fields=['wazo_tenant_uuid'])
        #create initial context
        context_data = create_context(tenant)
        # Store context data in tenant's contexts JSON field as a plain array of objects
        existing_contexts = tenant.contexts or []
        if isinstance(existing_contexts, dict):
            existing_contexts = list(existing_contexts.values())
        existing_contexts.append(context_data)
        tenant.contexts = existing_contexts
        tenant.save()
    except Exception as e:
        logger.info(f"Error saving tenant: {str(e)}")
        raise e 
    
    return tenant_uuid, False

def create_wazo_tenant(tenant_name: str, admin_token: str) -> str: # return tenant uuid
    wazo_api_url = WAZO_API_URL
    url = f"{wazo_api_url}/api/auth/0.1/tenants"
    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": admin_token
    }
    payload = {
        "name": tenant_name
    }
    logger.info(f"Tenant create request for: {payload}")
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            verify=False  # skip SSL verification like `curl -k`
        )
        
        if response.status_code == 200 or response.status_code == 201:
            logger.info("Tenant created successfully!")
            data = response.json()
            new_tenant_uuid = data["uuid"]
            
            return uuid.UUID(new_tenant_uuid)
        else:
            logger.info(f"Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        logger.info(f"Request failed: {e}")
        return None


# def delete_wazo_tenant(tenant_name: str, admin_token: str) -> str: # return tenant uuid
#     wazo_api_url = WAZO_API_URL
#     url = f"{wazo_api_url}/api/auth/0.1/tenants"
#     headers = {
#         "Content-Type": "application/json",
#         "X-Auth-Token": admin_token
#     }
#     payload = {
#         "name": tenant_name
#     }
#     logger.info(f"Tenant create request for: {payload}")
#     try:
#         response = requests.post(
#             url,
#             json=payload,
#             headers=headers,
#             verify=False  # skip SSL verification like `curl -k`
#         )
        
#         if response.status_code == 200 or response.status_code == 201:
#             logger.info("Tenant created successfully!")
#             data = response.json()
#             new_tenant_uuid = data["uuid"]
            
#             return uuid.UUID(new_tenant_uuid)
#         else:
#             logger.info(f"Error {response.status_code}: {response.text}")
#             return None
#     except Exception as e:
#         logger.info(f"Request failed: {e}")
#         return None
