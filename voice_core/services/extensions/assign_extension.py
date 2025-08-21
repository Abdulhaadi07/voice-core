from datetime import datetime
from typing import (
	Dict,
	List,
)

from voice_core.tenant.models import Tenant
from voice_core.users.models import (
	ExtensionAssignment, 
	User,
)
from voice_core.services.wazo_helpers.wazo_admin_token import get_wazo_admin_token
from voice_core.services.wazo_helpers.wazo_extensions import (
	create_line,
	create_extension,
	create_sip_endpoint,
	assign_line_with_sip_endpoint,
	assign_line_with_extension,
	assign_user_with_line,
	create_user_voicemail,
	unassign_line_with_sip_endpoint,
	unassign_line_with_extension,
	unassign_user_with_line,
	delete_sip_endpoint,
	delete_line,
	delete_extension,
	deassociate_user_with_voicemail,
	delete_voicemail,
)

import logging
logger = logging.getLogger(__name__)


def _rollback_extension_assignment(
	admin_token: str | None,
	tenant_uuid: str | None,
	*,
	line_id: int | None,
	sip_uuid: str | None,
	extension_id: int | None,
	user_uuid: str | None,
	voicemail_id: int | None,
) -> None:
	"""
	Best-effort Rollback of created/linked Wazo resources using helper functions.
	This function never raises; it logs any errors encountered during Rollback.
	"""
	if not admin_token or not tenant_uuid:
		return

	logger.info(
		f"Rollback starts tenant_uuid={tenant_uuid}, line_id={line_id}, sip_uuid={sip_uuid}, extension_id={extension_id}, user_uuid={user_uuid}, voicemail_id={voicemail_id}"
	)

	try:
		if user_uuid and line_id:
			ok = unassign_user_with_line(admin_token, tenant_uuid, user_uuid, line_id)
			if ok:
				logger.info(f"Rollback: Successfull to unassign user with line user_uuid={user_uuid} line_id={line_id}")
			else:
				logger.error(f"Rollback: failed to unassign user with line user_uuid={user_uuid} line_id={line_id}")
	except Exception as exc:
		logger.error(f"Rollback: exception at unassign user with line error={exc}", exc_info=True)

	try:
		if line_id and sip_uuid:
			ok = unassign_line_with_sip_endpoint(admin_token, tenant_uuid, line_id, sip_uuid)
			if ok:
				logger.info(f"Rollback: Successfull to unassign line with sip endpoint line_id={line_id} sip_uuid={sip_uuid}")
			else:
				logger.error(f"Rollback: failed to unassign line with sip endpoint line_id={line_id} sip_uuid={sip_uuid}")
	except Exception as exc:
		logger.error(f"Rollback: exception at unassign line with sip endpoint error={exc}", exc_info=True)

	try:
		if line_id and extension_id:
			ok = unassign_line_with_extension(admin_token, tenant_uuid, line_id, extension_id)
			if ok:
				logger.info(f"Rollback: Successfull to unassign line with extension line_id={line_id} extension_id={extension_id}")
			else:
				logger.error(f"Rollback: failed to unassign line with extension line_id={line_id} extension_id={extension_id}")
	except Exception as exc:
		logger.error(f"Rollback: exception at unassign line with extension error={exc}", exc_info=True)

	try:
		if sip_uuid:
			ok = delete_sip_endpoint(admin_token, tenant_uuid, sip_uuid)
			if ok:
				logger.info(f"Rollback: Successfull to delete sip endpoint sip_uuid={sip_uuid}")
			else:
				logger.error(f"Rollback: failed to delete sip endpoint sip_uuid={sip_uuid}")
	except Exception as exc:
		logger.error(f"Rollback: exception at delete sip endpoint error={exc}", exc_info=True)

	try:
		if line_id:
			ok = delete_line(admin_token, tenant_uuid, line_id)
			if ok:
				logger.info(f"Rollback: Successfull to delete line line_id={line_id}")
			else:
				logger.error(f"Rollback: failed to delete line line_id={line_id}")
	except Exception as exc:
		logger.error(f"Rollback: exception at delete line error={exc}", exc_info=True)

	try:
		if extension_id:
			ok = delete_extension(admin_token, tenant_uuid, extension_id)
			if ok:
				logger.info(f"Rollback: Successfull to delete extension extension_id={extension_id}")
			else:
				logger.error(f"Rollback: failed to delete extension extension_id={extension_id}")
	except Exception as exc:
		logger.error(f"Rollback: exception at delete extension error={exc}", exc_info=True)

	try:
		if voicemail_id and user_uuid:
			ok_to_deassociate_voicemail = deassociate_user_with_voicemail(admin_token, tenant_uuid, user_uuid)

			if ok_to_deassociate_voicemail :
				ok = delete_voicemail(admin_token, tenant_uuid, voicemail_id)
				if ok :
					logger.info(f"Rollback: Successfull to delete voicemail voicemail_id={voicemail_id}")
				else:
					logger.error(f"Rollback: failed to delete voicemail voicemail_id={voicemail_id}")

				logger.info(f"Rollback: Successfull to deassociate user with voicemail user_uuid={user_uuid}")
			else:
				logger.error(f"Rollback: failed to deassociate user with voicemail user uuid={user_uuid}")
	except Exception as exc:
		logger.error(f"Rollback: exception at delete voicemail error={exc}", exc_info=True)

	logger.info("Rollback: Successfully completed at extension assignment")

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
	
	# Track created resources for Rollback
	line_id = None
	extension_id = None
	sip_uuid = None
	user_uuid = None
	admin_token = None
	tenant_uuid = None
	voicemail_id = None

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
		create_line_start_time = datetime.now()
		line_id, provisioning_extension = create_line(admin_token, tenant_uuid, resolved_context_name)
		create_line_end_time = datetime.now()

		# 2) Create extension in context (exten is the number)
		extension_id = create_extension(admin_token, tenant_uuid, resolved_context_name, extension_int)
		create_extension_end_time = datetime.now()
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
		create_sip_endpoint_end_time = datetime.now()

		# 4) Attach SIP endpoint to line
		if not assign_line_with_sip_endpoint(admin_token, tenant_uuid, line_id, sip_uuid):
			raise RuntimeError("Failed to attach SIP endpoint to line")
		assign_line_with_sip_endpoint_end_time = datetime.now()

		# 5) Attach line to extension
		if not assign_line_with_extension(admin_token, tenant_uuid, line_id, extension_id):
			raise RuntimeError("Failed to attach line to extension")
		assign_line_with_extension_end_time = datetime.now()

		# 6) Attach line to user
		if not getattr(user, "wazo_user_id", None):
			raise ValueError("User is missing wazo_user_id")
		user_uuid = str(user.wazo_user_id)
		if not assign_user_with_line(admin_token, tenant_uuid, user_uuid, line_id):
			raise RuntimeError("Failed to attach line to user")
		assign_user_with_line_end_time = datetime.now()

		# 7) Persist local assignment
		voicemail_id, voicemail_pin, enabled_flag = create_user_voicemail(
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
		create_user_voicemail_end_time = datetime.now()

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
		
		# Step durations
		line_creation_time = (create_line_end_time - create_line_start_time).total_seconds()
		extension_creation_time = (create_extension_end_time - create_line_end_time).total_seconds()
		sip_endpoint_creation_time = (create_sip_endpoint_end_time - create_extension_end_time).total_seconds()
		assign_line_to_sip_time = (assign_line_with_sip_endpoint_end_time - create_sip_endpoint_end_time).total_seconds()
		assign_line_to_extension_time = (assign_line_with_extension_end_time - assign_line_with_sip_endpoint_end_time).total_seconds()
		assign_user_to_line_time = (assign_user_with_line_end_time - assign_line_with_extension_end_time).total_seconds()
		voicemail_creation_time = (create_user_voicemail_end_time - assign_user_with_line_end_time).total_seconds()

		# Total duration
		total_time = (create_user_voicemail_end_time - create_line_start_time).total_seconds()

		logger.info(
			f"Extension assignment completed successfully. "
			f"Line Creation: {line_creation_time:.3f}s, "
			f"Extension Creation: {extension_creation_time:.3f}s, "
			f"SIP Endpoint Creation: {sip_endpoint_creation_time:.3f}s, "
			f"Assign Line SIP: {assign_line_to_sip_time:.3f}s, "
			f"Assign Line Extension: {assign_line_to_extension_time:.3f}s, "
			f"Assign User Line: {assign_user_to_line_time:.3f}s, "
			f"Voicemail Creation: {voicemail_creation_time:.3f}s, "
			f"Total: {total_time:.3f}s"
		)
		return assignment

	except Exception as e:
		logger.error(
			f"Error assigning extension for tenant_id={tenant.id} user_id={getattr(user, 'id', 'unknown')}: {e}",
			exc_info=True,
		)
		# Attempt best-effort Rollback
		try:
			_rollback_extension_assignment(
				admin_token=admin_token,
				tenant_uuid=tenant_uuid,
				line_id=line_id,
				sip_uuid=sip_uuid,
				extension_id=extension_id,
				user_uuid=user_uuid,
				voicemail_id=voicemail_id,
			)
		except Exception as Rollback_exc:
			logger.error(f"Rollback encountered an error: {Rollback_exc}", exc_info=True)
		raise
		