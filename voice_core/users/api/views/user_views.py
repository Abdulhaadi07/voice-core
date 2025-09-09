from django.contrib.admin.models import ( 
    LogEntry, 
    CHANGE,
) 
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
)
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from voice_core.users.models import User, ExtensionAssignment
from voice_core.users.api.serializers.role_serializer import RoleAssignmentSerializer
from voice_core.users.api.serializers.user_serializer import UserSerializer, UserDetailSerializer

import logging
logger = logging.getLogger(__name__)


class UserViewSet(CreateModelMixin, GenericViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.none()
    lookup_field = "pk"

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        if self.action == "assign_role":
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_object(self):
        return self.request.user

    @extend_schema(
        summary="Get current user details",
        description=(
            "Retrieve details of the currently authenticated user.\n\n"
            "**Access:** Authenticated users only."
        ),
        responses={
            200: UserDetailSerializer,
            401: OpenApiResponse(description="Authentication required"),
        },
    )
    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        logger.info(f"User 'me' endpoint accessed by user_id={request.user.id}")
        serializer = UserDetailSerializer(request.user, context={"request": request})
        return Response(serializer.data)

    
    @extend_schema(
        tags=["Role Management"],
        summary="Assign Platform Role to User",
        description=(
            "Assign a platform role (`admin`, `supervisor`, `agent`) to a user. "
            "This will replace any existing platform roles.\n\n"
            "**Access:** Admin users only."
        ),
        request=RoleAssignmentSerializer,
        responses={
            200: OpenApiResponse(
                description="Role assigned successfully",
                response={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "roles": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            ),
            400: OpenApiResponse(description="Validation error (invalid role or request body)"),
            403: OpenApiResponse(description="Forbidden – only admins can assign roles"),
            404: OpenApiResponse(description="User not found"),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="assign-role"
    )
    def assign_role(self, request, pk=None): # assign platform role
        user = get_object_or_404(User, pk=pk)
        logger.info(f"Assigning platform role to user_id={user.id}, email={user.email}")
        serializer = RoleAssignmentSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            updated_user = serializer.save(user=user)
            # Django admin log: record role assignment as a change on the User
            LogEntry.objects.log_action(
                user_id=request.user.pk,
                content_type_id=ContentType.objects.get_for_model(User).pk,
                object_id=updated_user.pk,
                object_repr=str(updated_user),
                action_flag=CHANGE,
                change_message=f"Assigned platform roles: {list(updated_user.groups.values_list('name', flat=True))}",
            )
            logger.info(f"Role assignment success for user_id={updated_user.id}, roles={list(updated_user.groups.values_list('name', flat=True))}")
        except Exception as exc:
            logger.error(f"Role assignment failed for user_id={user.id}: {exc}")
            return Response(
                {"detail": f"Role assignment failed: {str(exc)}", "message": f"Role assignment failed: {str(exc)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                "message": f"Role assigned successfully to {updated_user.email}",
                "roles": list(updated_user.groups.values_list("name", flat=True)),
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Register a new user",
        description=(
            "Create a new user in the system (sign up).\n\n"
            "**Access:** Public (no authentication required)."
        ),
        request=UserSerializer,
        responses={
            201: UserDetailSerializer,
            400: OpenApiResponse(description="Validation error (invalid or missing fields)"),
        },
    )
    def create(self, request, *args, **kwargs):
        """Signup endpoint at POST /api/users/"""
        try:
            return super().create(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Unexpected error in user creation: {e}", exc_info=True)
            return Response({"message": f"Something went wrong: {str(e)}."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)