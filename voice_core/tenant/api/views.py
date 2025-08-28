from django.db.models import Q
from django.contrib.admin.models import (
    ADDITION, 
    CHANGE,
    LogEntry, 
)
from django.contrib.contenttypes.models import ContentType
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.decorators import action

from voice_core.services.extensions.assign_extension import assign_extension
from voice_core.services.wazo_helpers.wazo_admin_token import get_wazo_admin_token
from voice_core.services.wazo_helpers.wazo_tenant import get_wazo_tenant_uuid
from voice_core.tenant.models import Tenant
from voice_core.tenant.api.serializers import ( 
	TenantSerializer, 
	AvailableExtensionsSerializer,
)
from voice_core.users.permissions import IsPlatformAdminOrTenantAdmin
from voice_core.services.extensions.available_extensions import get_available_extensions
from voice_core.tenant.api.extension_assignment_serializer import AssignExtensionSerializer
from voice_core.users.models import (
	User, 
	ExtensionAssignment,
)


import logging
logger = logging.getLogger(__name__)


@extend_schema(tags=["Tenant Management"])
class TenantViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):  
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAdminUser] # only platform admin access 

    def get_queryset(self):
        queryset = Tenant.objects.all()
        search = self.request.query_params.get("search")
        if search:
            logger.info(f"Filtering tenants with search='{search}'")
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(domain__icontains=search)
            )
        return queryset


    def create(self, request, *args, **kwargs):
        """
        Create a new Tenant with Wazo API integration requesting by platform admin.
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            tenant = serializer.save()

            logger.info(
                f"Creating new Tenant | Name: {tenant.name} | Domain: {tenant.domain} | "
                f"Max Users: {tenant.max_users} | Status: {tenant.status} | "
                f"Requested by: {request.user.username}"
            )

            # Admin action audit log
            LogEntry.objects.log_action(
                user_id=request.user.pk,
                content_type_id=ContentType.objects.get_for_model(Tenant).pk,
                object_id=tenant.pk,
                object_repr=str(tenant),
                action_flag=ADDITION,
                change_message="Tenant created via Admin API",
            )

            # Check if tenant already exists in Wazo 
            admin_token = get_wazo_admin_token()
            tenant_uuid, does_tenant_pre_exist = get_wazo_tenant_uuid(
                tenant, admin_token
            )
            if does_tenant_pre_exist:
                logger.warning(f"Tenant already exists in Wazo: name={request.data.get('name')}")
                return Response(
                    {"detail": f"Tenant '{request.data['name']}' already exists in Wazo."},
                    status=status.HTTP_409_CONFLICT,
                )
            # Save Tenant 
            tenant.wazo_tenant_uuid = tenant_uuid
            tenant.save(update_fields=["wazo_tenant_uuid"])
            logger.info(f"Tenant created successfully: id={tenant.id}, name={tenant.name}")
            return Response(self.get_serializer(tenant).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            logger.error(
                f"ValidationError creating new Tenant: {e} | "
                f"Name: {request.data.get('name')} | Domain: {request.data.get('domain')} | "
                f"Max Users: {request.data.get('max_users')} | "
                f"Requested by: {request.user.username}"
            )
            return Response(e.detail, status=status.HTTP_409_CONFLICT)

    def partial_update(self, request, *args, **kwargs):
        try:
            tenant = self.get_object()

            logger.info(
                f"Updating Tenant (ID: {tenant.id}) | "
                f"Current: Name='{tenant.name}', Domain='{tenant.domain}', "
                f"Max Users={tenant.max_users}, Status='{tenant.status}' | "
                f"Requested by: {request.user.username}"
            )
            logger.info(
                f"Updating Tenant (ID: {tenant.id}) | New values: {request.data}"
            )

            # Admin action audit log
            LogEntry.objects.log_action(
                user_id=request.user.pk,
                content_type_id=ContentType.objects.get_for_model(Tenant).pk,
                object_id=tenant.pk,
                object_repr=str(tenant),
                action_flag=CHANGE,
                change_message=f"Tenant updated fields: {list(request.data.keys())}",
            )

            serializer = self.get_serializer(tenant, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error updating Tenant {tenant.id if 'tenant' in locals() else 'unknown'}: {e}")
            return Response(
                {"detail": "Failed to update tenant."},
                status=status.HTTP_400_BAD_REQUEST
            )



@extend_schema(tags=["Extension Management"])
class ExtensionViewSet(viewsets.GenericViewSet):
	permission_classes = [IsPlatformAdminOrTenantAdmin] # only platform admin or tenant admin can access 
	def get_serializer_class(self):
		if self.action == "available":
			return AvailableExtensionsSerializer
		if self.action == "assign":
			return AssignExtensionSerializer
		return super().get_serializer_class()

	@action(detail=False, methods=["get"], url_path="available")
	def available(self, request, tenant_id=None):
		logger.info(f"Getting available extensions for tenant: {tenant_id}")
		if not tenant_id:
			return Response({"detail": "tenant_id is required"}, status=status.HTTP_400_BAD_REQUEST)
		try:
			tenant_id = int(tenant_id)
			available_extensions_by_context = get_available_extensions(tenant_id)
			serializer = AvailableExtensionsSerializer({"contexts": available_extensions_by_context})
			return Response(serializer.data)
		except ValueError:
			return Response({"detail": "Invalid tenant_id format"}, status=status.HTTP_400_BAD_REQUEST)
		except Exception as e:
			logger.error(f"Error getting available extensions for tenant {tenant_id}: {e}")
			return Response({"detail": "Failed to retrieve available extensions"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

	@action(detail=False, methods=["post"], url_path="assign")
	def assign(self, request, tenant_id=None, user_id=None):


		logger.info(f"Assign extension requested tenant_id={tenant_id}, user_id={user_id}")
		if not tenant_id or not user_id:
			return Response({"detail": "tenant_id and user_id are required"}, status=status.HTTP_400_BAD_REQUEST)

		try:
			tenant_id = int(tenant_id)
			user_id = int(user_id)
		except ValueError:
			return Response({"detail": "Invalid tenant_id or user_id"}, status=status.HTTP_400_BAD_REQUEST)

		# Validate payload
		ser = AssignExtensionSerializer(data=request.data)
		ser.is_valid(raise_exception=True)
	    
		extension_int = ser.validated_data.get("extension")
		sip_username = ser.validated_data.get("sip_username")
		sip_password = ser.validated_data.get("sip_password")
		voicemail_max_messages = ser.validated_data.get("voicemail_max_messages")
		voicemail_pin = ser.validated_data.get("voicemail_pin")

		# Fetch user and tenant
		try:
			user = User.objects.select_related("tenant").get(pk=user_id, tenant_id=tenant_id)
		except User.DoesNotExist:
			return Response({"detail": "User not found for this tenant"}, status=status.HTTP_404_NOT_FOUND)

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
			return Response({"detail": f"Context '{context_name}' not found for tenant"}, status=status.HTTP_400_BAD_REQUEST)

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

		if not available_in_ctx or extension_int not in available_in_ctx:
			return Response({"detail": f"Extension {extension_int} not available in context '{context_name}'"}, status=status.HTTP_400_BAD_REQUEST)
		
		# Uniqueness checks
		if ExtensionAssignment.objects.filter(extension=str(extension_int), context_name=context_name).exists():
			return Response(
				{"detail": f"Extension {extension_int} already assigned in context '{context_name}'"},
				status=status.HTTP_409_CONFLICT
			)

		# Check if the SIP username is already in use in this context
		if ExtensionAssignment.objects.filter(sip_username=sip_username, context_name=context_name).exists():
			return Response(
				{"detail": f"SIP username '{sip_username}' already in use in context '{context_name}'"},
				status=status.HTTP_409_CONFLICT
			)
		logger.info(f"{context_name} ,,, {extension_int},,,,{user.name} ,,, {user.id}")

		assignment = assign_extension(
			tenant=tenant,
			extension_int=extension_int,
			sip_username=sip_username,
			sip_password=sip_password,
			user=user,
			context_name=context_name,
			voicemail_pin= voicemail_pin,
			voicemail_max_messages = voicemail_max_messages,
		)

		# Update user config to enable extension 
		user.config.extension_enabled = True
		user.config.save()

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