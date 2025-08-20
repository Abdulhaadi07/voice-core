import logging
from typing import List, Dict
from voice_core.tenant.models import Tenant
from voice_core.users.models import ExtensionAssignment, User

from voice_core.services.wazo_helpers.wazo_admin_token import get_wazo_admin_token
from voice_core.services.wazo_helpers.wazo_extentions import (
	create_line,
	create_extension,
	create_sip_endpoint,
	assign_line_with_sip_endpoint,
	assign_line_with_extension,
	assign_user_with_line,
	create_voicemail,
)

logger = logging.getLogger(__name__)


def assign_extension(
	tenant: Tenant, 
	extension_int: int, 
	sip_username: str, 
	sip_password: str, 
	user: User, 
	context_name: str,
	voicemail_pin: int,
	voicemail_max_messages: int
	):
	"""
	Provision resources in Wazo for a user and persist an ExtensionAssignment.
	"""
	
	try:
		admin_token = get_wazo_admin_token()
		if not tenant.wazo_tenant_uuid:
			raise ValueError("Tenant is missing wazo_tenant_uuid")
		tenant_uuid = str(tenant.wazo_tenant_uuid)

		# Resolve context name from tenant.contexts (list or legacy dict)
		raw_contexts = tenant.contexts or []
		if isinstance(raw_contexts, dict):
			contexts_iter = list(raw_contexts.values())
		else:
			contexts_iter = raw_contexts
		resolved_context_name = None
		for ctx in contexts_iter:
			if  ctx.get("name") == context_name:
				resolved_context_name = ctx.get("name") 
				break
		if not resolved_context_name:
			resolved_context_name = context_name

		# 1) Create line
		line_id, provisioning_extension = create_line(admin_token, tenant_uuid, resolved_context_name)

		# 2) Create extension in context (exten is the number)
		extension_id = create_extension(admin_token, tenant_uuid, resolved_context_name, extension_int)

		# 3) Create SIP endpoint
		sip_label = f"sip-E-{extension_int}-L-{line_id}"
		sip_name = sip_label
		sip_uuid, _, _ = create_sip_endpoint(
			admin_token=admin_token,
			tenant_uuid=tenant_uuid,
			username=sip_username,
			password=sip_password,
			label=sip_label
		)

		# 4) Attach SIP endpoint to line
		if not assign_line_with_sip_endpoint(admin_token, tenant_uuid, line_id, sip_uuid):
			raise RuntimeError("Failed to attach SIP endpoint to line")

		# 5) Attach line to extension
		if not assign_line_with_extension(admin_token, tenant_uuid, line_id, extension_id):
			raise RuntimeError("Failed to attach line to extension")

		# 6) Attach line to user
		if not getattr(user, "wazo_user_id", None):
			raise ValueError("User is missing wazo_user_id")
		if not assign_user_with_line(admin_token, tenant_uuid, str(user.wazo_user_id), line_id):
			raise RuntimeError("Failed to attach line to user")
		
		# 7) Persist local assignment
		voicemail_id, voicemail_pin, enabled_flag = create_voicemail(
				wazo_user_id=str(user.wazo_user_id),
				tenant_uuid=tenant_uuid,
				admin_token=admin_token,
				context_name=resolved_context_name,
				email=user.email,
				extension_number=str(extension_int),
				pin=voicemail_pin,
				name=user.name,
				max_messages = voicemail_max_messages,
			)
		# 8) Persist local assignment
		assignment = ExtensionAssignment.objects.create(
			extension=str(extension_int),
			sip_username=sip_username,
			sip_password=sip_password,
			user=user,
			wazo_line_id=line_id,
			context_name=context_name,
			voicemail_id = voicemail_id,
			voicemail_pin = voicemail_pin,
			voicemail_enabled = enabled_flag
		)
		logger.info(
			f"Extension assigned | tenant_id={tenant.id} user_id={user.id} line_id={line_id} extension={extension_int} context='{context_name}'"
		)
		return assignment

	except Exception as e:
		logger.error(
			f"Error assigning extension for tenant_id={tenant.id} user_id={getattr(user, 'id', 'unknown')}: {e}",
			exc_info=True,
		)
		raise