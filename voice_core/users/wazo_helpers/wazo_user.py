import logging
from config.settings.local import WAZO_API_URL
import requests
import uuid
import random
import string

logger = logging.getLogger(__name__)

def create_wazo_user(user: any, admin_token: str, tenant_uuid: uuid) -> [str, str]: 
    wazo_api_url = WAZO_API_URL
    url = f"{wazo_api_url}/api/auth/0.1/users"
    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": admin_token,
        "Wazo-Tenant": str(tenant_uuid),
    }
    random_password = generate_valid_password()
    payload = {
        "firstname": user.first_name,
        "lastname": user.last_name,
        "username": user.name,
        "email_address": user.email,
        "password": random_password,
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
    if length < 3:
        raise ValueError("Length must be at least 3 to include all required character types.")
    
    # Required characters
    uppercase = random.choice(string.ascii_uppercase)
    digit = random.choice(string.digits)
    special = random.choice(string.punctuation)

    # Fill the rest with random letters, digits, or punctuation
    others = random.choices(string.ascii_letters + string.digits + string.punctuation, k=length - 3)

    # Combine all characters and shuffle
    password_list = list(uppercase + digit + special + ''.join(others))
    random.shuffle(password_list)
    
    return ''.join(password_list)

def delete_wazo_user(wazo_user_id: uuid, admin_token: str):
    wazo_api_url = WAZO_API_URL
    url = f"{wazo_api_url}/api/auth/0.1/users/{wazo_user_id}"
    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": admin_token,
    }

    try:
        response = requests.delete(
            url, 
            headers=headers, 
            verify=False
        )  # adjust verify as needed
        if response.status_code == 204:
            # 204 No Content means successful deletion
            return True
        else:
            logger.error(f"Failed to delete Wazo user: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error calling Wazo API to delete user: {e}")
        return False
