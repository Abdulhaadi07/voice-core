from django.contrib.admin.models import ( 
    LogEntry, 
    CHANGE,
) 
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import CreateModelMixin
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from voice_core.users.models import User
from voice_core.users.api.serializers.role_serializer import RoleAssignmentSerializer
from voice_core.users.api.serializers.user_serializer import UserSerializer

import logging
logger = logging.getLogger(__name__)


class UserViewSet(CreateModelMixin, GenericViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.none()
    lookup_field = "pk"

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_object(self):
        return self.request.user

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        logger.info(f"User 'me' endpoint accessed by user_id={request.user.id}")
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    
    @extend_schema(tags=["Role Management"])
    @action(
        detail=True,
        methods=["post"],
        url_path="assign-role",
        permission_classes=[IsAuthenticated, IsAdminUser]
    )
    def assign_role(self, request, pk=None): # assign platform role
        user = get_object_or_404(User, pk=pk)
        logger.info(f"Assigning platform role to user_id={user.id}, email={user.email}")

        serializer = self.get_serializer_class()(data=request.data)
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
            raise

        return Response(
            {
                "message": f"Role assigned successfully to {updated_user.email}",
                "roles": list(updated_user.groups.values_list("name", flat=True)),
            },
            status=status.HTTP_200_OK,
        )

    def get_serializer_class(self):
        if self.action == "assign_role":
            return RoleAssignmentSerializer
        return super().get_serializer_class()
