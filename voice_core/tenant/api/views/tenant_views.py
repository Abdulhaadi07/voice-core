from django.db.models import Q
from django.contrib.admin.models import (
    ADDITION, 
    CHANGE,
    LogEntry, 
)
from django.contrib.contenttypes.models import ContentType
from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter, 
    OpenApiExample, 
    OpenApiResponse
)
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.decorators import action

from voice_core.services.extensions.assign_extension import assign_extension
from voice_core.services.wazo_helpers.wazo_admin_token import get_wazo_admin_token
from voice_core.services.wazo_helpers.wazo_tenant import get_wazo_tenant_uuid
from voice_core.tenant.models import Tenant
from voice_core.tenant.api.serializers.tenant_serializer import TenantSerializer
from voice_core.tenant.api.serializers.extension_serializer import AvailableExtensionsSerializer
from voice_core.tenant.api.serializers.extension_serializer import AssignExtensionSerializer
from voice_core.users.permissions import IsPlatformAdminOrTenantAdmin
from voice_core.services.extensions.available_extensions import get_available_extensions

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

    @extend_schema(
        summary="Create a new Tenant",
        description=(
            "Create a new Tenant with Wazo API integration.\n\n"
            "**Access:** Platform Admin only"
        ),
        request=TenantSerializer,
        responses={
            201: TenantSerializer,
            400: OpenApiResponse(description="Bad request"),
            409: OpenApiResponse(description="Tenant already exists or validation error"),
        },
    )
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

    @extend_schema(
        summary="Update tenant partially",
        description=(
            "Update specific fields of a tenant (name, domain, max_users, status).\n\n"
            "**Access:** Platform Admin only"
        ),
        request=TenantSerializer,
        responses={
            200: TenantSerializer,
            400: OpenApiResponse(description="Failed to update tenant"),
        },
    )
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
	
    @extend_schema(
        summary="List all tenants",
        description=(
            "Retrieve a list of all tenants.\n\n"
            "Supports optional search filter by name or domain.\n\n"
            "**Access:** Platform Admin only"
        ),
        parameters=[
            OpenApiParameter(
                name="search",
                description="Filter tenants by name or domain (case-insensitive)",
                required=False,
                type=str,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={200: TenantSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Retrieve a tenant",
        description=(
            "Retrieve details of a specific tenant by ID.\n\n"
            "**Access:** Platform Admin only"
        ),
        responses={
            200: TenantSerializer,
            404: OpenApiResponse(description="Tenant not found"),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
