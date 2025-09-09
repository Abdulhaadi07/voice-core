from django.db.models import Q
from django.contrib.admin.models import (
    ADDITION, 
    CHANGE,
    LogEntry, 
)
from django.contrib.contenttypes.models import ContentType
from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
)
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action

from voice_core.services.extensions.assign_extension import assign_extension
from voice_core.users.permissions import IsPlatformAdminOrTenantAdmin
from voice_core.services.extensions.available_extensions import get_available_extensions
from voice_core.tenant.api.serializers.extension_serializer import AvailableExtensionsSerializer
from voice_core.tenant.api.serializers.extension_serializer import AssignExtensionSerializer
from voice_core.users.models import (
	User, 
	ExtensionAssignment,
)

import logging
logger = logging.getLogger(__name__)


@extend_schema(tags=["Extension Management"])
class ExtensionViewSet(viewsets.GenericViewSet):
	permission_classes = [IsPlatformAdminOrTenantAdmin] # only platform admin or tenant admin can access 
	def get_serializer_class(self):
		if self.action == "available":
			return AvailableExtensionsSerializer
		if self.action == "assign":
			return AssignExtensionSerializer
		return super().get_serializer_class()

	@extend_schema(
        summary="Get available extensions",
        description=(
            "Retrieve a list of available extensions for a given tenant, grouped by contexts.\n\n"
            "**Access:** Platform Admin or Tenant Admin"
        ),
        responses={
            200: AvailableExtensionsSerializer,
            400: OpenApiResponse(description="Missing or invalid tenant_id"),
            500: OpenApiResponse(description="Failed to retrieve available extensions"),
        },
    )
	@action(detail=False, methods=["get"], url_path="available")
	def available(self, request, tenant_id=None):
		logger.info(f"Getting available extensions for tenant: {tenant_id}")
		# 401 when not authenticated
		if not request.user or not request.user.is_authenticated:
			return Response({"message": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
		if not tenant_id:
			return Response({"detail": "tenant_id is required", "message": "tenant_id is required"}, status=status.HTTP_400_BAD_REQUEST)
		try:
			tenant_id = int(tenant_id)
			available_extensions_by_context = get_available_extensions(tenant_id)
			serializer = AvailableExtensionsSerializer({"contexts": available_extensions_by_context})
			return Response(serializer.data)
		except ValueError:
			return Response({"detail": "Invalid tenant_id format", "message": "Invalid tenant_id format"}, status=status.HTTP_400_BAD_REQUEST)
		except Exception as e:
			logger.error(f"Error getting available extensions for tenant {tenant_id}: {e}")
			msg = str(e)
			return Response({"message": f"Failed to retrieve available extensions: {msg}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

	@extend_schema(
        summary="Assign an extension to a user",
        description=(
            "Assign a specific extension, SIP credentials, and optional voicemail settings "
            "to a user within a tenant.\n\n"
            "**Access:** Platform Admin or Tenant Admin"
        ),
        request=AssignExtensionSerializer,
        responses={
            201: OpenApiResponse(
                description="Extension assigned successfully",
                response={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "user_id": {"type": "integer"},
                        "tenant_id": {"type": "integer"},
                        "line_id": {"type": "string"},
                        "extension": {"type": "string"},
                        "sip_username": {"type": "string"},
                        "context_name": {"type": "string"},
                    },
                },
            ),
            400: OpenApiResponse(description="Validation error (e.g. missing tenant_id, user_id, or bad context)"),
            404: OpenApiResponse(description="User not found"),
            409: OpenApiResponse(description="Extension or SIP username already in use"),
        },
    )
	@action(detail=False, methods=["post"], url_path="assign")
	def assign(self, request, tenant_id=None, user_id=None):
		try: 
			logger.info(f"Assign extension requested tenant_id={tenant_id}, user_id={user_id}")
			# 401 when not authenticated
			if not request.user or not request.user.is_authenticated:
				return Response({"message": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
			if not tenant_id or not user_id:
				return Response({"detail": "tenant_id and user_id are required", "message": "tenant_id and user_id are required"}, status=status.HTTP_400_BAD_REQUEST)

			try:
				tenant_id = int(tenant_id)
				user_id = int(user_id)
			except ValueError as e:
				msg = (list(e.detail.values())[0][0] if isinstance(e.detail, dict) else e.detail[0])
				return Response({"detail": f"Invalid tenant_id or user_id: {msg}"}, status=status.HTTP_400_BAD_REQUEST)

			# Validate payload
			ser = AssignExtensionSerializer(data=request.data)
			ser.is_valid(raise_exception=True)
			
			extension_num = ser.validated_data.get("extension")
			sip_username = ser.validated_data.get("sip_username")
			sip_password = ser.validated_data.get("sip_password")
			voicemail_max_messages = ser.validated_data.get("voicemail_max_messages")
			voicemail_pin = ser.validated_data.get("voicemail_pin")

			# Fetch user and tenant
			try:
				user = User.objects.select_related("tenant").get(pk=user_id, tenant_id=tenant_id)
			except User.DoesNotExist:
				return Response({"detail": "User not found for this tenant", "message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

			# Uniqueness checks
			if ExtensionAssignment.objects.filter(user=user).exists():
				return Response(
					{"message": f"Extension already assigned to this user"},
					status=status.HTTP_409_CONFLICT
				)

			tenant = user.tenant
			# contexts is stored as a list of objects; support legacy dict for backward compatibility
			raw_contexts = tenant.contexts or []
			if isinstance(raw_contexts, dict):
				contexts_iter = list(raw_contexts.values())
			else:
				contexts_iter = raw_contexts
			# Determine context_name from request or default to first context
			context_name = ser.validated_data.get("context_name")
			if not context_name:
				first_ctx = next(iter(contexts_iter), None)
				if not first_ctx:
					return Response({"detail": "No contexts configured for tenant"}, status=status.HTTP_400_BAD_REQUEST)
				context_name = first_ctx.get("name")
			# Find context by name
			matched_context = None
			for ctx in contexts_iter:
				if ctx.get("name") == context_name:
					matched_context = ctx
					break
			if not matched_context:
				return Response({"detail": f"Context '{context_name}' not found for tenant", "message": f"Context '{context_name}' not found for tenant"}, status=status.HTTP_400_BAD_REQUEST)

			available_by_context = get_available_extensions(tenant.id)  
			
			available_in_ctx = None
			
			if context_name in available_by_context:
				available_in_ctx = available_by_context[context_name]
			else:
				for key, vals in available_by_context.items():
					if key == matched_context.get("name"):
						available_in_ctx = vals
						break
			logger.info(f"available_by_context: {available_in_ctx}, {available_by_context}")

			if not available_in_ctx or extension_num not in available_in_ctx:
				return Response({"detail": f"Extension {extension_num} not available in context '{context_name}'", "message": f"Extension {extension_num} not available in context '{context_name}'"}, status=status.HTTP_400_BAD_REQUEST)
			
			# Uniqueness checks
			if ExtensionAssignment.objects.filter(extension=str(extension_num), context_name=context_name).exists():
				return Response(
					{"detail": f"Extension {extension_num} already assigned in context '{context_name}'", "message": f"Extension {extension_num} already assigned in context '{context_name}'", "code": "EXTENSION_TAKEN"},
					status=status.HTTP_409_CONFLICT
				)

			# Check if the SIP username is already in use in this context
			if ExtensionAssignment.objects.filter(sip_username=sip_username, context_name=context_name).exists():
				return Response(
					{"detail": f"SIP username '{sip_username}' already in use in context '{context_name}'", "message": f"SIP username '{sip_username}' already in use in context '{context_name}'", "code": "SIP_USERNAME_TAKEN"},
					status=status.HTTP_409_CONFLICT
				)
			logger.info(f"{context_name} ,,, {extension_num},,,,{user.name} ,,, {user.id}")

			try: 
				assignment = assign_extension(
					tenant=tenant,
					extension_num=extension_num,
					sip_username=sip_username,
					sip_password=sip_password,
					user=user,
					context_name=context_name,
					voicemail_pin= voicemail_pin,
					voicemail_max_messages = voicemail_max_messages,
				)

				logger.info(f"Assigned extension {assignment.extension} to user_id={user.id} in context '{context_name}'")
				return Response(
					{
						"message": "Extension assigned successfully",
						"user_id": user.id,
						"tenant_id": tenant.id,
						"line_id": assignment.wazo_line_id,
						"extension": assignment.extension,
						"sip_username": assignment.sip_username,
						"context_name": assignment.context_name,
					},
					status=status.HTTP_201_CREATED,
				)
			except Exception as e:
				msg = str(e)
				return Response({"detail": f"Extension assignment request failed: {msg}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
		except Exception as e:
			logger.error(f"Error in assign extension: {e}")
			return Response({"message": "Something went wrong."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


		