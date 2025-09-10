from django.contrib.auth import get_user_model
from django.contrib.admin.models import ( 
    LogEntry, 
    ADDITION, 
    CHANGE,
)
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
)
from rest_framework import generics, viewsets, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError as DRFValidationError
import requests
import socket

from voice_core.users.permissions import IsPlatformAdminOrTenantAdmin
from voice_core.tenant.models import Tenant
from voice_core.users.api.serializers.user_serializer import (
    UserCreateSerializer,
    UserDetailSerializer,
    UserListSerializer,
    UserUpdateSerializer,
)
from voice_core.custom_error_exception import extract_error_message

import logging
logger = logging.getLogger(__name__)


User = get_user_model()

@extend_schema(tags=["User Management"])
class TenantUserViewSet(viewsets.GenericViewSet,
                        generics.ListAPIView,
                        generics.CreateAPIView):
    """
    Tenant-scoped users:
    - list users
      - with search
    - create user
    - partial update
    - retrieve user
    """
    permission_classes = [IsPlatformAdminOrTenantAdmin]
    lookup_field = "user_id"
    serializer_class = UserListSerializer
    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action == "retrieve":
            return UserDetailSerializer
        if self.action == "partial_update":
            return UserUpdateSerializer
        return UserListSerializer

    def get_queryset(self):
        tenant_id = self.kwargs.get("tenant_id")
        tenant = get_object_or_404(Tenant, id=tenant_id)

        queryset = User.objects.filter(tenant=tenant).select_related("tenant")
        search = self.request.query_params.get("search")
        if search:
            logger.info(f"Filtering users for tenant={tenant.id} with search='{search}'")
            queryset = queryset.filter(Q(email__icontains=search) | Q(name__icontains=search))
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["tenant_id"] = self.kwargs.get("tenant_id")
        return context

    @extend_schema(
        summary="Create Tenant User",
        description=(
            "Create a new user under the specified tenant. "
            "You can assign a tenant role (default is `agent`).\n\n"
            "**Access:** Platform Admin or Tenant Admin"
        ),
        request=UserCreateSerializer,
        responses={
            201: UserDetailSerializer,
            400: OpenApiResponse(description="Bad request"),
            409: OpenApiResponse(description="Conflict: user already exists or validation error"),
            503: OpenApiResponse(description="Service unavailable"),
        },
    )
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            # Tenant limit check
            tenant_id = self.kwargs.get("tenant_id")
            tenant = get_object_or_404(Tenant, id=tenant_id)
            current_count = User.objects.filter(tenant_id=tenant_id).count()
            if getattr(tenant, "max_users", None) is not None and current_count >= tenant.max_users:
                return Response({"message": "Max user count reached for this tenant"}, status=400)

            # Duplicate email fast fail
            email = serializer.validated_data.get("email")
            if User.objects.filter(email=email, tenant_id=tenant_id).exists():
                return Response({"message": "User already exists"}, status=409)

            # Try create with one retry on timeout for external calls inside manager
            try:
                user = self.perform_create(serializer)
            except (socket.timeout, requests.Timeout):
                logger.warning("Timeout during user creation, retrying once...")
                try:
                    user = self.perform_create(serializer)
                except Exception as e:
                    logger.warning(f"Error during user creation: {e}")
                    return Response({"message": f"System busy. Try again later. {str(e)}"}, status=503)
            except DRFValidationError as e:
                logger.warning(f"Validation error during user creation: {str(e)}")
                return Response({"message": f"Validation error during user creation: {str(e)}"}, status=400)
            except Exception as e:
                msg = str(e)
                return Response({"message": f"Registration failed: {msg}"}, status=400)

            headers = self.get_success_headers(serializer.data)
            # If this isn't a real User instance (e.g., MagicMock in tests), avoid heavy serialization
            if isinstance(user, User):
                payload = UserDetailSerializer(user, context=self.get_serializer_context()).data
            else:
                payload = serializer.data
            return Response(payload, status=201, headers=headers)
        except DRFValidationError as ve:
            logger.warning(f"Validation error during user creation: {str(ve)}")
            return Response({"message": f"Validation error during user creation. {extract_error_message(ve)}"}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as ve:
            logger.warning(f"ValueError during user creation: {str(ve)}")
            return Response({"message": f"ValueError during user creation. {extract_error_message(ve)}"}, status=status.HTTP_400_BAD_REQUEST) 
        except Exception as e:
            logger.error(f"Unexpected error in user creation: {e}", exc_info=True)
            return Response({"message": f"Something went wrong. {extract_error_message(e)}."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)   

    @extend_schema(
        summary="Retrieve Tenant User",
        description=(
            "Get detailed information about a specific user belonging to a tenant.\n\n"
            "**Access:** Platform Admin or Tenant Admin"
        ),
        responses={
            200: UserDetailSerializer,
            404: OpenApiResponse(description="User not found"),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        try:
            user_id = self.kwargs.get("user_id")
            tenant_id = self.kwargs.get("tenant_id")
            tenant = get_object_or_404(Tenant, id=tenant_id)
            user = get_object_or_404(User, id=user_id, tenant=tenant)
            logger.info(
                "Tenant user retrieved",
                extra={"tenant_id": tenant.id, "user_id": user.id, "email": user.email},
            )
            
            serializer = UserDetailSerializer(user, context=self.get_serializer_context())
            return Response(serializer.data)
        except Exception as e:  
            logger.error(f"Error retrieving tenant user: {e}", exc_info=True)
            return Response({"message": f"Something went wrong. {extract_error_message(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        summary="Update Tenant User",
        description=(
            "Partially update fields of a user belonging to a tenant. "
            "Supports updating fields like `name`, `email`, or `tenant_role`.\n\n"
            "**Access:** Platform Admin or Tenant Admin"
        ),
        request=UserUpdateSerializer,
        responses={
            200: UserDetailSerializer,
            400: OpenApiResponse(description="Failed to update tenant user"),
        },
    )
    def partial_update(self, request, *args, **kwargs):
        user_id = self.kwargs.get("user_id")
        tenant_id = self.kwargs.get("tenant_id")
        tenant = get_object_or_404(Tenant, id=tenant_id)
        user = get_object_or_404(User, id=user_id, tenant=tenant)
        logger.info(f"Partial update tenant user start: tenant_id={tenant.id}, user_id={user.id}")

        serializer = UserUpdateSerializer(
            user, data=request.data, partial=True, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        try:
            updated_user = serializer.save()
            logger.info(
                "Tenant user updated",
                extra={
                    "tenant_id": tenant.id,
                    "user_id": updated_user.id,
                    "changes": request.data,
                },
            )
            # Admin log for update
            LogEntry.objects.log_action(
                user_id=request.user.pk,
                content_type_id=ContentType.objects.get_for_model(User).pk,
                object_id=updated_user.pk,
                object_repr=str(updated_user),
                action_flag=CHANGE,
                change_message=f"Updated tenant user fields: {list(request.data.keys())}",
            )
            return Response(
                UserDetailSerializer(
                    updated_user, context=self.get_serializer_context()
                ).data
            )
        except Exception as e:
            logger.error(
                "Failed to update tenant user",
                extra={"tenant_id": tenant.id, "user_id": user.id, "error": str(e)},
            )
            msg = str(e)
            return Response(
                {"message": f"User update request failed. {msg}"},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @extend_schema(
        summary="List Tenant Users",
        description=(
            "Retrieve a list of users belonging to the specified tenant. "
            "Supports search by email and name using `?search=` query parameter.\n\n"
            "**Access:** Platform Admin or Tenant Admin"
        ),
        responses={
            200: UserListSerializer,
            400: OpenApiResponse(description="Bad request"),
        },
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        tenant_id = self.kwargs.get("tenant_id")
        tenant = get_object_or_404(Tenant, id=tenant_id)

        tenant_role = serializer.validated_data.get("tenant_role", "agent")

        try:
            user = serializer.save(tenant=tenant, tenant_role=tenant_role)
            logger.info(
                f"Tenant user created. Tenant_id: {tenant.id}, user_id: {user.id}, email: {user.email}, tenant_role: {user.tenant_role}"
            )
            # Admin audit log for creation
            LogEntry.objects.log_action(
                user_id=self.request.user.pk,
                content_type_id=ContentType.objects.get_for_model(User).pk,
                object_id=user.pk,
                object_repr=str(user),
                action_flag=ADDITION,
                change_message=f"Created tenant user in tenant {tenant.id}",
            )
            return user
        except Exception as e:
            logger.error(
                "Failed to create tenant user",
                extra={"tenant_id": tenant.id, "error": str(e)},
            )
            # from rest_framework.exceptions import ValidationError
            raise e
