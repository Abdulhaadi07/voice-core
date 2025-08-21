import logging
from config.settings.base import WAZO_API_URL
import requests
import uuid
import random
import string

logger = logging.getLogger(__name__)

def create_wazo_user(user: any, admin_token: str, tenant_uuid: uuid) -> [str, str]: 
    wazo_api_url = WAZO_API_URL
    url = f"{wazo_api_url}/api/confd/1.1/users"
    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": admin_token,
        "Wazo-Tenant": str(tenant_uuid),
    }
    random_password = generate_valid_password()
    logger.info(f"User create request for: {user.first_name} {user.last_name} {user.name} {user.email} {random_password}")
    payload = {
        "firstname": user.first_name if user.first_name else user.name,
        "lastname": user.last_name if user.last_name else "",
        "username": user.name,
        "email": user.email,
        "password": random_password,
        "auth": {
            "email_address": user.email,
            "enabled": True,
            "firstname": user.first_name if user.first_name else user.name,
            "lastname": user.last_name if user.last_name else "",
            "password": random_password,
            "purpose": "user",
            "username":  user.name,
        }
    }
    logger.info(f"User create request for: {payload}")

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            verify=False  # skip SSL verification like `curl -k`
        )
        if response.status_code == 200 or response.status_code == 201:
            data = response.json()
            logger.info(f"User created successfully!: {data}")
            
            wazo_user_id = uuid.UUID(data["uuid"])
            wazo_username = data["username"]
            if wazo_username is None:
                wazo_username = ""
            return [wazo_user_id, wazo_username]
        else:
            logger.error(f"Fail to create wazo user! {response.status_code} {response.text}")
            return None
    except Exception as e:
        logger.error("Error calling Wazo API to create user:", e)
        raise Exception(str(e)) 

def generate_valid_password(length=12):
    if length < 4:
        raise ValueError("Length must be at least 4 to include all required character types.")

    safe_specials = "$&*-+"
    
    uppercase = random.choice(string.ascii_uppercase)
    lowercase = random.choice(string.ascii_lowercase)
    digit = random.choice(string.digits)
    special = random.choice(safe_specials)

    others = random.choices(
        string.ascii_letters + string.digits + safe_specials,
        k=length - 4
    )

    password_list = list(uppercase + lowercase + digit + special + ''.join(others))
    random.shuffle(password_list)

    return ''.join(password_list)

def delete_wazo_user(wazo_user_id: uuid, admin_token: str):
    wazo_api_url = WAZO_API_URL
    url = f"{wazo_api_url}/api/confd/1.1/users{wazo_user_id}"
    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": admin_token,
    }

    try:
        response = requests.delete(
            url, 
            headers=headers, 
            verify=False
        )  
        if response.status_code == 204:
            return True
        else:
            logger.error(f"Failed to delete Wazo user: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error calling Wazo API to delete user: {e}")
        return False

def get_wazo_users_by_tenant(tenant_uuid: str, admin_token: str) -> dict:
    """
    Fetch the list of users from Wazo confd for the given tenant.
    """
    wazo_api_url = WAZO_API_URL
    url = f"{wazo_api_url}/api/confd/1.1/users?recurse=false"
    headers = {
        "accept": "application/json",
        "Wazo-Tenant": tenant_uuid,
        "X-Auth-Token": admin_token
    }

    logger.info(f"Fetching Wazo users for tenant: {tenant_uuid}")
    try:
        response = requests.get(url, headers=headers, verify=False)  # -k in curl disables SSL verification
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Fetched {len(data.get('items', []))} Wazo users for tenant: {tenant_uuid}")
            return data
        else:
            print(f"Error at Wazo.py {response.status_code}: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Failed to fetch Wazo users for tenant {tenant_uuid}: {e}")
        raise

