from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404

from drf_spectacular.utils import extend_schema

from rest_framework import generics, viewsets
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from voice_core.tenant.models import Tenant
from voice_core.users.api.serializers.user_serializer import (
    UserCreateSerializer,
    UserDetailSerializer,
    UserListSerializer,
    UserUpdateSerializer,
)

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
    permission_classes = [IsAdminUser]
    lookup_field = "pk"

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

    def perform_create(self, serializer):
        tenant_id = self.kwargs.get("tenant_id")
        tenant = get_object_or_404(Tenant, id=tenant_id)

        tenant_role = serializer.validated_data.get("tenant_role", "agent")

        try:
            user = serializer.save(tenant=tenant, tenant_role=tenant_role)
            logger.info(
                "Tenant user created",
                extra={
                    "tenant_id": tenant.id,
                    "user_id": user.id,
                    "email": user.email,
                    "role": user.tenant_role,
                },
            )
            return user
        except Exception as e:
            logger.error(
                "Failed to create tenant user",
                extra={"tenant_id": tenant.id, "error": str(e)},
            )
            raise

    def retrieve(self, request, *args, **kwargs):
        user_id = self.kwargs.get("pk")
        tenant_id = self.kwargs.get("tenant_id")
        tenant = get_object_or_404(Tenant, id=tenant_id)
        user = get_object_or_404(User, id=user_id, tenant=tenant)
        logger.info(
            "Tenant user retrieved",
            extra={"tenant_id": tenant.id, "user_id": user.id, "email": user.email},
        )
        
        serializer = UserDetailSerializer(user, context=self.get_serializer_context())
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        user_id = self.kwargs.get("pk")
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
            raise
